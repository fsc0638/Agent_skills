"""mcp-text-summarizer — Long-text → N structured summary items.

Contract (see ../SKILL.md):
  env SKILL_PARAM_TEXT       : raw input text (multiple articles / transcript / ...)
  env SKILL_PARAM_COUNT      : number of summary items to produce (default 5)
  env SKILL_PARAM_MIN_CHARS  : minimum chars per item (default 100)
  env SKILL_PARAM_MAX_CHARS  : maximum chars per item (default 500)
  env SKILL_PARAM_STYLE      : news-brief | bullet | narrative (default news-brief)
  env SKILL_PARAM_FOCUS      : optional focus topic to filter content
  env SKILL_PARAM_LANGUAGE   : output language (default 繁體中文)

Output JSON:
  { status, count, style, items: [ {index, headline, summary, source}, ... ],
    _usage: {...} }
"""

import json
import os
import re
import sys
import traceback


# ── Token usage accumulator (per Agent_skills/README.md _usage contract) ──
_USAGE_TOTAL = {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}
_MODEL_USED = ""


def _get_int(env: str, default: int, lo: int, hi: int) -> int:
    try:
        v = int(os.getenv(env, "").strip() or default)
    except ValueError:
        v = default
    return max(lo, min(hi, v))


def _build_prompt(text: str, count: int, min_chars: int, max_chars: int,
                  style: str, focus: str, language: str) -> str:
    """Compose the single-shot LLM prompt that produces structured JSON."""
    focus_line = f"\n【重點主題】{focus}\n（只選跟此主題相關的內容，無關主題直接跳過）" if focus else ""
    style_brief = {
        "news-brief": (
            "每項包含 headline（10-25 字的標題）+ summary（核心重點）+ source（來源網站）。"
            "summary 要自成段落，讀者不看原文就能理解。"
        ),
        "bullet": (
            "每項為單一重點句 / 短段落，無標題。適合純條列式呈現。"
            "headline 欄位可填空字串。"
        ),
        "narrative": (
            "每項為一段敘事文字。headline 為該段主題詞。"
            "適合連貫閱讀。"
        ),
    }.get(style, "每項包含 headline + summary + source。")

    return f"""# 任務
將以下原始文本濃縮為 **{count} 則**結構化摘要，輸出純 JSON。

# 規格
- 數量：剛好 {count} 則（不多不少；原文不足寧可少也不要重複 / 編造）
- 每則 summary 字數：{min_chars} ~ {max_chars} 字元（以中文字數計）
- 輸出語言：{language}
- 風格：{style} — {style_brief}
- 保留關鍵量化資訊：數字、日期、機構名稱、人名
- 過濾雜訊：網頁導航列、廣告、天氣、登入提示、「為您推薦」「追蹤中」這類 UI 文字
- 不要加入原文沒有的評論 / 意見 / 推測{focus_line}

# 輸出格式（必須嚴格 JSON，不要 code fence，不要開場白）
{{
  "items": [
    {{"headline": "...", "summary": "... 字元數在區間內 ...", "source": "來源網站名或 URL"}},
    ... 共 {count} 筆 ...
  ]
}}

# 原始文本（可能含多篇 / 多段）
---
{text}
---"""


def _call_openai(prompt: str) -> tuple[str, dict]:
    """Single LLM call. Returns (content_str, usage_dict)."""
    global _MODEL_USED
    from openai import OpenAI
    api_key = os.environ.get("OPENAI_API_KEY", "")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY 未設定")

    model = os.getenv("TEXT_SUMMARIZER_MODEL") or os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    _MODEL_USED = model

    client = OpenAI(api_key=api_key)
    resp = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": "你是專業的內容摘要編輯，嚴格遵守字數與數量規格，只輸出純 JSON。"},
            {"role": "user",   "content": prompt},
        ],
        temperature=0.3,
        response_format={"type": "json_object"},
    )
    content = resp.choices[0].message.content or ""
    u = resp.usage
    usage = {
        "input_tokens":  getattr(u, "prompt_tokens", 0) or 0,
        "output_tokens": getattr(u, "completion_tokens", 0) or 0,
        "total_tokens":  getattr(u, "total_tokens", 0) or 0,
    }
    for k in ("input_tokens", "output_tokens", "total_tokens"):
        _USAGE_TOTAL[k] += usage[k]
    return content, usage


def _parse_items(raw: str) -> list:
    """Extract the items list from the LLM's JSON output."""
    # Strip possible code fences
    s = raw.strip()
    s = re.sub(r"^```(?:json)?\s*", "", s)
    s = re.sub(r"\s*```\s*$", "", s)
    try:
        d = json.loads(s)
    except json.JSONDecodeError:
        # Try to find the JSON object in the response
        m = re.search(r"\{.*\}", s, flags=re.DOTALL)
        if not m:
            raise
        d = json.loads(m.group(0))
    items = d.get("items") if isinstance(d, dict) else None
    if not isinstance(items, list):
        raise ValueError("LLM 回傳沒有 items 陣列")
    return items


def _clamp_items(items: list, count: int, min_chars: int, max_chars: int) -> list:
    """Enforce count + length bounds client-side (LLM sometimes disobeys)."""
    out = []
    for i, it in enumerate(items[:count], start=1):
        if not isinstance(it, dict):
            continue
        summary = (it.get("summary") or "").strip()
        # Hard cap max; we don't pad short ones (signals weak source material)
        if len(summary) > max_chars:
            summary = summary[: max_chars - 1].rstrip() + "…"
        out.append({
            "index":    i,
            "headline": (it.get("headline") or "").strip()[:120],
            "summary":  summary,
            "source":   (it.get("source") or "").strip()[:200],
            "chars":    len(summary),
            "meets_min": len(summary) >= min_chars,
        })
    return out


def main():
    text      = os.getenv("SKILL_PARAM_TEXT", "")
    count     = _get_int("SKILL_PARAM_COUNT", 5, 1, 30)
    min_chars = _get_int("SKILL_PARAM_MIN_CHARS", 100, 30, 2000)
    max_chars = _get_int("SKILL_PARAM_MAX_CHARS", 500, 50, 3000)
    style     = (os.getenv("SKILL_PARAM_STYLE", "") or "news-brief").strip().lower()
    if style not in ("news-brief", "bullet", "narrative"):
        style = "news-brief"
    focus     = os.getenv("SKILL_PARAM_FOCUS", "").strip()
    language  = os.getenv("SKILL_PARAM_LANGUAGE", "").strip() or "繁體中文"

    if not text.strip():
        print(json.dumps({
            "status": "error",
            "message": "未提供待摘要的文本 (text 參數為空)",
            "_usage": {"model": "", "input_tokens": 0, "output_tokens": 0,
                       "total_tokens": 0, "skill_total_tokens": 0},
        }, ensure_ascii=False))
        return

    # Clamp max_chars to be >= min_chars (common LLM-generated param mistake)
    if max_chars < min_chars:
        max_chars = min_chars + 200

    # Cap raw text to 40K chars so a single LLM call fits comfortably; for
    # longer inputs the generator workflow should chunk before calling us.
    text_capped = text[:40000]
    if len(text) > 40000:
        text_capped += "\n\n[⚠️ 輸入過長，已截斷至前 40000 字元]"

    try:
        prompt = _build_prompt(text_capped, count, min_chars, max_chars, style, focus, language)
        raw, _ = _call_openai(prompt)
        items = _parse_items(raw)
        items = _clamp_items(items, count, min_chars, max_chars)

        result = {
            "status": "success",
            "count": len(items),
            "style": style,
            "items": items,
            "_usage": {
                "model": _MODEL_USED,
                "input_tokens":  _USAGE_TOTAL["input_tokens"],
                "output_tokens": _USAGE_TOTAL["output_tokens"],
                "total_tokens":  _USAGE_TOTAL["total_tokens"],
                "skill_total_tokens": _USAGE_TOTAL["total_tokens"],
            },
        }
        # Also provide a pre-formatted markdown version so downstream blocks
        # (e.g. python-executor creating a PDF) can use it directly without
        # having to re-iterate items.
        result["output"] = _format_markdown(items, style)
        print(json.dumps(result, ensure_ascii=False))

    except Exception as e:
        print(json.dumps({
            "status": "error",
            "message": f"摘要失敗：{e}",
            "detail":  traceback.format_exc()[:500],
            "_usage": {
                "model": _MODEL_USED,
                "input_tokens":  _USAGE_TOTAL["input_tokens"],
                "output_tokens": _USAGE_TOTAL["output_tokens"],
                "total_tokens":  _USAGE_TOTAL["total_tokens"],
                "skill_total_tokens": _USAGE_TOTAL["total_tokens"],
            },
        }, ensure_ascii=False))


def _format_markdown(items: list, style: str) -> str:
    """Flatten items into a readable markdown string for downstream PDF/email."""
    lines = []
    for it in items:
        idx  = it["index"]
        head = it.get("headline", "")
        summ = it.get("summary", "")
        src  = it.get("source", "")
        if style == "bullet":
            lines.append(f"{idx}. {summ}")
        elif style == "narrative":
            lines.append(f"### {head}\n\n{summ}")
        else:  # news-brief
            src_part = f"\n> 來源：{src}" if src else ""
            lines.append(f"### {idx}. {head}\n\n{summ}{src_part}")
    return "\n\n".join(lines)


if __name__ == "__main__":
    main()
