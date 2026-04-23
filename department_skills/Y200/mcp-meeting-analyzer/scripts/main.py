"""
mcp-meeting-analyzer — 會議逐字稿結構化分析

2-Phase AI Pipeline:
  Phase 1: Sanitizer   (文本清洗 → 去噪 + 語意重組 + 翻譯)
  Phase 2: Org Parser  (人員歸戶 → 人名識別 + 部門映射 + 角色區分)

輸出結構化 JSON，不綁定任何外部系統。
"""

import os
import sys
import json
import re
import csv
import traceback
from pathlib import Path


# ── Configuration ────────────────────────────────────────────────────────────

SKILL_DIR = Path(__file__).resolve().parent.parent
CONFIG_DIR = SKILL_DIR / "config"
PROMPTS_DIR = SKILL_DIR / "prompts"

# LLM model for Phase 1-2
LLM_MODEL = os.getenv("MEETING_LLM_MODEL", "gpt-4.1-mini")


# ── Helper: LLM Call ─────────────────────────────────────────────────────────

# Running totals for _usage reporting. Aggregated across all LLM calls this
# invocation makes (Phase 1 Sanitizer + Phase 2 Org Parser), printed to stdout
# at the end so WorkflowExecutor can fold the real spend into the admin
# Dashboard analytics pipeline.
_USAGE_TOTAL = {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}


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
    # Accumulate token usage across every call made this invocation.
    # Contract: top-level _usage in stdout JSON (see Agent_skills/README.md).
    try:
        u = response.usage
        if u is not None:
            _USAGE_TOTAL["input_tokens"]  += getattr(u, "prompt_tokens", 0) or 0
            _USAGE_TOTAL["output_tokens"] += getattr(u, "completion_tokens", 0) or 0
            _USAGE_TOTAL["total_tokens"]  += getattr(u, "total_tokens", 0) or 0
    except Exception:
        pass
    return response.choices[0].message.content.strip()


def extract_json(text: str):
    """Extract JSON from text that may contain markdown fences or filler."""
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


# ── Config Loaders ───────────────────────────────────────────────────────────

def load_department_list() -> str:
    path = CONFIG_DIR / "department_list.txt"
    if path.exists():
        return path.read_text(encoding="utf-8")
    return "Y200 研發中心-開發處\nT200 (一)產品開發一處\nC130 資訊處"


def load_employee_names() -> set:
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

            name_cols = []
            for i, col in enumerate(header):
                col_lower = col.strip().lower()
                if any(kw in col_lower for kw in ["name", "姓名", "名前", "名字"]):
                    name_cols.append(i)

            if not name_cols:
                name_cols = [0, 1] if len(header) > 1 else [0]

            for row in reader:
                for col_idx in name_cols:
                    if col_idx < len(row) and row[col_idx].strip():
                        names.add(row[col_idx].strip())
    except Exception:
        pass

    return names


def load_prompt(filename: str) -> str:
    path = PROMPTS_DIR / filename
    if path.exists():
        return path.read_text(encoding="utf-8")
    raise FileNotFoundError(f"Prompt template not found: {path}")


# ── Phase 1: Sanitizer ──────────────────────────────────────────────────────

def phase1_sanitize(transcript: str, language: str) -> str:
    """Clean raw transcript: de-noise, rephrase, translate."""
    template = load_prompt("phase1_sanitizer.txt")
    prompt = template.replace("{language}", language).replace("{transcript}", transcript)
    return call_llm(prompt, max_tokens=4096)


# ── Phase 2: Org Parser ─────────────────────────────────────────────────────

def phase2_org_parse(cleaned_text: str, department_code: str | None,
                     employee_names: set, department_list: str) -> dict:
    """Identify people, departments, and roles."""
    template = load_prompt("phase2_org_parser.txt")

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

    # Hallucination guard
    if employee_names:
        for field in ["負責人", "識別人員", "執行人"]:
            if isinstance(org_data.get(field), list):
                valid = [n for n in org_data[field] if n == "待指派" or n in employee_names]
                if field == "負責人":
                    org_data[field] = valid if valid else ["待指派"]
                else:
                    org_data[field] = valid

    if department_code:
        org_data["責任部門代碼"] = department_code

    return org_data


# ── Main Entry Point ─────────────────────────────────────────────────────────

def main():
    transcript = os.getenv("SKILL_PARAM_TRANSCRIPT", "")
    language = os.getenv("SKILL_PARAM_LANGUAGE", "繁體中文")
    department_code = os.getenv("SKILL_PARAM_DEPARTMENT_CODE", "") or None

    if not transcript:
        print(json.dumps({
            "status": "error",
            "message": "未提供會議逐字稿內容 (transcript 參數為空)"
        }, ensure_ascii=False))
        return

    try:
        # Load reference data
        department_list = load_department_list()
        employee_names = load_employee_names()

        # Phase 1: Sanitizer
        cleaned_text = phase1_sanitize(transcript, language)

        # Phase 2: Org Parser
        org_data = phase2_org_parse(cleaned_text, department_code,
                                    employee_names, department_list)

        output = {
            "status": "success",
            "cleaned_text": cleaned_text,
            "org_data": org_data,
            "metadata": {
                "language": language,
                "department_code": department_code or org_data.get("責任部門代碼", ""),
            },
            "_usage": {
                "model": LLM_MODEL,
                "input_tokens":  _USAGE_TOTAL["input_tokens"],
                "output_tokens": _USAGE_TOTAL["output_tokens"],
                "total_tokens":  _USAGE_TOTAL["total_tokens"],
                "skill_total_tokens": _USAGE_TOTAL["total_tokens"],
            },
        }

        print(json.dumps(output, ensure_ascii=False))

    except Exception:
        # Even on failure, surface any partial usage already consumed so
        # the admin dashboard doesn't under-report cost on pipelines that
        # crash mid-way through Phase 2.
        print(json.dumps({
            "status": "error",
            "message": f"Pipeline 執行失敗：{traceback.format_exc()}",
            "_usage": {
                "model": LLM_MODEL,
                "input_tokens":  _USAGE_TOTAL["input_tokens"],
                "output_tokens": _USAGE_TOTAL["output_tokens"],
                "total_tokens":  _USAGE_TOTAL["total_tokens"],
                "skill_total_tokens": _USAGE_TOTAL["total_tokens"],
            },
        }, ensure_ascii=False))


if __name__ == "__main__":
    main()
