"""
mcp-notion-crud — Notion ToDo 資料庫完整 CRUD 操作

支援動作:
  create:        新增單筆 ToDo
  create_batch:  批次匯入（支援 Schema Mapping + Upsert）
  list:          依條件篩選待辦事項
  summary:       整體進度摘要
  update:        更新指定頁面欄位（支援 keyword 定位）
  update_batch:  條件式批次更新（依篩選條件批量修改欄位）
  delete:        封存（軟刪除）指定頁面（支援 keyword 定位）
  delete_batch:  條件式批次刪除（依篩選條件批量封存）

篩選語法:
  filter_status:   "已完成" | "not:已完成"
  filter_date:     "today" | "2026-04-15" | "before:2026-04-15" | "after:2026-04-15" | "2026-04-01:2026-04-15"
  filter_due_date: "overdue" | "upcoming" | "before:2026-04-15" | "after:2026-04-15" | "2026-04-15" | "range"
"""

import os
import sys
import json
import re
import time
import traceback
from datetime import datetime, timedelta
from pathlib import Path
from difflib import SequenceMatcher

import requests

# ── Configuration ────────────────────────────────────────────────────────────

NOTION_API_BASE = "https://api.notion.com/v1"
NOTION_VERSION = "2022-06-28"

SKILL_DIR = Path(__file__).resolve().parent.parent
CONFIG_DIR = SKILL_DIR / "config"
PROMPTS_DIR = SKILL_DIR / "prompts"

# LLM model for Schema Mapping (Phase 3)
LLM_MODEL = os.getenv("MEETING_LLM_MODEL", "gpt-4.1-mini")


def _safe_int_env(name: str, default: int) -> int:
    raw = os.getenv(name, str(default)).strip()
    try:
        return int(raw)
    except (TypeError, ValueError):
        return default


# Safety guard: prevent accidental large destructive operations.
MAX_SAFE_BATCH_DELETE = max(1, min(_safe_int_env("NOTION_MAX_SAFE_BATCH_DELETE", 20), 200))


def _headers(token: str) -> dict:
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Notion-Version": NOTION_VERSION,
    }


# ── Notion Query ─────────────────────────────────────────────────────────────

def query_database(token: str, database_id: str, filter_obj: dict | None = None,
                   page_size: int = 100, max_pages: int = 10) -> list:
    """Query Notion database with optional filter. Handles pagination."""
    headers = _headers(token)
    all_results = []
    has_more = True
    start_cursor = None
    pages_fetched = 0

    while has_more and pages_fetched < max_pages:
        body = {
            "page_size": min(page_size, 100),
            "sorts": [{"timestamp": "last_edited_time", "direction": "descending"}],
        }
        if filter_obj:
            body["filter"] = filter_obj
        if start_cursor:
            body["start_cursor"] = start_cursor

        resp = requests.post(
            f"{NOTION_API_BASE}/databases/{database_id}/query",
            headers=headers, json=body, timeout=15,
        )
        if not resp.ok:
            err = resp.json()
            raise RuntimeError(f"Notion API error: {err.get('message', resp.status_code)}")

        data = resp.json()
        all_results.extend(data.get("results", []))
        has_more = data.get("has_more", False)
        start_cursor = data.get("next_cursor")
        pages_fetched += 1

    return all_results


# ── Property Extractors ──────────────────────────────────────────────────────

def extract_title(prop: dict) -> str:
    parts = prop.get("title", [])
    return parts[0].get("plain_text", "") if parts else ""

def extract_multi_select(prop: dict) -> list:
    return [opt.get("name", "") for opt in prop.get("multi_select", [])]

def extract_status(prop: dict) -> str:
    status = prop.get("status")
    return status.get("name", "") if status else ""

def extract_date(prop: dict) -> str | None:
    date = prop.get("date")
    return date.get("start") if date else None

def extract_number(prop: dict) -> float | None:
    return prop.get("number")

def extract_rich_text(prop: dict) -> str:
    parts = prop.get("rich_text", [])
    return "".join(p.get("plain_text", "") for p in parts)

def extract_created_time(prop: dict) -> str | None:
    return prop.get("created_time")

def parse_page(page: dict) -> dict:
    """Extract structured fields from a Notion page object."""
    props = page.get("properties", {})
    item = {}
    for prop_name, prop_val in props.items():
        ptype = prop_val.get("type", "")
        if ptype == "title":
            item["ToDo"] = extract_title(prop_val)
        elif ptype == "multi_select":
            item[prop_name] = extract_multi_select(prop_val)
        elif ptype == "status":
            item[prop_name] = extract_status(prop_val)
        elif ptype == "date":
            item[prop_name] = extract_date(prop_val)
        elif ptype == "number":
            item[prop_name] = extract_number(prop_val)
        elif ptype == "rich_text":
            item[prop_name] = extract_rich_text(prop_val)
        elif ptype == "created_time":
            item[prop_name] = extract_created_time(prop_val)
    item["_page_id"] = page.get("id", "")
    item["_last_edited"] = page.get("last_edited_time", "")
    return item


# ── Filter Builder ───────────────────────────────────────────────────────────

def _parse_number_filter(raw: str) -> list[dict]:
    """Parse numeric filter syntax and return Notion number-filter conditions for 工時.

    支援語法：
      "8"            → equals 8
      ">=8" / ">8"   → on_or_greater_than / greater_than
      "<=8" / "<8"   → on_or_less_than / less_than
      "5:10"         → range [5, 10]
    """
    s = raw.strip()
    if not s:
        return []
    prop = "工時"
    # range
    if ":" in s and not any(s.startswith(p) for p in (">", "<")):
        lo, hi = [p.strip() for p in s.split(":", 1)]
        try:
            return [
                {"property": prop, "number": {"greater_than_or_equal_to": float(lo)}},
                {"property": prop, "number": {"less_than_or_equal_to": float(hi)}},
            ]
        except ValueError:
            return []
    try:
        if s.startswith(">="):
            return [{"property": prop, "number": {"greater_than_or_equal_to": float(s[2:])}}]
        if s.startswith("<="):
            return [{"property": prop, "number": {"less_than_or_equal_to": float(s[2:])}}]
        if s.startswith(">"):
            return [{"property": prop, "number": {"greater_than": float(s[1:])}}]
        if s.startswith("<"):
            return [{"property": prop, "number": {"less_than": float(s[1:])}}]
        return [{"property": prop, "number": {"equals": float(s)}}]
    except ValueError:
        return []


def build_notion_filter(filter_status: str | None, filter_assignee: str | None,
                        filter_project: str | None, filter_date: str | None,
                        filter_due_date: str | None,
                        filter_hours: str | None = None,
                        filter_logic: str = "and") -> dict | None:
    conditions = []
    if filter_status:
        # filter_status supports:
        #   "已完成"           → 精確匹配
        #   "not:已完成"       → 排除該狀態（用於查「所有未完成」）
        fs = filter_status.strip()
        if fs.lower().startswith("not:"):
            status_val = fs.split(":", 1)[1].strip()
            conditions.append({"property": "狀態", "status": {"does_not_equal": status_val}})
        else:
            conditions.append({"property": "狀態", "status": {"equals": fs}})
    if filter_assignee:
        conditions.append({"property": "負責人 / PM", "multi_select": {"contains": filter_assignee}})
    if filter_project:
        conditions.append({"property": "專案", "multi_select": {"contains": filter_project}})
    if filter_date:
        # filter_date supports:
        #   "today"                        → 「建立時間」欄位為今天
        #   "yyyy-mm-dd"                   → 「建立時間」欄位為指定日期（精確）
        #   "yyyy-mm-dd:yyyy-mm-dd"        → 範圍
        #   "before:yyyy-mm-dd"            → 「建立時間」早於指定日期
        #   "after:yyyy-mm-dd"             → 「建立時間」晚於/等於指定日期
        fd = filter_date.strip()
        if fd.lower() == "today":
            today = datetime.now().strftime("%Y-%m-%d")
            conditions.append({"property": "建立時間", "date": {"equals": today}})
        elif fd.lower().startswith("before:"):
            date_val = fd.split(":", 1)[1].strip()
            conditions.append({"property": "建立時間", "date": {"before": date_val}})
        elif fd.lower().startswith("after:"):
            date_val = fd.split(":", 1)[1].strip()
            conditions.append({"property": "建立時間", "date": {"on_or_after": date_val}})
        elif ":" in fd and not fd.startswith(("before", "after")):
            parts = fd.split(":", 1)
            conditions.append({"property": "建立時間", "date": {"on_or_after": parts[0].strip()}})
            conditions.append({"property": "建立時間", "date": {"on_or_before": parts[1].strip()}})
        else:
            conditions.append({"property": "建立時間", "date": {"equals": fd}})
    if filter_due_date:
        # filter_due_date supports:
        #   "yyyy-mm-dd"                   → 精確到期日
        #   "yyyy-mm-dd:yyyy-mm-dd"        → 範圍
        #   "before:yyyy-mm-dd"            → 該日之前到期
        #   "after:yyyy-mm-dd"             → 該日之後到期（含當日）
        #   "overdue"                      → 已逾期
        #   "upcoming"                     → 未來 7 天內到期
        fdd = filter_due_date.strip()
        if fdd.lower() == "overdue":
            today = datetime.now().strftime("%Y-%m-%d")
            conditions.append({"property": "到期日", "date": {"before": today}})
        elif fdd.lower() == "upcoming":
            today = datetime.now().strftime("%Y-%m-%d")
            week_later = (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d")
            conditions.append({"property": "到期日", "date": {"on_or_after": today}})
            conditions.append({"property": "到期日", "date": {"on_or_before": week_later}})
        elif fdd.lower().startswith("before:"):
            date_val = fdd.split(":", 1)[1].strip()
            conditions.append({"property": "到期日", "date": {"before": date_val}})
        elif fdd.lower().startswith("after:"):
            date_val = fdd.split(":", 1)[1].strip()
            conditions.append({"property": "到期日", "date": {"on_or_after": date_val}})
        elif ":" in fdd and not fdd.startswith(("before", "after")):
            parts = fdd.split(":", 1)
            conditions.append({"property": "到期日", "date": {"on_or_after": parts[0].strip()}})
            conditions.append({"property": "到期日", "date": {"on_or_before": parts[1].strip()}})
        else:
            conditions.append({"property": "到期日", "date": {"equals": fdd}})
    if filter_hours:
        conditions.extend(_parse_number_filter(filter_hours))
    if not conditions:
        return None
    if len(conditions) == 1:
        return conditions[0]
    logic_key = "or" if (filter_logic or "").strip().lower() == "or" else "and"
    return {logic_key: conditions}


def apply_keyword_filter(items: list, keyword: str) -> list:
    kw = keyword.lower()
    return [item for item in items if kw in item.get("ToDo", "").lower()]


# ── Notion Property Builder ──────────────────────────────────────────────────

def build_notion_properties(item: dict) -> dict:
    """Convert flat item dict → Notion API properties format."""
    props = {}

    if item.get("ToDo"):
        props["ToDo"] = {"title": [{"text": {"content": item["ToDo"]}}]}

    MULTI_SELECT_MAP = {
        "專案": "專案",
        "負責人": "負責人 / PM",
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

    # Rich text field (階段里程碑)
    milestone = item.get("階段里程碑", [])
    if isinstance(milestone, list) and milestone:
        text = "、".join(str(v) for v in milestone if v)
        if text:
            props["階段里程碑"] = {"rich_text": [{"text": {"content": text}}]}
    elif isinstance(milestone, str) and milestone:
        props["階段里程碑"] = {"rich_text": [{"text": {"content": milestone}}]}

    if item.get("狀態"):
        props["狀態"] = {"status": {"name": item["狀態"]}}

    if item.get("到期日"):
        props["到期日"] = {"date": {"start": item["到期日"]}}

    if item.get("建立時間"):
        props["建立時間"] = {"date": {"start": item["建立時間"]}}

    if item.get("工時") is not None:
        try:
            props["工時"] = {"number": float(item["工時"])}
        except (TypeError, ValueError):
            pass

    return props


# ── Config Loaders ───────────────────────────────────────────────────────────

def load_notion_schema() -> dict:
    path = CONFIG_DIR / "notion_schema.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {}

def load_source_options(schema: dict) -> list:
    source_field = schema.get("來源", {})
    options = source_field.get("options", [])
    if isinstance(options, list) and options:
        result = []
        for opt in options:
            if isinstance(opt, str):
                result.append(opt)
            elif isinstance(opt, dict) and "name" in opt:
                result.append(opt["name"])
        return result
    return ["商業模式", "外部合作", "法律法規", "會議記錄", "董事會顧問會議", "董事長交辦", "KWAY研發中心"]

def load_prompt(filename: str) -> str:
    path = PROMPTS_DIR / filename
    if path.exists():
        return path.read_text(encoding="utf-8")
    raise FileNotFoundError(f"Prompt template not found: {path}")


# ── LLM Call (for Schema Mapping) ───────────────────────────────────────────

def call_llm(prompt: str, max_tokens: int = 4096) -> str:
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
    if not text:
        return None
    try:
        return json.loads(text.strip())
    except json.JSONDecodeError:
        pass
    cleaned = re.sub(r"```json\s*", "", text)
    cleaned = re.sub(r"```\s*", "", cleaned).strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass
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


# ── Phase 3: Schema Mapper (for create_batch) ───────────────────────────────

def phase3_schema_map(cleaned_text: str, org_data: dict, language: str,
                      source_options: list, base_date_compact: str = "",
                      base_date_iso: str = "") -> list:
    """Convert cleaned text + org data → Notion JSON Array."""
    template = load_prompt("phase3_schema_mapper.txt")

    today = datetime.now().strftime("%Y-%m-%d")
    date_compact = base_date_compact or datetime.now().strftime("%Y%m%d")
    reference_date = base_date_iso or today

    _raw_dept = org_data.get("責任部門代碼", "KWAY") or "KWAY"
    dept_code = _raw_dept if re.match(r'^[A-Za-z0-9]+$', _raw_dept) else "KWAY"
    project_prefix = f"{dept_code}_{date_compact}"
    meeting_lead = (org_data.get("負責人") or ["待指派"])[0]

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
        .replace("{reference_date}", reference_date)
        .replace("{today}", today)
        .replace("{cleaned_text}", cleaned_text)
    )

    result = call_llm(prompt, max_tokens=8192)
    json_array = extract_json(result)
    if not isinstance(json_array, list):
        json_array = [json_array]

    # Hallucination guard
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


# ── Phase 4: QA Inspector (for create_batch) ────────────────────────────────

GARBAGE_WORDS = {"然後", "那個", "比較", "就是", "出來", "這樣子", "對對對"}
ALLOWED_STATUSES = {"未開始", "進行中", "完成", "已完成"}


def phase4_qa_inspect(items: list, source_options: list, date_prefix: str = "") -> tuple[list, list]:
    """Validate and clean the JSON array. Returns (clean_items, errors)."""
    errors = []
    today = datetime.now().strftime("%Y-%m-%d")
    if not date_prefix:
        date_prefix = datetime.now().strftime("%Y%m%d")
    source_set = set(source_options)

    for idx, item in enumerate(items):
        if item.get("建立時間") != today:
            item["建立時間"] = today

        todo = item.get("ToDo", "")
        if len(todo) < 10:
            errors.append({"item_index": idx, "field": "ToDo", "error_type": "TOO_SHORT",
                           "current_length": len(todo), "value": todo})
        elif len(todo) > 60:
            item["ToDo"] = todo[:50]
            errors.append({"item_index": idx, "field": "ToDo", "error_type": "TRUNCATED",
                           "original_length": len(todo)})

        for field in ["ToDo", "關鍵詞"]:
            val = item.get(field, "")
            if isinstance(val, list):
                item[field] = [v for v in val if v not in GARBAGE_WORDS]
            elif isinstance(val, str):
                for gw in GARBAGE_WORDS:
                    if gw in val:
                        errors.append({"item_index": idx, "field": field,
                                       "error_type": "GARBAGE_KEYWORD", "found": gw})

        status = item.get("狀態", "未開始")
        if status not in ALLOWED_STATUSES:
            item["狀態"] = "未開始"
            errors.append({"item_index": idx, "field": "狀態",
                           "error_type": "INVALID_STATUS", "found": status})

        source = item.get("來源", [])
        if isinstance(source, str):
            source = [source]
            item["來源"] = source
        invalid_sources = [s for s in source if s not in source_set]
        if invalid_sources:
            item["來源"] = [s for s in source if s in source_set] or ["會議記錄"]
            errors.append({"item_index": idx, "field": "來源",
                           "error_type": "INVALID_SOURCE", "found": invalid_sources,
                           "replaced_with": item["來源"]})

        if date_prefix:
            item["來源"] = [
                f"{date_prefix}_{s}" if not s.startswith(date_prefix) else s
                for s in item["來源"]
            ]

        for field in ["專案", "負責人", "執行人", "責任部門", "階段里程碑", "關鍵詞", "來源"]:
            val = item.get(field)
            if val is not None and not isinstance(val, list):
                item[field] = [val]

    return items, errors


# ── Notion Upload (Upsert) ──────────────────────────────────────────────────

def similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()


def upload_to_notion(items: list, token: str, database_id: str) -> list:
    """Upload items with Upsert logic. Returns list of result dicts."""
    headers = _headers(token)
    results = []

    # Pre-fetch existing pages for dedup
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
                for prop_name, prop_val in page.get("properties", {}).items():
                    if prop_val.get("type") == "title":
                        title_parts = prop_val.get("title", [])
                        if title_parts:
                            title_text = title_parts[0].get("plain_text", "")
                            if title_text:
                                existing_titles[title_text] = page["id"]
                        break
    except Exception:
        pass

    for item in items:
        todo_title = item.get("ToDo", "")
        properties = build_notion_properties(item)

        try:
            best_match_id = None
            best_sim = 0.0
            for existing_title, page_id in existing_titles.items():
                sim = similarity(todo_title, existing_title)
                if sim > best_sim:
                    best_sim = sim
                    best_match_id = page_id

            if best_match_id and best_sim > 0.8:
                update_resp = requests.patch(
                    f"{NOTION_API_BASE}/pages/{best_match_id}",
                    headers=headers, json={"properties": properties}, timeout=15,
                )
                if update_resp.ok:
                    results.append({**item, "_action": "updated", "_similarity": round(best_sim, 2)})
                else:
                    err = update_resp.json()
                    results.append({**item, "_action": "error", "_error": err.get("message", str(update_resp.status_code))})
            else:
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


# ═══════════════════════════════════════════════════════════════════════════════
# Actions
# ═══════════════════════════════════════════════════════════════════════════════

def action_create(token: str, db_id: str, todo_title: str, status: str | None,
                  assignee: str | None, due_date: str | None, project: str | None,
                  source: str | None, keywords: str | None) -> dict:
    """Create a single ToDo page."""
    item = {"ToDo": todo_title, "狀態": status or "未開始"}

    if assignee:
        item["負責人"] = [n.strip() for n in assignee.split(",") if n.strip()]
    if due_date:
        item["到期日"] = due_date
    if project:
        item["專案"] = [n.strip() for n in project.split(",") if n.strip()]
    if source:
        item["來源"] = [n.strip() for n in source.split(",") if n.strip()]
    if keywords:
        item["關鍵詞"] = [n.strip() for n in keywords.split(",") if n.strip()]

    item["建立時間"] = datetime.now().strftime("%Y-%m-%d")
    properties = build_notion_properties(item)

    resp = requests.post(
        f"{NOTION_API_BASE}/pages",
        headers=_headers(token),
        json={"parent": {"database_id": db_id}, "properties": properties},
        timeout=15,
    )

    if resp.ok:
        page_id = resp.json().get("id", "")
        return {"status": "success", "action": "create", "page_id": page_id,
                "message": f"已成功建立待辦項目：{todo_title}"}
    else:
        err = resp.json()
        return {"status": "error", "action": "create",
                "message": f"Notion API 錯誤：{err.get('message', resp.status_code)}"}


def action_create_batch(token: str, db_id: str, items_json: str | None,
                        cleaned_text: str | None, org_data_json: str | None,
                        language: str, meeting_date: str | None) -> dict:
    """Batch create from structured JSON or via Schema Mapping pipeline."""

    # Resolve base date
    base_date_compact = ""
    if meeting_date:
        base_date_compact = meeting_date.replace("-", "").replace("/", "")[:8]
    if not base_date_compact or len(base_date_compact) != 8:
        base_date_compact = datetime.now().strftime("%Y%m%d")
    base_date_iso = f"{base_date_compact[:4]}-{base_date_compact[4:6]}-{base_date_compact[6:8]}"

    schema = load_notion_schema()
    source_options = load_source_options(schema)

    if items_json:
        # Direct JSON input — skip Phase 3
        items = extract_json(items_json) if isinstance(items_json, str) else items_json
        if not isinstance(items, list):
            items = [items]
    elif cleaned_text and org_data_json:
        # Pipeline mode: Phase 3 Schema Mapping
        org_data = extract_json(org_data_json) if isinstance(org_data_json, str) else org_data_json
        items = phase3_schema_map(cleaned_text, org_data, language, source_options,
                                  base_date_compact, base_date_iso)
    else:
        return {"status": "error", "action": "create_batch",
                "message": "請提供 items_json 或 cleaned_text + org_data_json"}

    # Phase 4: QA
    validated_items, qa_errors = phase4_qa_inspect(items, source_options, date_prefix=base_date_compact)

    # Upload (Upsert)
    upload_results = upload_to_notion(validated_items, token, db_id)

    created = sum(1 for r in upload_results if r.get("_action") == "created")
    updated = sum(1 for r in upload_results if r.get("_action") == "updated")
    errored = sum(1 for r in upload_results if r.get("_action") == "error")

    item_summaries = []
    for r in upload_results:
        summary = {"ToDo": r.get("ToDo", ""), "負責人": r.get("負責人", []),
                   "來源": r.get("來源", []), "_action": r.get("_action", "unknown")}
        if r.get("_error"):
            summary["_error"] = r["_error"]
        item_summaries.append(summary)

    output = {"status": "success", "action": "create_batch",
              "total": len(upload_results), "created": created,
              "updated": updated, "errors": errored,
              "qa_warnings": len(qa_errors), "items": item_summaries}
    if qa_errors:
        output["qa_details"] = qa_errors[:10]
    return output


def action_list(token: str, db_id: str, filter_status: str | None,
                filter_assignee: str | None, filter_project: str | None,
                keyword: str | None, limit: int, offset: int = 0,
                filter_date: str | None = None,
                filter_due_date: str | None = None,
                filter_hours: str | None = None,
                filter_logic: str = "and") -> dict:
    """List todo items with filters. Supports offset-based pagination."""
    notion_filter = build_notion_filter(filter_status, filter_assignee, filter_project,
                                        filter_date, filter_due_date,
                                        filter_hours=filter_hours,
                                        filter_logic=filter_logic)
    pages = query_database(token, db_id, filter_obj=notion_filter)
    items = [parse_page(p) for p in pages]

    if keyword:
        items = apply_keyword_filter(items, keyword)

    total = len(items)
    items = items[offset:offset + limit]

    clean_items = []
    for item in items:
        clean = {k: v for k, v in item.items() if (not k.startswith("_") or k == "_page_id") and v is not None}
        if "_page_id" in clean:
            clean["page_id"] = clean.pop("_page_id")
        clean_items.append(clean)

    result = {"status": "success", "action": "list", "total": total,
              "returned": len(clean_items), "offset": offset, "limit": limit,
              "items": clean_items,
              "usage_hint": (
                  "後續 update/delete 指定「第 N 筆」時，必須從 items[N-1].page_id 取用 UUID，"
                  "嚴禁自行拼湊或推測 page_id。若使用者未明確指定筆數且只提供名稱，"
                  "請用 keyword 參數（系統會以子字串匹配），或從 items 中找出名稱完全相符的那筆並複製其 page_id。"
              )}
    if offset + limit < total:
        result["next_offset"] = offset + limit
        result["hint"] = f"還有 {total - offset - limit} 筆未顯示，請用 offset={offset + limit} 取得下一頁"
    return result


def action_summary(token: str, db_id: str) -> dict:
    """Generate progress summary."""
    pages = query_database(token, db_id, max_pages=5)
    items = [parse_page(p) for p in pages]

    today = datetime.now().strftime("%Y-%m-%d")
    today_dt = datetime.now()

    status_counts = {}
    overdue = []
    due_soon = []

    for item in items:
        status = item.get("狀態", "未知")
        status_counts[status] = status_counts.get(status, 0) + 1

        due_date = item.get("到期日")
        if due_date and status not in ("已完成", "完成"):
            try:
                due_dt = datetime.strptime(due_date[:10], "%Y-%m-%d")
                entry = {"ToDo": item.get("ToDo", ""), "到期日": due_date,
                         "負責人": item.get("負責人 / PM", item.get("負責人", [])),
                         "狀態": status}
                if due_dt < today_dt:
                    overdue.append(entry)
                elif due_dt <= today_dt + timedelta(days=7):
                    due_soon.append(entry)
            except ValueError:
                pass

    assignee_counts = {}
    for item in items:
        assignees = item.get("負責人 / PM", item.get("負責人", []))
        if isinstance(assignees, list):
            for a in assignees:
                if a and a != "待指派":
                    assignee_counts[a] = assignee_counts.get(a, 0) + 1

    return {"status": "success", "action": "summary", "total_items": len(items),
            "by_status": status_counts, "overdue": overdue[:20],
            "due_within_7_days": due_soon[:20], "by_assignee": assignee_counts,
            "as_of": today}


def action_update(token: str, page_id: str, status: str | None,
                  assignee: str | None, due_date: str | None,
                  project: str | None, todo_title: str | None,
                  keyword: str | None = None, db_id: str | None = None) -> dict:
    """Update specified fields on a Notion page. Supports keyword lookup if page_id is empty."""
    # Keyword lookup: find page_id by searching todo title
    if not page_id and keyword and db_id:
        items = _query_pages_by_filter(token, db_id, keyword=keyword)
        if len(items) == 0:
            return {"status": "error", "action": "update",
                    "message": f"找不到包含「{keyword}」的待辦項目"}
        if len(items) == 1:
            page_id = items[0]["_page_id"]
        else:
            candidates = [{"ToDo": it.get("ToDo", ""), "page_id": it["_page_id"],
                           "狀態": it.get("狀態", "")} for it in items[:10]]
            return {"status": "error", "action": "update",
                    "message": f"找到 {len(items)} 筆符合「{keyword}」的項目，請指定 page_id",
                    "candidates": candidates}

    if not page_id or not _is_valid_uuid(page_id):
        return {"status": "error", "action": "update", "page_id": page_id or "",
                "message": f"page_id 格式錯誤：'{page_id or ''}' 不是有效的 UUID。"
                           f"請使用 action=list 查詢結果中的 page_id（UUID 格式，如 343e791c-b3f0-8130-8b47-c0e50ee40a53），"
                           f"不可使用序號（如 1、2、3）。也可傳入 keyword 參數以名稱查找。"}
    properties = {}
    updated_fields = []

    if todo_title:
        properties["ToDo"] = {"title": [{"text": {"content": todo_title}}]}
        updated_fields.append("ToDo")
    if status:
        properties["狀態"] = {"status": {"name": status}}
        updated_fields.append("狀態")
    if assignee:
        names = [n.strip() for n in assignee.split(",") if n.strip()]
        properties["負責人 / PM"] = {"multi_select": [{"name": n} for n in names]}
        updated_fields.append("負責人")
    if due_date:
        properties["到期日"] = {"date": {"start": due_date}}
        updated_fields.append("到期日")
    if project:
        names = [n.strip() for n in project.split(",") if n.strip()]
        properties["專案"] = {"multi_select": [{"name": n} for n in names]}
        updated_fields.append("專案")

    if not properties:
        return {"status": "error", "action": "update",
                "message": "未指定任何要更新的欄位"}

    resp = requests.patch(
        f"{NOTION_API_BASE}/pages/{page_id}",
        headers=_headers(token), json={"properties": properties}, timeout=15,
    )

    if resp.ok:
        return {"status": "success", "action": "update", "page_id": page_id,
                "updated_fields": updated_fields,
                "message": f"已成功更新 {len(updated_fields)} 個欄位：{'、'.join(updated_fields)}"}
    else:
        err = resp.json()
        err_msg = err.get("message", str(resp.status_code))
        hint = ""
        if "could not find page" in err_msg.lower():
            hint = (
                "（此 UUID 在 Notion 不存在，極可能是你從對話中推測或拼湊出來的。"
                "請重新呼叫 action=list（可帶 keyword 或 filter_* 縮小範圍），"
                "從結果的 items[*].page_id 取得實際 UUID 後再更新，嚴禁自行編造 page_id。）"
            )
        return {"status": "error", "action": "update", "page_id": page_id,
                "message": f"Notion API 錯誤：{err_msg}{hint}"}


def _is_valid_uuid(value: str) -> bool:
    """Check if a string is a valid UUID format."""
    uuid_pattern = re.compile(
        r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$',
        re.IGNORECASE
    )
    return bool(uuid_pattern.match(value))


def _is_already_archived_message(message: str) -> bool:
    msg = (message or "").lower()
    return (
        "can't edit block that is archived" in msg
        or ("archived" in msg and "unarchive" in msg)
    )


def action_delete(token: str, page_id: str, keyword: str | None = None,
                  db_id: str | None = None) -> dict:
    """Archive a Notion page (soft delete). Supports keyword lookup if page_id is empty."""
    # Keyword lookup: find page_id by searching todo title
    if not page_id and keyword and db_id:
        items = _query_pages_by_filter(token, db_id, keyword=keyword)
        if len(items) == 0:
            return {"status": "error", "action": "delete",
                    "message": f"找不到包含「{keyword}」的待辦項目"}
        if len(items) == 1:
            page_id = items[0]["_page_id"]
        else:
            candidates = [{"ToDo": it.get("ToDo", ""), "page_id": it["_page_id"],
                           "狀態": it.get("狀態", "")} for it in items[:10]]
            return {"status": "error", "action": "delete",
                    "message": f"找到 {len(items)} 筆符合「{keyword}」的項目，請指定 page_id",
                    "candidates": candidates}

    if not page_id or not _is_valid_uuid(page_id):
        return {"status": "error", "action": "delete", "page_id": page_id or "",
                "message": f"page_id 格式錯誤：'{page_id or ''}' 不是有效的 UUID。"
                           f"請使用 action=list 查詢結果中的 page_id（UUID 格式，如 343e791c-b3f0-8130-8b47-c0e50ee40a53），"
                           f"不可使用序號（如 1、2、3）。也可傳入 keyword 參數以名稱查找。"}
    resp = requests.patch(
        f"{NOTION_API_BASE}/pages/{page_id}",
        headers=_headers(token), json={"archived": True}, timeout=15,
    )

    if resp.ok:
        return {"status": "success", "action": "delete", "page_id": page_id,
                "message": "已成功封存該待辦項目（可在 Notion 垃圾桶中還原）"}
    else:
        err = resp.json()
        err_msg = err.get("message", str(resp.status_code))
        if _is_already_archived_message(err_msg):
            return {"status": "success", "action": "delete", "page_id": page_id,
                    "already_archived": True,
                    "message": "Item is already archived; treated as successful delete."}
        hint = ""
        if "could not find page" in err_msg.lower():
            hint = (
                "（此 UUID 在 Notion 不存在，極可能是你從對話中推測或拼湊出來的。"
                "請重新呼叫 action=list（可帶 keyword 或 filter_* 縮小範圍），"
                "從結果的 items[*].page_id 取得實際 UUID 後再刪除，嚴禁自行編造 page_id。）"
            )
        return {"status": "error", "action": "delete", "page_id": page_id,
                "message": f"Notion API 錯誤：{err_msg}{hint}"}


# ── Batch Delete / Batch Update ─────────────────────────────────────────────

def _query_pages_by_filter(token: str, db_id: str,
                           filter_status: str | None = None,
                           filter_assignee: str | None = None,
                           filter_project: str | None = None,
                           filter_date: str | None = None,
                           filter_due_date: str | None = None,
                           keyword: str | None = None,
                           filter_hours: str | None = None,
                           filter_logic: str = "and") -> list:
    """Query pages using filters and return parsed items with page IDs."""
    notion_filter = build_notion_filter(filter_status, filter_assignee,
                                        filter_project, filter_date, filter_due_date,
                                        filter_hours=filter_hours,
                                        filter_logic=filter_logic)
    pages = query_database(token, db_id, filter_obj=notion_filter, max_pages=5)
    items = [parse_page(p) for p in pages]
    if keyword:
        items = apply_keyword_filter(items, keyword)
    return items


def _normalize_page_ids(page_ids: list | None) -> list[str]:
    if not page_ids:
        return []
    normalized = []
    for pid in page_ids:
        if isinstance(pid, str):
            clean = pid.strip()
            if clean:
                normalized.append(clean)
    return normalized


def _parse_page_ids_arg(page_ids_raw: str | None) -> tuple[list[str] | None, str | None]:
    if not page_ids_raw:
        return None, None
    try:
        parsed = json.loads(page_ids_raw)
    except json.JSONDecodeError:
        return None, "page_ids 參數格式錯誤：必須是 JSON 陣列，例如 [\"uuid-1\", \"uuid-2\"]"

    if not isinstance(parsed, list):
        return None, "page_ids 參數格式錯誤：必須是 JSON 陣列"

    normalized = _normalize_page_ids(parsed)
    if not normalized:
        return None, "page_ids 參數不可為空陣列"

    return normalized, None


def action_delete_batch(token: str, db_id: str,
                        page_ids: list[str] | None = None,
                        filter_status: str | None = None,
                        filter_assignee: str | None = None,
                        filter_project: str | None = None,
                        filter_date: str | None = None,
                        filter_due_date: str | None = None,
                        keyword: str | None = None,
                        filter_hours: str | None = None,
                        filter_logic: str = "and",
                        confirm: bool = False) -> dict:
    """Batch archive pages by page_ids or filter conditions.

    Two-phase flow for filter-based delete:
      1. 第一次呼叫（只帶 filter）→ 回傳 preview，列出命中的 page_ids，不執行
      2. 第二次呼叫（帶 page_ids，或 confirm=true + 同樣 filter）→ 實際執行
    直接帶 page_ids 視為已確認，立即執行。
    """
    headers = _headers(token)
    page_ids = _normalize_page_ids(page_ids)

    has_filter = any([filter_status, filter_assignee, filter_project, filter_date,
                      filter_due_date, keyword, filter_hours])

    # Filter-based flow
    if not page_ids:
        if not has_filter:
            return {
                "status": "error",
                "action": "delete_batch",
                "message": "delete_batch 必須提供 page_ids 或至少一個 filter_* / keyword 條件。",
            }

        items = _query_pages_by_filter(token, db_id,
                                       filter_status=filter_status,
                                       filter_assignee=filter_assignee,
                                       filter_project=filter_project,
                                       filter_date=filter_date,
                                       filter_due_date=filter_due_date,
                                       keyword=keyword,
                                       filter_hours=filter_hours,
                                       filter_logic=filter_logic)
        if not items:
            return {"status": "success", "action": "delete_batch",
                    "total": 0, "archived": 0, "errors": 0,
                    "message": "查無符合條件的待辦項目"}

        resolved_ids = [it["_page_id"] for it in items]

        if not confirm:
            # Preview mode: list what would be deleted, do not execute.
            preview = [{"ToDo": it.get("ToDo", ""),
                        "到期日": it.get("到期日"),
                        "狀態": it.get("狀態", ""),
                        "page_id": it["_page_id"]} for it in items[:MAX_SAFE_BATCH_DELETE]]
            return {
                "status": "preview",
                "action": "delete_batch",
                "total": len(items),
                "message": f"偵測到 {len(items)} 筆符合條件的待辦項目。確認要刪除請再次呼叫並帶 confirm=true，或帶上回傳的 page_ids。",
                "candidates": preview,
                "page_ids": resolved_ids[:MAX_SAFE_BATCH_DELETE],
                "confirm_hint": "下一步呼叫請帶 confirm=true（保留相同 filter 條件）或直接傳 page_ids 參數執行。",
                "truncated": len(items) > MAX_SAFE_BATCH_DELETE,
                "max_allowed": MAX_SAFE_BATCH_DELETE,
            }

        # confirm=true: execute using filter-resolved ids
        page_ids = resolved_ids

    if len(page_ids) > MAX_SAFE_BATCH_DELETE:
        return {
            "status": "error",
            "action": "delete_batch",
            "message": f"單次 delete_batch 最多允許 {MAX_SAFE_BATCH_DELETE} 筆，請分批執行。",
            "requested": len(page_ids),
            "max_allowed": MAX_SAFE_BATCH_DELETE,
        }

    results = []
    for i, pid in enumerate(page_ids):
        if not _is_valid_uuid(pid):
            results.append({"page_id": pid, "_action": "error",
                           "_error": "無效的 UUID 格式"})
            continue
        try:
            resp = requests.patch(
                f"{NOTION_API_BASE}/pages/{pid}",
                headers=headers, json={"archived": True}, timeout=15,
            )
            if resp.ok:
                results.append({"page_id": pid, "_action": "archived"})
            else:
                err = resp.json()
                err_msg = err.get("message", str(resp.status_code))
                if _is_already_archived_message(err_msg):
                    results.append({"page_id": pid, "_action": "archived", "_already_archived": True})
                else:
                    results.append({"page_id": pid, "_action": "error", "_error": err_msg})
        except Exception as e:
            err_msg = str(e)
            if _is_already_archived_message(err_msg):
                results.append({"page_id": pid, "_action": "archived", "_already_archived": True})
            else:
                results.append({"page_id": pid, "_action": "error", "_error": err_msg})

        # Rate limit: Notion allows ~3 req/s
        if (i + 1) % 3 == 0:
            time.sleep(1.0)

    archived = sum(1 for r in results if r.get("_action") == "archived")
    errored = sum(1 for r in results if r.get("_action") == "error")

    return {"status": "success", "action": "delete_batch",
            "total": len(results), "archived": archived, "errors": errored,
            "message": f"已封存 {archived} 筆待辦項目（{errored} 筆失敗）",
            "items": results}


def action_update_batch(token: str, db_id: str,
                        page_ids: list[str] | None = None,
                        filter_status: str | None = None,
                        filter_assignee: str | None = None,
                        filter_project: str | None = None,
                        filter_date: str | None = None,
                        filter_due_date: str | None = None,
                        keyword: str | None = None,
                        set_status: str | None = None,
                        set_assignee: str | None = None,
                        set_due_date: str | None = None,
                        set_project: str | None = None,
                        filter_hours: str | None = None,
                        filter_logic: str = "and") -> dict:
    """Batch update pages by page_ids or filter conditions."""
    headers = _headers(token)

    # Build the properties to set
    properties = {}
    updated_fields = []
    if set_status:
        properties["狀態"] = {"status": {"name": set_status}}
        updated_fields.append("狀態")
    if set_assignee:
        names = [n.strip() for n in set_assignee.split(",") if n.strip()]
        properties["負責人 / PM"] = {"multi_select": [{"name": n} for n in names]}
        updated_fields.append("負責人")
    if set_due_date:
        properties["到期日"] = {"date": {"start": set_due_date}}
        updated_fields.append("到期日")
    if set_project:
        names = [n.strip() for n in set_project.split(",") if n.strip()]
        properties["專案"] = {"multi_select": [{"name": n} for n in names]}
        updated_fields.append("專案")

    if not properties:
        return {"status": "error", "action": "update_batch",
                "message": "未指定任何要更新的欄位（set_status / set_assignee / set_due_date / set_project）"}

    # If no page_ids provided, query by filter
    if not page_ids:
        items = _query_pages_by_filter(token, db_id,
                                       filter_status=filter_status,
                                       filter_assignee=filter_assignee,
                                       filter_project=filter_project,
                                       filter_date=filter_date,
                                       filter_due_date=filter_due_date,
                                       keyword=keyword,
                                       filter_hours=filter_hours,
                                       filter_logic=filter_logic)
        if not items:
            return {"status": "success", "action": "update_batch",
                    "total": 0, "updated": 0, "errors": 0,
                    "message": "查無符合條件的待辦項目"}
        page_ids = [item["_page_id"] for item in items]

    results = []
    for i, pid in enumerate(page_ids):
        if not _is_valid_uuid(pid):
            results.append({"page_id": pid, "_action": "error",
                           "_error": "無效的 UUID 格式"})
            continue
        try:
            resp = requests.patch(
                f"{NOTION_API_BASE}/pages/{pid}",
                headers=headers, json={"properties": properties}, timeout=15,
            )
            if resp.ok:
                results.append({"page_id": pid, "_action": "updated"})
            else:
                err = resp.json()
                results.append({"page_id": pid, "_action": "error",
                               "_error": err.get("message", str(resp.status_code))})
        except Exception as e:
            results.append({"page_id": pid, "_action": "error", "_error": str(e)})

        # Rate limit: Notion allows ~3 req/s
        if (i + 1) % 3 == 0:
            time.sleep(1.0)

    updated = sum(1 for r in results if r.get("_action") == "updated")
    errored = sum(1 for r in results if r.get("_action") == "error")

    return {"status": "success", "action": "update_batch",
            "total": len(results), "updated": updated, "errors": errored,
            "updated_fields": updated_fields,
            "message": f"已更新 {updated} 筆待辦項目的 {'、'.join(updated_fields)}（{errored} 筆失敗）",
            "items": results}


# ── Main Entry Point ─────────────────────────────────────────────────────────

def main():
    action = os.getenv("SKILL_PARAM_ACTION", "").strip().lower()

    # Credentials
    token = os.getenv("NOTION_TOKEN", "")
    db_id = os.getenv("NOTION_DATABASE_ID", "")

    if not token:
        print(json.dumps({"status": "error", "message": "缺少 NOTION_TOKEN，請在 .env 中配置"}, ensure_ascii=False))
        return

    db_id_actions = ("create", "create_batch", "list", "summary",
                      "delete_batch", "update_batch")
    if action in db_id_actions and not db_id:
        print(json.dumps({"status": "error", "message": "缺少 NOTION_DATABASE_ID，請在 .env 中配置"}, ensure_ascii=False))
        return

    try:
        if action == "create":
            todo_title = os.getenv("SKILL_PARAM_TODO_TITLE", "").strip()
            if not todo_title:
                print(json.dumps({"status": "error", "action": "create",
                                  "message": "缺少 todo_title 參數"}, ensure_ascii=False))
                return
            def _c_resolve(primary: str, *aliases: str) -> str | None:
                val = os.getenv(f"SKILL_PARAM_{primary}", "").strip()
                if val:
                    return val
                for a in aliases:
                    v = os.getenv(f"SKILL_PARAM_{a}", "").strip()
                    if v:
                        return v
                return None

            result = action_create(
                token, db_id, todo_title,
                status=_c_resolve("STATUS", "SET_STATUS", "FILTER_STATUS"),
                assignee=_c_resolve("ASSIGNEE", "SET_ASSIGNEE", "FILTER_ASSIGNEE"),
                due_date=_c_resolve("DUE_DATE", "SET_DUE_DATE", "FILTER_DUE_DATE"),
                project=_c_resolve("PROJECT", "SET_PROJECT", "FILTER_PROJECT"),
                source=os.getenv("SKILL_PARAM_SOURCE", "").strip() or None,
                keywords=os.getenv("SKILL_PARAM_KEYWORDS", "").strip() or None,
            )

        elif action == "create_batch":
            result = action_create_batch(
                token, db_id,
                items_json=os.getenv("SKILL_PARAM_ITEMS_JSON", "").strip() or None,
                cleaned_text=os.getenv("SKILL_PARAM_CLEANED_TEXT", "").strip() or None,
                org_data_json=os.getenv("SKILL_PARAM_ORG_DATA_JSON", "").strip() or None,
                language=os.getenv("SKILL_PARAM_LANGUAGE", "繁體中文"),
                meeting_date=os.getenv("SKILL_PARAM_MEETING_DATE", "").strip() or None,
            )

        elif action == "list":
            limit = int(os.getenv("SKILL_PARAM_LIMIT", "20"))
            limit = max(1, min(limit, 100))
            offset = int(os.getenv("SKILL_PARAM_OFFSET", "0"))
            offset = max(0, offset)
            result = action_list(
                token, db_id,
                filter_status=os.getenv("SKILL_PARAM_FILTER_STATUS", "").strip() or None,
                filter_assignee=os.getenv("SKILL_PARAM_FILTER_ASSIGNEE", "").strip() or None,
                filter_project=os.getenv("SKILL_PARAM_FILTER_PROJECT", "").strip() or None,
                keyword=os.getenv("SKILL_PARAM_KEYWORD", "").strip() or None,
                limit=limit,
                offset=offset,
                filter_date=os.getenv("SKILL_PARAM_FILTER_DATE", "").strip() or None,
                filter_due_date=os.getenv("SKILL_PARAM_FILTER_DUE_DATE", "").strip() or None,
                filter_hours=os.getenv("SKILL_PARAM_FILTER_HOURS", "").strip() or None,
                filter_logic=os.getenv("SKILL_PARAM_FILTER_LOGIC", "and").strip() or "and",
            )

        elif action == "summary":
            result = action_summary(token, db_id)

        elif action == "update":
            page_id = os.getenv("SKILL_PARAM_PAGE_ID", "").strip()
            keyword = os.getenv("SKILL_PARAM_KEYWORD", "").strip() or None
            if not page_id and not keyword:
                print(json.dumps({"status": "error", "action": "update",
                                  "message": "請提供 page_id 或 keyword 參數"}, ensure_ascii=False))
                return
            # Alias fallback: LLM 常誤用 filter_* / set_* 前綴於單筆 update。
            # 將其視為直接欄位值以提高容錯（僅當對應直接參數為空時才接手）。
            def _resolve(primary: str, *aliases: str) -> str | None:
                val = os.getenv(f"SKILL_PARAM_{primary}", "").strip()
                if val:
                    return val
                for a in aliases:
                    v = os.getenv(f"SKILL_PARAM_{a}", "").strip()
                    if v:
                        return v
                return None

            result = action_update(
                token, page_id or "",
                status=_resolve("STATUS", "SET_STATUS", "FILTER_STATUS"),
                assignee=_resolve("ASSIGNEE", "SET_ASSIGNEE", "FILTER_ASSIGNEE"),
                due_date=_resolve("DUE_DATE", "SET_DUE_DATE", "FILTER_DUE_DATE"),
                project=_resolve("PROJECT", "SET_PROJECT", "FILTER_PROJECT"),
                todo_title=os.getenv("SKILL_PARAM_TODO_TITLE", "").strip() or None,
                keyword=keyword,
                db_id=db_id,
            )

        elif action == "delete":
            page_id = os.getenv("SKILL_PARAM_PAGE_ID", "").strip()
            keyword = os.getenv("SKILL_PARAM_KEYWORD", "").strip() or None
            if not page_id and not keyword:
                print(json.dumps({"status": "error", "action": "delete",
                                  "message": "請提供 page_id 或 keyword 參數"}, ensure_ascii=False))
                return
            result = action_delete(token, page_id or "", keyword=keyword, db_id=db_id)

        elif action == "delete_batch":
            page_ids_raw = os.getenv("SKILL_PARAM_PAGE_IDS", "").strip()
            page_ids, parse_error = _parse_page_ids_arg(page_ids_raw)
            if parse_error:
                print(json.dumps({"status": "error", "action": "delete_batch", "message": parse_error}, ensure_ascii=False))
                return
            confirm_raw = os.getenv("SKILL_PARAM_CONFIRM", "").strip().lower()
            confirm_flag = confirm_raw in ("true", "1", "yes", "y")
            result = action_delete_batch(
                token, db_id, page_ids,
                filter_status=os.getenv("SKILL_PARAM_FILTER_STATUS", "").strip() or None,
                filter_assignee=os.getenv("SKILL_PARAM_FILTER_ASSIGNEE", "").strip() or None,
                filter_project=os.getenv("SKILL_PARAM_FILTER_PROJECT", "").strip() or None,
                filter_date=os.getenv("SKILL_PARAM_FILTER_DATE", "").strip() or None,
                filter_due_date=os.getenv("SKILL_PARAM_FILTER_DUE_DATE", "").strip() or None,
                keyword=os.getenv("SKILL_PARAM_KEYWORD", "").strip() or None,
                filter_hours=os.getenv("SKILL_PARAM_FILTER_HOURS", "").strip() or None,
                filter_logic=os.getenv("SKILL_PARAM_FILTER_LOGIC", "and").strip() or "and",
                confirm=confirm_flag,
            )

        elif action == "update_batch":
            page_ids_raw = os.getenv("SKILL_PARAM_PAGE_IDS", "").strip()
            page_ids, parse_error = _parse_page_ids_arg(page_ids_raw)
            if parse_error:
                print(json.dumps({"status": "error", "action": "update_batch", "message": parse_error}, ensure_ascii=False))
                return
            result = action_update_batch(
                token, db_id, page_ids,
                filter_status=os.getenv("SKILL_PARAM_FILTER_STATUS", "").strip() or None,
                filter_assignee=os.getenv("SKILL_PARAM_FILTER_ASSIGNEE", "").strip() or None,
                filter_project=os.getenv("SKILL_PARAM_FILTER_PROJECT", "").strip() or None,
                filter_date=os.getenv("SKILL_PARAM_FILTER_DATE", "").strip() or None,
                filter_due_date=os.getenv("SKILL_PARAM_FILTER_DUE_DATE", "").strip() or None,
                keyword=os.getenv("SKILL_PARAM_KEYWORD", "").strip() or None,
                filter_hours=os.getenv("SKILL_PARAM_FILTER_HOURS", "").strip() or None,
                filter_logic=os.getenv("SKILL_PARAM_FILTER_LOGIC", "and").strip() or "and",
                set_status=os.getenv("SKILL_PARAM_SET_STATUS", "").strip() or None,
                set_assignee=os.getenv("SKILL_PARAM_SET_ASSIGNEE", "").strip() or None,
                set_due_date=os.getenv("SKILL_PARAM_SET_DUE_DATE", "").strip() or None,
                set_project=os.getenv("SKILL_PARAM_SET_PROJECT", "").strip() or None,
            )

        else:
            result = {"status": "error",
                      "message": f"不支援的動作：{action}，請使用 create/create_batch/list/summary/update/update_batch/delete/delete_batch"}

        print(json.dumps(result, ensure_ascii=False))

    except Exception:
        print(json.dumps({"status": "error",
                          "message": f"執行失敗：{traceback.format_exc()}"}, ensure_ascii=False))


if __name__ == "__main__":
    main()
