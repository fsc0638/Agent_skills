"""
mcp-meeting-to-notion — 會議紀錄自動上傳 Notion

4-Phase AI Pipeline:
  Phase 1: Sanitizer    (文本清洗 → 去噪 + 語意重組 + 翻譯)
  Phase 2: Org Parser   (人員歸戶 → 人名識別 + 部門映射 + 角色區分)
  Phase 3: Schema Mapper(Notion 映射 → 11 欄位 + 專案前綴 + 時間推論)
  Phase 4: QA Inspector (品質檢核 → 本地 Python 驗證，無需 LLM)
  Upload:  Notion Upsert(模糊比對 → UPDATE / INSERT)
"""

import os
import sys
import json
import csv
import re
import traceback
from datetime import datetime, timedelta
from pathlib import Path
from difflib import SequenceMatcher


# ── Configuration ────────────────────────────────────────────────────────────

SKILL_DIR = Path(__file__).resolve().parent.parent
CONFIG_DIR = SKILL_DIR / "config"
PROMPTS_DIR = SKILL_DIR / "prompts"

NOTION_API_BASE = "https://api.notion.com/v1"
NOTION_VERSION = "2022-06-28"

# LLM model for Phase 1-3 (cheap + fast)
LLM_MODEL = os.getenv("MEETING_LLM_MODEL", "gpt-4.1-mini")


# ── Helper: LLM Call ─────────────────────────────────────────────────────────

def call_llm(prompt: str, max_tokens: int = 4096) -> str:
    """Call OpenAI API for text generation. Returns raw text response."""
    import openai

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("Missing OPENAI_API_KEY environment variable")

    client = openai.OpenAI(api_key=api_key)
    response = client.chat.completions.create(
        model=LLM_MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3,
        max_tokens=max_tokens,
    )
    return response.choices[0].message.content.strip()


def extract_json(text: str):
    """Extract JSON from text that may contain markdown fences or filler."""
    if not text:
        return None

    # 1. Direct parse
    try:
        return json.loads(text.strip())
    except json.JSONDecodeError:
        pass

    # 2. Remove markdown fences
    cleaned = re.sub(r"```json\s*", "", text)
    cleaned = re.sub(r"```\s*", "", cleaned).strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    # 3. Brute-force: find outermost JSON structure
    starts = [cleaned.find("{"), cleaned.find("[")]
    start = min(s for s in starts if s >= 0) if any(s >= 0 for s in starts) else -1
    ends = [cleaned.rfind("}"), cleaned.rfind("]")]
    end = max(ends) if any(e >= 0 for e in ends) else -1

    if start >= 0 and end > start:
        try:
            return json.loads(cleaned[start : end + 1])
        except json.JSONDecodeError:
            pass

    raise ValueError(f"Cannot extract valid JSON from text (first 200 chars): {text[:200]}")


# ── Config Loaders ───────────────────────────────────────────────────────────

def load_notion_schema() -> dict:
    """Load Notion database schema from local config."""
    path = CONFIG_DIR / "notion_schema.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {}


def load_department_list() -> str:
    """Load department list as text for prompt injection."""
    path = CONFIG_DIR / "department_list.txt"
    if path.exists():
        return path.read_text(encoding="utf-8")
    return "Y200 研發中心-開發處\nT200 (一)產品開發一處\nC130 資訊處"


def load_employee_names() -> set:
    """Load employee names from CSV for hallucination guard."""
    names = set()
    path = CONFIG_DIR / "personal_list.csv"
    if not path.exists():
        return names

    try:
        with open(path, "r", encoding="utf-8-sig") as f:
            reader = csv.reader(f)
            header = next(reader, None)
            if not header:
                return names

            # Try to find name columns (flexible header matching)
            name_cols = []
            for i, col in enumerate(header):
                col_lower = col.strip().lower()
                if any(kw in col_lower for kw in ["name", "姓名", "名前", "名字"]):
                    name_cols.append(i)

            # Fallback: use first two columns
            if not name_cols:
                name_cols = [0, 1] if len(header) > 1 else [0]

            for row in reader:
                for col_idx in name_cols:
                    if col_idx < len(row) and row[col_idx].strip():
                        names.add(row[col_idx].strip())
    except Exception:
        pass

    return names


def load_source_options(schema: dict) -> list:
    """Extract allowed source options from Notion schema."""
    source_field = schema.get("來源", {})
    options = source_field.get("options", [])
    if isinstance(options, list) and options:
        # Options might be strings or dicts with "name" key
        result = []
        for opt in options:
            if isinstance(opt, str):
                result.append(opt)
            elif isinstance(opt, dict) and "name" in opt:
                result.append(opt["name"])
        return result
    return ["商業模式", "外部合作", "法律法規", "會議記錄", "董事會顧問會議", "董事長交辦", "KWAY研發中心"]


def load_prompt(filename: str) -> str:
    """Load a prompt template from the prompts/ directory."""
    path = PROMPTS_DIR / filename
    if path.exists():
        return path.read_text(encoding="utf-8")
    raise FileNotFoundError(f"Prompt template not found: {path}")


# ── Phase 1: Sanitizer ──────────────────────────────────────────────────────

def phase1_sanitize(transcript: str, language: str) -> str:
    """Clean raw transcript: de-noise, rephrase, translate."""
    template = load_prompt("phase1_sanitizer.txt")
    prompt = template.replace("{language}", language).replace("{transcript}", transcript)

    result = call_llm(prompt, max_tokens=4096)
    return result


# ── Phase 2: Org Parser ─────────────────────────────────────────────────────

def phase2_org_parse(
    cleaned_text: str,
    department_code: str | None,
    employee_names: set,
    department_list: str,
) -> dict:
    """Identify people, departments, and roles."""
    template = load_prompt("phase2_org_parser.txt")

    # Build hints
    dept_hint = ""
    if department_code:
        dept_hint = f"⚠️ 使用者已指定部門代碼：{department_code}，請以此為優先參考。"

    employee_sample = "、".join(list(employee_names)[:50]) if employee_names else ""
    employee_hint = ""
    if employee_sample:
        employee_hint = f"\n【公司員工名單 (部分)】僅供參考：\n{employee_sample}"

    prompt = (
        template
        .replace("{dept_hint}", dept_hint)
        .replace("{employee_hint}", employee_hint)
        .replace("{department_list}", department_list)
        .replace("{cleaned_text}", cleaned_text)
    )

    result = call_llm(prompt, max_tokens=2048)
    org_data = extract_json(result)

    # ── Hallucination Guard: strict validation for 負責人 ──
    OBVIOUS_FAKES = {"王小華", "張偉", "李強", "王強", "陳明", "李佳", "張麗", "王芳"}

    if employee_names:
        # Strict: 負責人 must be in employee list
        if isinstance(org_data.get("負責人"), list):
            valid = [n for n in org_data["負責人"] if n == "待指派" or n in employee_names]
            org_data["負責人"] = valid if valid else ["待指派"]

        # Relaxed: 識別人員 / 執行人 — only block obvious fakes
        for field in ["識別人員", "執行人"]:
            if isinstance(org_data.get(field), list):
                org_data[field] = [n for n in org_data[field] if n not in OBVIOUS_FAKES]

    # Force override with user-specified department
    if department_code:
        org_data["責任部門代碼"] = department_code

    return org_data


# ── Phase 3: Schema Mapper ──────────────────────────────────────────────────

def phase3_schema_map(
    cleaned_text: str,
    org_data: dict,
    language: str,
    source_options: list,
) -> list:
    """Convert cleaned text + org data → Notion JSON Array."""
    template = load_prompt("phase3_schema_mapper.txt")

    today = datetime.now().strftime("%Y-%m-%d")
    date_compact = datetime.now().strftime("%Y%m%d")
    # Validate department code: must be alphanumeric (e.g. T255, Y200, KWAY)
    # Fallback to "KWAY" if LLM returned non-code values like "待指派", "N/A", etc.
    _raw_dept = org_data.get("責任部門代碼", "KWAY") or "KWAY"
    dept_code = _raw_dept if re.match(r'^[A-Za-z0-9]+$', _raw_dept) else "KWAY"
    project_prefix = f"{dept_code}_{date_compact}"
    meeting_lead = (org_data.get("負責人") or ["待指派"])[0]

    # Build candidate list
    identified = org_data.get("識別人員", [])
    if isinstance(identified, list):
        identified = [p if isinstance(p, str) else p.get("姓名", "") for p in identified]
    executors = org_data.get("執行人", [])
    candidates = list(set([*identified, *executors, meeting_lead]) - {"待指派", "", None})
    candidate_str = ", ".join(candidates) if candidates else "待指派"

    source_str = ", ".join(source_options)

    prompt = (
        template
        .replace("{language}", language)
        .replace("{project_prefix}", project_prefix)
        .replace("{candidate_str}", candidate_str)
        .replace("{meeting_lead}", meeting_lead)
        .replace("{source_options}", source_str)
        .replace("{today}", today)
        .replace("{cleaned_text}", cleaned_text)
    )

    result = call_llm(prompt, max_tokens=8192)
    json_array = extract_json(result)
    if not isinstance(json_array, list):
        json_array = [json_array]

    # ── Hallucination Guard: programmatic validation of 負責人 ──
    candidate_set = set(candidates)
    candidate_set.add("待指派")

    for item in json_array:
        if item.get("負責人"):
            owners = item["負責人"] if isinstance(item["負責人"], list) else [item["負責人"]]
            valid = [n for n in owners if n in candidate_set]
            item["負責人"] = valid if valid else ["待指派"]
        else:
            item["負責人"] = ["待指派"]

    return json_array


# ── Phase 4: QA Inspector (local Python, no LLM) ────────────────────────────

GARBAGE_WORDS = {"然後", "那個", "比較", "就是", "出來", "這樣子", "對對對"}

ALLOWED_STATUSES = {"未開始", "進行中", "完成", "已完成"}


def phase4_qa_inspect(items: list, source_options: list) -> tuple[list, list]:
    """
    Validate and clean the JSON array. Returns (clean_items, errors).
    Fixes minor issues in-place; flags major issues in errors list.
    """
    errors = []
    today = datetime.now().strftime("%Y-%m-%d")
    source_set = set(source_options)

    for idx, item in enumerate(items):
        # 4.1 Fix 建立時間
        if item.get("建立時間") != today:
            item["建立時間"] = today

        # 4.2 ToDo length check (20-50 chars, warning only)
        todo = item.get("ToDo", "")
        if len(todo) < 10:
            errors.append({
                "item_index": idx,
                "field": "ToDo",
                "error_type": "TOO_SHORT",
                "current_length": len(todo),
                "value": todo,
            })
        elif len(todo) > 60:
            # Truncate gracefully
            item["ToDo"] = todo[:50]
            errors.append({
                "item_index": idx,
                "field": "ToDo",
                "error_type": "TRUNCATED",
                "original_length": len(todo),
            })

        # 4.3 Garbage keyword scan in ToDo + 關鍵詞
        for field in ["ToDo", "關鍵詞"]:
            val = item.get(field, "")
            if isinstance(val, list):
                item[field] = [v for v in val if v not in GARBAGE_WORDS]
            elif isinstance(val, str):
                for gw in GARBAGE_WORDS:
                    if gw in val:
                        errors.append({
                            "item_index": idx,
                            "field": field,
                            "error_type": "GARBAGE_KEYWORD",
                            "found": gw,
                        })

        # 4.4 Status validation
        status = item.get("狀態", "未開始")
        if status not in ALLOWED_STATUSES:
            item["狀態"] = "未開始"
            errors.append({
                "item_index": idx,
                "field": "狀態",
                "error_type": "INVALID_STATUS",
                "found": status,
            })

        # 4.5 Source validation
        source = item.get("來源", [])
        if isinstance(source, str):
            source = [source]
            item["來源"] = source
        invalid_sources = [s for s in source if s not in source_set]
        if invalid_sources:
            item["來源"] = [s for s in source if s in source_set] or ["會議記錄"]
            errors.append({
                "item_index": idx,
                "field": "來源",
                "error_type": "INVALID_SOURCE",
                "found": invalid_sources,
                "replaced_with": item["來源"],
            })

        # 4.6 Ensure array fields are arrays
        for field in ["專案", "負責人", "執行人", "責任部門", "階段里程碑", "關鍵詞", "來源"]:
            val = item.get(field)
            if val is not None and not isinstance(val, list):
                item[field] = [val]

    return items, errors


# ── Notion Upload ────────────────────────────────────────────────────────────

def similarity(a: str, b: str) -> float:
    """Fuzzy string similarity (0-1)."""
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()


def _notion_headers(token: str) -> dict:
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Notion-Version": NOTION_VERSION,
    }


def _build_notion_properties(item: dict) -> dict:
    """Convert flat item dict → Notion API properties format."""
    props = {}

    # Title (ToDo)
    if item.get("ToDo"):
        props["ToDo"] = {"title": [{"text": {"content": item["ToDo"]}}]}

    # Multi-select fields (map internal names → actual Notion property names)
    MULTI_SELECT_MAP = {
        "專案": "專案",
        "負責人": "負責人 / PM",    # Notion 欄位名含 " / PM"
        "執行人": "執行人",
        "責任部門": "責任部門",
        "來源": "來源",
        "關鍵詞": "關鍵詞",
    }
    for internal_name, notion_name in MULTI_SELECT_MAP.items():
        vals = item.get(internal_name, [])
        if isinstance(vals, str):
            vals = [vals]
        if vals:
            props[notion_name] = {"multi_select": [{"name": v} for v in vals if v]}

    # Rich text field (階段里程碑 — Notion type: rich_text)
    milestone = item.get("階段里程碑", [])
    if isinstance(milestone, list) and milestone:
        text = "、".join(str(v) for v in milestone if v)
        if text:
            props["階段里程碑"] = {"rich_text": [{"text": {"content": text}}]}
    elif isinstance(milestone, str) and milestone:
        props["階段里程碑"] = {"rich_text": [{"text": {"content": milestone}}]}

    # Status
    if item.get("狀態"):
        props["狀態"] = {"status": {"name": item["狀態"]}}

    # Date (到期日)
    if item.get("到期日"):
        props["到期日"] = {"date": {"start": item["到期日"]}}

    # Date (建立時間 — Notion type: date)
    if item.get("建立時間"):
        props["建立時間"] = {"date": {"start": item["建立時間"]}}

    # Number (工時)
    if item.get("工時") is not None:
        try:
            props["工時"] = {"number": float(item["工時"])}
        except (TypeError, ValueError):
            pass

    return props


def upload_to_notion(items: list, token: str, database_id: str) -> list:
    """
    Upload items to Notion with Upsert logic.
    Returns list of result dicts with _action: created/updated/error.
    """
    import requests

    headers = _notion_headers(token)
    results = []

    # Pre-fetch existing pages for dedup (query last 100 pages)
    existing_titles = {}
    try:
        query_resp = requests.post(
            f"{NOTION_API_BASE}/databases/{database_id}/query",
            headers=headers,
            json={"page_size": 100, "sorts": [{"timestamp": "created_time", "direction": "descending"}]},
            timeout=15,
        )
        if query_resp.ok:
            for page in query_resp.json().get("results", []):
                # Extract title from properties
                for prop_name, prop_val in page.get("properties", {}).items():
                    if prop_val.get("type") == "title":
                        title_parts = prop_val.get("title", [])
                        if title_parts:
                            title_text = title_parts[0].get("plain_text", "")
                            if title_text:
                                existing_titles[title_text] = page["id"]
                        break
    except Exception:
        pass  # Failed to query — will insert all as new

    # Process each item
    for item in items:
        todo_title = item.get("ToDo", "")
        properties = _build_notion_properties(item)

        try:
            # Check for duplicate (similarity > 0.8)
            best_match_id = None
            best_sim = 0.0
            for existing_title, page_id in existing_titles.items():
                sim = similarity(todo_title, existing_title)
                if sim > best_sim:
                    best_sim = sim
                    best_match_id = page_id

            if best_match_id and best_sim > 0.8:
                # UPDATE existing page
                update_resp = requests.patch(
                    f"{NOTION_API_BASE}/pages/{best_match_id}",
                    headers=headers,
                    json={"properties": properties},
                    timeout=15,
                )
                if update_resp.ok:
                    results.append({**item, "_action": "updated", "_similarity": round(best_sim, 2)})
                else:
                    err = update_resp.json()
                    results.append({**item, "_action": "error", "_error": err.get("message", str(update_resp.status_code))})
            else:
                # CREATE new page
                create_resp = requests.post(
                    f"{NOTION_API_BASE}/pages",
                    headers=headers,
                    json={"parent": {"database_id": database_id}, "properties": properties},
                    timeout=15,
                )
                if create_resp.ok:
                    results.append({**item, "_action": "created"})
                else:
                    err = create_resp.json()
                    results.append({**item, "_action": "error", "_error": err.get("message", str(create_resp.status_code))})

        except Exception as e:
            results.append({**item, "_action": "error", "_error": str(e)})

    return results


# ── Main Entry Point ─────────────────────────────────────────────────────────

def main():
    # 1. Read parameters (injected by UMA ExecutionEngine)
    transcript = os.getenv("SKILL_PARAM_TRANSCRIPT", "")
    language = os.getenv("SKILL_PARAM_LANGUAGE", "繁體中文")
    department_code = os.getenv("SKILL_PARAM_DEPARTMENT_CODE", "") or None

    if not transcript:
        print(json.dumps({"status": "error", "message": "未提供會議逐字稿內容 (transcript 參數為空)"}, ensure_ascii=False))
        return

    # 2. Read credentials
    notion_token = os.getenv("NOTION_TOKEN", "")
    notion_db_id = os.getenv("NOTION_DATABASE_ID", "")

    if not notion_token or not notion_db_id:
        print(json.dumps({
            "status": "error",
            "message": "缺少 Notion 設定：請在 .env 中配置 NOTION_TOKEN 和 NOTION_DATABASE_ID"
        }, ensure_ascii=False))
        return

    # 3. Load reference data
    schema = load_notion_schema()
    department_list = load_department_list()
    employee_names = load_employee_names()
    source_options = load_source_options(schema)

    try:
        # ── Phase 1: Sanitizer ──
        cleaned_text = phase1_sanitize(transcript, language)

        # ── Phase 2: Org Parser ──
        org_data = phase2_org_parse(cleaned_text, department_code, employee_names, department_list)

        # ── Phase 3: Schema Mapper ──
        json_array = phase3_schema_map(cleaned_text, org_data, language, source_options)

        # ── Phase 4: QA Inspector ──
        validated_items, qa_errors = phase4_qa_inspect(json_array, source_options)

        # ── Upload to Notion ──
        upload_results = upload_to_notion(validated_items, notion_token, notion_db_id)

        # Tally results
        created = sum(1 for r in upload_results if r.get("_action") == "created")
        updated = sum(1 for r in upload_results if r.get("_action") == "updated")
        errored = sum(1 for r in upload_results if r.get("_action") == "error")

        # Build summary for each item (keep output concise for LINE)
        item_summaries = []
        for r in upload_results:
            summary = {
                "ToDo": r.get("ToDo", ""),
                "負責人": r.get("負責人", []),
                "來源": r.get("來源", []),
                "_action": r.get("_action", "unknown"),
            }
            if r.get("_error"):
                summary["_error"] = r["_error"]
            item_summaries.append(summary)

        output = {
            "status": "success",
            "total": len(upload_results),
            "created": created,
            "updated": updated,
            "errors": errored,
            "qa_warnings": len(qa_errors),
            "items": item_summaries,
        }

        if qa_errors:
            output["qa_details"] = qa_errors[:10]  # Cap to avoid huge output

        print(json.dumps(output, ensure_ascii=False))

    except Exception:
        print(json.dumps({
            "status": "error",
            "message": f"Pipeline 執行失敗：{traceback.format_exc()}"
        }, ensure_ascii=False))


if __name__ == "__main__":
    main()
