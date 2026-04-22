"""
mcp-schedule-manager — Manages scheduled push tasks for LINE Bot.
Called by LLM when user expresses scheduling intent.
Reads/writes workspace/schedules/{session_id}.json.
"""

import json
import os
import sys
import uuid
from datetime import datetime, timedelta
from pathlib import Path


def _resolve_project_root() -> Path:
    skills_home = os.getenv("SKILLS_HOME", "")
    if skills_home:
        return Path(skills_home).resolve().parent.parent
    return Path(__file__).resolve().parents[4]


def _parse_cron(cron_str: str) -> dict:
    """Parse cron string into structured dict."""
    import re as _re
    cron_str = cron_str.strip()

    # Interval: 'every +10m' / 'every 10m' / 'every 10 min'
    _iv = _re.search(r'every\s*\+?(\d+)\s*(?:m|min)', cron_str)
    if _iv:
        return {"interval_minutes": int(_iv.group(1))}

    # Full cron with interval in minute field: '*/10 * * * *'
    _iparts = cron_str.split()
    if len(_iparts) == 5 and _iparts[0].startswith("*/"):
        try:
            return {"interval_minutes": int(_iparts[0][2:])}
        except ValueError:
            pass

    # One-time reminder: 'once +10m' or 'once +1h'
    if cron_str.startswith("once"):
        import re
        m = re.search(r'\+(\d+)\s*(m|min|h|hr|s|sec)', cron_str)
        if m:
            val = int(m.group(1))
            unit = m.group(2)
            if unit.startswith("h"):
                target = datetime.now() + timedelta(hours=val)
            elif unit.startswith("s"):
                target = datetime.now() + timedelta(seconds=val)
            else:
                target = datetime.now() + timedelta(minutes=val)
            return {
                "hour": target.hour,
                "minute": target.minute,
                "once": True,
                "target_time": target.isoformat(),
            }

    # HH:MM format
    if ":" in cron_str and len(cron_str.split()) <= 2:
        time_part = cron_str.split()[-1]
        prefix = cron_str.split()[0] if len(cron_str.split()) > 1 else ""
        parts = time_part.split(":")
        h, m = int(parts[0]), int(parts[1])
        result = {"hour": h, "minute": m}
        if prefix in ("weekday", "平日", "工作日"):
            result["day_of_week"] = "mon-fri"
        return result

    # Full cron: minute hour day month day_of_week
    parts = cron_str.split()
    if len(parts) == 5:
        result = {}
        if parts[0] != "*":
            result["minute"] = int(parts[0])
        if parts[1] != "*":
            result["hour"] = int(parts[1])
        if parts[2] != "*":
            result["day"] = int(parts[2])
        if parts[3] != "*":
            result["month"] = int(parts[3])
        if parts[4] != "*":
            result["day_of_week"] = parts[4]
        return result

    return {"hour": 8, "minute": 0}


_NEWS_KEYWORDS = {"新聞", "news", "頭條", "時事", "報導"}
_DOMAIN_KEYWORDS = [
    # Finance / Economy
    "經濟", "股市", "房市", "金融", "財經", "投資", "貿易", "匯率", "利率",
    "加密貨幣", "區塊鏈", "房地產", "基金", "債券", "期貨", "外匯",
    # Tech
    "科技", "AI", "半導體", "電動車", "生技", "5G", "量子", "機器人",
    "雲端", "資安", "晶片", "軟體",
    # Industry / Sector
    "產業", "能源", "航運", "零售", "製造", "農業", "觀光", "旅遊",
    # Society / Crime / Law
    "政治", "國際", "軍事", "外交", "社會", "社會案件", "社會事件",
    "犯罪", "警政", "刑事", "詐騙", "治安",
    "教育", "體育", "娛樂",
    "醫療", "健康", "環境", "氣候", "法律", "法規",
]
_STOPWORDS = {
    "分鐘", "小時", "天", "週", "月", "年", "後", "前", "每天", "每日",
    "統整", "推送", "搜尋", "幫我", "給我", "整理", "製作", "產生", "生成",
    "PDF", "pdf", "下載", "檔案", "文件",
    "則", "條", "篇", "筆", "個",
    "新聞", "頭條", "報導", "時事", "資訊", "相關", "議題", "主題",
    "請", "並", "且", "與", "和", "的", "了",
}


def _parse_task_index(task_id_str: str) -> int | None:
    """Parse index from user-friendly references like '1', '#2', '第3項', '③'."""
    import re
    if not task_id_str:
        return None
    s = task_id_str.strip()
    # Circled numbers ①②③...
    _CIRCLED = "①②③④⑤⑥⑦⑧⑨⑩⑪⑫⑬⑭⑮⑯⑰⑱⑲⑳"
    if len(s) == 1 and s in _CIRCLED:
        return _CIRCLED.index(s) + 1
    # "第X項" / "第X個" with Chinese or Arabic digits
    _CN = {"一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9, "十": 10}
    m = re.search(r'第([一二三四五六七八九十\d]+)[項個]?', s)
    if m:
        v = m.group(1)
        if v.isdigit():
            return int(v)
        return _CN.get(v)
    # Plain digit or #digit
    m = re.match(r'#?(\d+)$', s)
    if m:
        return int(m.group(1))
    return None


def _extract_topic(text: str) -> str:
    """Extract topic keywords from text (AutoScan-inspired)."""
    import re
    found = []
    for kw in _DOMAIN_KEYWORDS:
        if kw in text and kw not in found:
            found.append(kw)
    # "XXX相關" pattern
    for m in re.finditer(r'([\u4e00-\u9fff]{2,6}?)相關', text):
        cand = m.group(1)
        if cand not in _STOPWORDS and cand not in found:
            found.append(cand)
    return " ".join(found) if found else "綜合"


def _auto_correct_task_type(task_type: str, task_config: dict, original_request: str):
    """
    1. If LLM classified as 'custom'/'reminder' but original_request is clearly
       a news request, auto-correct to 'news' and extract structured fields.
    2. If type is already 'news' but key fields (topic/count/detail) are missing,
       infer them from original_request to prevent defaults like '經濟'.
    """
    import re

    # ── Case 2: type is already 'news' but fields are missing ──
    if task_type == "news":
        text = original_request or task_config.get("original_request", "")
        if text:
            _needs_infer = (
                not task_config.get("topic")
                or not task_config.get("count")
                or not task_config.get("detail")
            )
            if _needs_infer:
                inferred = {}
                if not task_config.get("count"):
                    m = re.search(r'(\d+)\s*[則條篇筆]', text)
                    inferred["count"] = int(m.group(1)) if m else 10
                if not task_config.get("detail"):
                    if any(kw in text for kw in ["詳盡", "詳細", "深入", "越詳盡越好", "越詳細越好"]):
                        inferred["detail"] = "detailed"
                    elif any(kw in text for kw in ["簡要", "精簡", "簡單"]):
                        inferred["detail"] = "brief"
                    else:
                        inferred["detail"] = "normal"
                if not task_config.get("topic"):
                    inferred["topic"] = _extract_topic(text)
                if not task_config.get("extra_instructions"):
                    extra = []
                    if any(kw in text.lower() for kw in ["pdf", "下載"]):
                        extra.append("統整成PDF供下載")
                    if any(kw in text for kw in ["標記出處", "出處", "來源"]):
                        extra.append("標記出處")
                    if extra:
                        inferred["extra_instructions"] = "，".join(extra)
                task_config = {**task_config, **inferred}
                print(f"[AUTO-INFER] Filled missing news fields: {inferred}", file=sys.stderr)
        return task_type, task_config

    # pipeline 類型保持不變，不進行任何自動修正
    if task_type not in ("custom", "reminder"):
        return task_type, task_config

    text = original_request or task_config.get("original_request", "")
    if not text:
        return task_type, task_config

    # Gate: must contain news keyword
    if not any(kw in text.lower() for kw in _NEWS_KEYWORDS):
        return task_type, task_config

    # It's a news request — extract structured fields
    inferred = {}

    # count
    m = re.search(r'(\d+)\s*[則條篇筆]', text)
    inferred["count"] = int(m.group(1)) if m else 10

    # detail
    if any(kw in text for kw in ["詳盡", "詳細", "深入", "越詳盡越好", "越詳細越好"]):
        inferred["detail"] = "detailed"
    elif any(kw in text for kw in ["簡要", "精簡", "簡單"]):
        inferred["detail"] = "brief"
    else:
        inferred["detail"] = "normal"

    # topic
    inferred["topic"] = _extract_topic(text)

    # extra_instructions
    extra = []
    if any(kw in text.lower() for kw in ["pdf", "下載"]):
        extra.append("統整成PDF供下載")
    if any(kw in text for kw in ["標記出處", "出處", "來源"]):
        extra.append("標記出處")
    incl_m = re.search(r'(?:包含|涵蓋|最好包含)(.*?)(?:[，,。]|$)', text)
    if incl_m:
        extra.append(incl_m.group(1).strip())
    if extra:
        inferred["extra_instructions"] = "，".join(extra)

    # Merge: keep original_request, overlay inferred fields
    new_config = {**task_config, **inferred}
    return "news", new_config


def main():
    action = os.getenv("SKILL_PARAM_ACTION", "list")
    task_type = os.getenv("SKILL_PARAM_TASK_TYPE", "custom")
    name = os.getenv("SKILL_PARAM_NAME", "")
    cron = os.getenv("SKILL_PARAM_CRON", "08:00")
    config_str = os.getenv("SKILL_PARAM_CONFIG", "{}")
    task_id = os.getenv("SKILL_PARAM_TASK_ID", "") or os.getenv("SKILL_PARAM_ID", "")

    # Session info from environment (injected by adapter)
    session_id = os.getenv("SESSION_ID", "")
    chat_id = os.getenv("CHAT_ID", "")
    # Read original request from multiple sources in priority order:
    # 1. SKILL_PARAM_ORIGINAL_REQUEST — when passed as top-level input_map
    #    param (workflow executor / LLM-gen path)
    # 2. USER_ORIGINAL_REQUEST — set by adapter for LINE / Web chat path
    user_original_request = (
        os.getenv("SKILL_PARAM_ORIGINAL_REQUEST", "")
        or os.getenv("USER_ORIGINAL_REQUEST", "")
    )

    # Resolve paths
    project_root = _resolve_project_root()
    schedules_dir = project_root / "workspace" / "schedules"
    schedules_dir.mkdir(parents=True, exist_ok=True)

    config_path = schedules_dir / f"{session_id}.json"

    # Load existing config
    if config_path.exists():
        try:
            cfg = json.loads(config_path.read_text(encoding="utf-8"))
        except Exception:
            cfg = {"session_id": session_id, "chat_id": chat_id, "tasks": []}
    else:
        cfg = {"session_id": session_id, "chat_id": chat_id, "tasks": []}

    # Always update chat_id
    if chat_id:
        cfg["chat_id"] = chat_id
    cfg["session_id"] = session_id

    # Parse config JSON
    try:
        task_config = json.loads(config_str) if config_str and config_str != "{}" else {}
    except json.JSONDecodeError:
        task_config = {}

    # ── Helper: build task list summary for post-action response ──
    def _build_tasks_summary(tasks_list):
        if not tasks_list:
            return "📋 目前沒有任何排程。"
        lines = [f"📋 目前排程（共 {len(tasks_list)} 個）："]
        for i, t in enumerate(tasks_list, 1):
            status = "⏸️" if not t.get("enabled", True) else ""
            lines.append(f"{'①②③④⑤⑥⑦⑧⑨⑩'[i-1] if i <= 10 else f'{i}.'} {t['name']} — {t['cron']} {status}")
        return "\n".join(lines)

    # ── ACTION: add ──
    if action == "add":
        # ── Guard: reject follow-up confirmations as original_request ──
        # If user_original_request is a short confirmation like "先刪除再新增" / "好的" / "是",
        # it must NOT be used as task content. The LLM should have extracted the real request
        # from conversation history and put it in config fields.
        _FOLLOWUP_PATTERNS = [
            "先刪除", "刪除這個", "再新增", "好的", "好啊", "可以", "是的", "對", "沒問題",
            "幫我", "麻煩", "OK", "ok", "確認", "執行", "開始", "正確", "沒錯", "對的",
            "yes", "Yes", "YES", "嗯", "恩", "好", "要", "是", "行",
        ]
        _or = task_config.get("original_request", "") or user_original_request or ""
        _is_followup = (
            len(_or) <= 10
            and not any(kw in _or for kw in ["新聞", "推送", "提醒", "學習", "摘要", "搜尋", "行程", "排程"])
        ) or (
            len(_or) <= 20
            and any(p in _or for p in _FOLLOWUP_PATTERNS)
            and not any(kw in _or for kw in ["新聞", "推送", "提醒", "學習", "摘要", "搜尋", "行程", "排程"])
        )
        if _is_followup:
            # Reject: tell LLM to extract real parameters from conversation history
            print(json.dumps({
                "status": "error",
                "action": "add",
                "message": (
                    f"⚠️ original_request 為「{_or}」，這是確認語而非排程需求。"
                    "請從對話歷史中找到使用者的原始排程需求（包含時間、內容、數量等），"
                    "重新提取 task_type、cron、config 各欄位後再呼叫 add。"
                ),
            }, ensure_ascii=False))
            return

        # Always store the user's original request for fallback prompt generation
        if user_original_request and "original_request" not in task_config:
            task_config["original_request"] = user_original_request

        # ── Auto-correct: fix LLM type misclassification before saving ──
        task_type, task_config = _auto_correct_task_type(task_type, task_config, user_original_request)

        # ── Server-side auto-split: detect multiple content types in one request ──
        # e.g., "3個N1文法和10個N1單字" → create 2 tasks
        _split_requests = []
        _orig = user_original_request or task_config.get("original_request", "")
        if task_type == "language" and _orig:
            import re as _split_re
            _has_grammar = any(kw in _orig for kw in ["文法", "語法", "句型", "grammar"])
            _has_vocab = any(kw in _orig for kw in ["單字", "單詞", "詞彙", "vocabulary"])
            if _has_grammar and _has_vocab:
                # Extract counts for each
                _g_count = 5
                _v_count = 5
                _g_m = _split_re.search(r'(\d+)\s*[個條]\s*(?:N\d\s*)?(?:文法|語法|句型)', _orig)
                if _g_m:
                    _g_count = int(_g_m.group(1))
                _v_m = _split_re.search(r'(\d+)\s*[個條]\s*(?:N\d\s*)?(?:單字|單詞|詞彙)', _orig)
                if _v_m:
                    _v_count = int(_v_m.group(1))
                # Extract common fields
                _lang = task_config.get("language", "日文")
                _level = task_config.get("level", "")
                if not _level:
                    _lm = _split_re.search(r'N([1-5])', _orig)
                    _level = f"N{_lm.group(1)}" if _lm else "N3"
                _split_requests = [
                    {"content_type": "grammar", "count": _g_count, "language": _lang, "level": _level,
                     "original_request": _orig, "name_suffix": "文法"},
                    {"content_type": "vocabulary", "count": _v_count, "language": _lang, "level": _level,
                     "original_request": _orig, "name_suffix": "單字"},
                ]

        if _split_requests:
            # Create multiple tasks server-side
            _created_tasks = []
            for _sr in _split_requests:
                _sr_name = f"{_sr['level']}{_sr['language']}{_sr['name_suffix']}推送"
                _sr_config = {k: v for k, v in _sr.items() if k != "name_suffix"}
                _sr_parsed = _parse_cron(cron)
                _sr_task = {
                    "id": f"task_{uuid.uuid4().hex[:8]}",
                    "type": "language",
                    "name": _sr_name,
                    "cron": cron,
                    "cron_parsed": _sr_parsed,
                    "config": _sr_config,
                    "enabled": True,
                    "created_at": datetime.now().isoformat(),
                    "last_run": None,
                }
                if _sr_parsed.get("once"):
                    _sr_task["once"] = True

                # Check dedup for each split task
                _dup_found = False
                for _et in cfg["tasks"]:
                    if (not _et.get("enabled", True) or _et["cron"] != cron
                            or _et["type"] != "language"):
                        continue
                    _ec = _et.get("config", {})
                    if (_ec.get("language") == _sr_config.get("language")
                            and _ec.get("content_type") == _sr_config.get("content_type")):
                        _et["config"].update(_sr_config)
                        _et["name"] = _sr_name
                        _created_tasks.append(_et)
                        _dup_found = True
                        break
                if not _dup_found:
                    cfg["tasks"].append(_sr_task)
                    _created_tasks.append(_sr_task)

            config_path.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
            _tasks_summary = _build_tasks_summary(cfg["tasks"])
            print(json.dumps({
                "status": "success",
                "action": "add",
                "tasks_created": _created_tasks,
                "count": len(_created_tasks),
                "message": f"已自動拆分為 {len(_created_tasks)} 個排程任務",
                "tasks_summary": _tasks_summary,
                "instruction": (
                    "【重要】排程已建立。回覆使用者時必須包含上方 tasks_summary 的排程清單。"
                    "絕對不要自己立刻執行任務內容。"
                ),
            }, ensure_ascii=False))
            return

        # ── Guard: Validate cron against user's actual request ──────────
        # LLM sometimes carries over cron from previous conversation turn,
        # or sends interval (*/5, every +5m) when user meant one-time ("5分鐘後").
        if user_original_request:
            import re as _re

            # Chinese numeral → Arabic conversion for time parsing
            _CN_NUM = {"一": 1, "二": 2, "兩": 2, "三": 3, "四": 4, "五": 5,
                       "六": 6, "七": 7, "八": 8, "九": 9, "十": 10,
                       "十一": 11, "十二": 12, "十三": 13, "十四": 14, "十五": 15,
                       "二十": 20, "三十": 30, "半": 30}

            def _parse_cn_or_digit(text, unit_pattern):
                """Extract number before a unit (分鐘/小時), supporting both 五分鐘 and 5分鐘."""
                # Try Arabic digit first
                m = _re.search(r'(\d+)\s*' + unit_pattern, text)
                if m:
                    return int(m.group(1))
                # Try Chinese numeral (1-2 chars before the unit)
                m = _re.search(r'([一二兩三四五六七八九十半]{1,2})\s*' + unit_pattern, text)
                if m:
                    cn = m.group(1)
                    return _CN_NUM.get(cn, None)
                return None

            _req_min = _parse_cn_or_digit(user_original_request, r'分鐘[後后]')
            _req_hr = _parse_cn_or_digit(user_original_request, r'小時[後后]')
            # Also parse Chinese count (五則 → 5)
            _req_count = _parse_cn_or_digit(user_original_request, r'[則條篇筆個]')

            # Detect one-time intent: "X分鐘後" / "X小時後" WITHOUT recurring keywords
            # Recurring keywords — recognise common Chinese phrasings:
            #   每天/每日/每週/每周/每月/每年
            #   每個工作天/每個工作日/每工作日 (user's "每個工作天" case)
            #   每週五/每個週一 etc.
            #   每 N 分鐘/小時
            #   每隔、定時、weekday、daily、weekly
            _recurring_kw = _re.search(
                r'每[天日週周月年]'
                r'|每個?[天日週周月]'
                r'|每個?工作[天日]'
                r'|每週?[一二三四五六日天]'
                r'|每\s*[\d一二三四五六七八九十]+\s*(分鐘|小時|時|日|天)'
                r'|每隔|定時|周期性|固定時間'
                r'|工作日|週[一二三四五]至週[一二三四五六日天]'
                r'|weekday|daily|weekly|monthly',
                user_original_request,
            )

            if _req_min and not _recurring_kw:
                # User said "X分鐘後" (one-time) — cron MUST be "once +Xm"
                _expected = f"once +{_req_min}m"
                if cron != _expected:
                    _old = cron
                    cron = _expected
                    print(f"[GUARD] Corrected cron: {_old} → {cron} (user said {_req_min}分鐘後, one-time)", file=sys.stderr)
            elif _req_hr and not _recurring_kw:
                # User said "X小時後" (one-time) — cron MUST be "once +Xh"
                _expected = f"once +{_req_hr}h"
                if cron != _expected:
                    _old = cron
                    cron = _expected
                    print(f"[GUARD] Corrected cron: {_old} → {cron} (user said {_req_hr}小時後, one-time)", file=sys.stderr)
            elif cron.startswith("once"):
                # Already once format — just validate the time value matches
                if _req_min:
                    _cron_m = _re.search(r'\+(\d+)\s*m', cron)
                    _cron_min = int(_cron_m.group(1)) if _cron_m else None
                    if _cron_min is not None and _cron_min != _req_min:
                        _old = cron
                        cron = f"once +{_req_min}m"
                        print(f"[GUARD] Corrected cron: {_old} → {cron} (user said {_req_min}分鐘)", file=sys.stderr)
                elif _req_hr:
                    _cron_h = _re.search(r'\+(\d+)\s*h', cron)
                    _cron_hr = int(_cron_h.group(1)) if _cron_h else None
                    if _cron_hr is not None and _cron_hr != _req_hr:
                        _old = cron
                        cron = f"once +{_req_hr}h"
                        print(f"[GUARD] Corrected cron: {_old} → {cron} (user said {_req_hr}小時)", file=sys.stderr)

            # Guard: Fixed-time one-shot — "在1700時" / "17點" / "下午5點" without recurring keywords
            # If user said a specific clock time but no "每天/每日/每週", treat as one-time.
            # IMPORTANT: require an explicit time unit (時/點) or colon separator, otherwise
            # bare numbers like "200字元", "十則" get mis-parsed as clock times.
            if not _recurring_kw and not _req_min and not _req_hr and not cron.startswith("once"):
                # Detect fixed-time patterns: "1700時", "17:00", "17點", "下午5點"
                _fixed_time = None
                # Pattern 1: 3-4 digits REQUIRED to be followed by 時/點 (e.g. "1700時"),
                # previously [時点點]? was optional causing "200字元" → 02:00
                _ft = _re.search(r'(?:在|於)\s*(\d{3,4})\s*[時点點]', user_original_request)
                if _ft:
                    _t = _ft.group(1).zfill(4)
                    _fixed_time = (int(_t[:2]), int(_t[2:]))
                # Pattern 2: colon separator (17:00 / 17：00) — these are unambiguously times
                if not _fixed_time:
                    _ft = _re.search(r'(\d{1,2})\s*[:：]\s*(\d{2})', user_original_request)
                    if _ft:
                        _fixed_time = (int(_ft.group(1)), int(_ft.group(2)))
                # Pattern 3: Chinese clock marker 點 (e.g. "17點", "下午5點半"). Only
                # match when the digit IS followed by 點/点, not when it precedes
                # other quantifier units like 則/個/筆/條/字.
                if not _fixed_time:
                    _ft = _re.search(r'(\d{1,2})\s*[點点](\d{0,2})', user_original_request)
                    if _ft:
                        _h = int(_ft.group(1))
                        _m = int(_ft.group(2)) if _ft.group(2) else 0
                        # Handle 下午/PM
                        if _re.search(r'下午|晚上|pm', user_original_request, _re.IGNORECASE) and _h < 12:
                            _h += 12
                        _fixed_time = (_h, _m)
                # Pattern 4: Chinese numeral hour (e.g. 「上午八點」 = 08:00, 「下午五點」 = 17:00)
                # This was missing — so "上午八點" got parsed via the looser digit pattern
                # into some random match. Explicit Chinese numeral → hour mapping.
                if not _fixed_time:
                    _cn_digits = {"零":0,"一":1,"二":2,"三":3,"四":4,"五":5,"六":6,"七":7,"八":8,"九":9,"十":10,"十一":11,"十二":12}
                    _cn_re = _re.search(r'(上午|早上|中午|下午|晚上)?\s*([一二三四五六七八九十]+)\s*[點点]', user_original_request)
                    if _cn_re:
                        _ampm = _cn_re.group(1) or ""
                        _hanzi = _cn_re.group(2)
                        if _hanzi in _cn_digits:
                            _h = _cn_digits[_hanzi]
                            if _ampm in ("下午", "晚上") and _h < 12:
                                _h += 12
                            elif _ampm == "中午" and _h < 12:
                                _h = 12
                            _fixed_time = (_h, 0)

                if _fixed_time:
                    _target_h, _target_m = _fixed_time
                    _now = datetime.now()
                    _target = _now.replace(hour=_target_h, minute=_target_m, second=0, microsecond=0)
                    if _target <= _now:
                        _target += timedelta(days=1)  # Tomorrow if time already passed
                    _diff_min = max(1, int((_target - _now).total_seconds() / 60))
                    _old = cron
                    cron = f"once +{_diff_min}m"
                    print(f"[GUARD] Fixed-time one-shot: {_old} → {cron} (target {_target_h:02d}:{_target_m:02d}, {_diff_min}min from now)", file=sys.stderr)

            # Guard: Auto-correct count if Chinese numeral was used (e.g. 五則 → 5)
            if _req_count and task_config.get("count") != _req_count:
                _old_count = task_config.get("count")
                task_config["count"] = _req_count
                print(f"[GUARD] Corrected count: {_old_count} → {_req_count} (parsed from user request)", file=sys.stderr)

        # ── Guard: Auto-correct name if it doesn't match task type ──────
        # LLM sometimes copies name from previous task (e.g. "提醒看手機" for a news task)
        _REMINDER_NAME_KW = {"提醒", "看手機", "開會", "買", "記得"}
        if task_type == "news" and name and any(kw in name for kw in _REMINDER_NAME_KW):
            _topic = task_config.get("topic", "綜合")
            name = f"{_topic}新聞統整"
            if task_config.get("extra_instructions") and "pdf" in task_config["extra_instructions"].lower():
                name += "PDF"
            print(f"[GUARD] Corrected name to: {name}", file=sys.stderr)

        if not name:
            type_names = {
                "news": "每日新聞摘要",
                "work_summary": "工作重點摘要",
                "language": "語言學習",
                "custom": "自訂推送",
                "reminder": "提醒",
                "pipeline": "複合任務",
            }
            name = type_names.get(task_type, "定時推送")

        parsed_cron = _parse_cron(cron)

        task = {
            "id": f"task_{uuid.uuid4().hex[:8]}",
            "type": task_type,
            "name": name,
            "cron": cron,
            "cron_parsed": parsed_cron,
            "config": task_config,
            "enabled": True,
            "created_at": datetime.now().isoformat(),
            "last_run": None,
        }

        # For one-time reminders, mark as once
        if parsed_cron.get("once"):
            task["once"] = True

        # ── Duplicate detection: same cron + same type → update existing ──
        # Loosened: for news/work_summary, same cron+type is enough (topic may be reparsed differently)
        # For language, also match content_type (grammar vs vocabulary are distinct)
        _updated_existing = False
        for _et in cfg["tasks"]:
            if not _et.get("enabled", True):
                continue
            if _et["cron"] != cron or _et["type"] != task_type:
                continue
            _ec = _et.get("config", {})
            _is_dup = False
            if task_type == "language":
                _is_dup = (_ec.get("language") == task_config.get("language")
                           and _ec.get("content_type") == task_config.get("content_type"))
            elif task_type == "news":
                _is_dup = True  # same cron + same type = same news schedule
            elif task_type == "work_summary":
                _is_dup = True
            elif task_type in ("custom", "pipeline"):
                _is_dup = (_ec.get("original_request") == task_config.get("original_request"))
            elif task_type == "reminder":
                _is_dup = (_ec.get("message") == task_config.get("message"))
            if _is_dup:
                _et["config"].update(task_config)
                _et["name"] = name
                config_path.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
                task = _et  # reuse for response
                _updated_existing = True
                print(f"[DEDUP] Updated existing task {_et['id']} instead of creating duplicate", file=sys.stderr)
                break

        if not _updated_existing:
            cfg["tasks"].append(task)
            config_path.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")

        _tasks_summary = _build_tasks_summary(cfg["tasks"])
        print(json.dumps({
            "status": "success",
            "action": "add",
            "task": task,
            "message": f"排程「{name}」已{'更新' if _updated_existing else '建立'}，時間：{cron}",
            "tasks_summary": _tasks_summary,
            "instruction": (
                "【重要】排程已建立，任務將在指定時間由排程系統自動執行。"
                "你現在只需要回覆使用者確認訊息，並且必須在末尾附上 tasks_summary 中的排程清單。"
                "絕對不要自己立刻執行任務內容（不要搜尋新聞、不要生成檔案、不要呼叫其他工具）。"
            ),
        }, ensure_ascii=False))
        return

    # ── ACTION: list ──
    if action == "list":
        tasks = cfg.get("tasks", [])
        if not tasks:
            print(json.dumps({
                "status": "success",
                "action": "list",
                "tasks": [],
                "message": "目前沒有任何排程任務。",
            }, ensure_ascii=False))
            return

        summary = []
        for i, t in enumerate(tasks, 1):
            summary.append({
                "index": i,
                "id": t["id"],
                "name": t["name"],
                "type": t["type"],
                "cron": t["cron"],
                "enabled": t.get("enabled", True),
                "last_run": t.get("last_run"),
            })

        print(json.dumps({
            "status": "success",
            "action": "list",
            "tasks": summary,
            "count": len(summary),
            "message": f"共有 {len(summary)} 個排程任務。",
        }, ensure_ascii=False))
        return

    # ── Helper: auto-list when no task_id provided for modification ops ──
    def _auto_list_for_selection(action_name: str):
        """Return numbered task list for user to pick from."""
        tasks = [t for t in cfg.get("tasks", []) if t.get("enabled", True)] if action_name != "resume" else cfg.get("tasks", [])
        if not tasks:
            print(json.dumps({
                "status": "success",
                "action": action_name,
                "message": "目前沒有可操作的排程任務。",
            }, ensure_ascii=False))
            return True
        summary = []
        for i, t in enumerate(tasks, 1):
            summary.append({
                "index": i,
                "id": t["id"],
                "name": t["name"],
                "type": t["type"],
                "cron": t["cron"],
                "enabled": t.get("enabled", True),
            })
        _action_zh = {"remove": "刪除", "pause": "暫停", "resume": "恢復", "trigger": "立即執行"}.get(action_name, action_name)
        print(json.dumps({
            "status": "need_selection",
            "action": action_name,
            "tasks": summary,
            "count": len(summary),
            "message": f"共有 {len(summary)} 個排程任務，請問要{_action_zh}哪一個？",
            "instruction": (
                f"請以編號清單呈現排程（① ② ③ ...），詢問使用者要{_action_zh}哪一項。"
                "不要顯示 task_id。使用者回覆「第X項」或「①」時，"
                f"再次呼叫此工具 action={action_name}，task_id 填入使用者指定的編號數字（如 '2'）。"
            ),
        }, ensure_ascii=False))
        return True

    # ── Helper: resolve task_id (supports index like "2", "#2", "第2項", "②") ──
    def _resolve_task_id(tid: str) -> str:
        """If tid is not a real task_id, try to parse it as an index."""
        if tid.startswith("task_"):
            return tid
        idx = _parse_task_index(tid)
        if idx and 1 <= idx <= len(cfg.get("tasks", [])):
            resolved = cfg["tasks"][idx - 1]["id"]
            print(f"[INDEX] Resolved index {idx} → {resolved}", file=sys.stderr)
            return resolved
        return tid  # fallback: return as-is

    # ── Helper: try to extract task index from user_original_request when task_id is empty ──
    def _try_extract_task_id_from_request():
        """Last resort: if LLM didn't fill task_id, parse index from user's raw request."""
        if not user_original_request:
            return ""
        idx = _parse_task_index(user_original_request)
        if idx and 1 <= idx <= len(cfg.get("tasks", [])):
            resolved = cfg["tasks"][idx - 1]["id"]
            print(f"[GUARD] Extracted task index {idx} → {resolved} from user request: '{user_original_request}'", file=sys.stderr)
            return resolved
        # Also try bare digit anywhere in the request
        import re as _re2
        _m = _re2.search(r'(\d+)', user_original_request)
        if _m:
            _idx = int(_m.group(1))
            if 1 <= _idx <= len(cfg.get("tasks", [])):
                resolved = cfg["tasks"][_idx - 1]["id"]
                print(f"[GUARD] Extracted bare digit {_idx} → {resolved} from user request: '{user_original_request}'", file=sys.stderr)
                return resolved
        return ""

    # ── ACTION: remove ──
    if action == "remove":
        if not task_id:
            task_id = _try_extract_task_id_from_request()
        if not task_id:
            if _auto_list_for_selection("remove"):
                return

        task_id = _resolve_task_id(task_id)
        original_len = len(cfg["tasks"])
        cfg["tasks"] = [t for t in cfg["tasks"] if t["id"] != task_id]
        if len(cfg["tasks"]) < original_len:
            config_path.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
            _tasks_summary = _build_tasks_summary(cfg["tasks"])
            print(json.dumps({
                "status": "success",
                "action": "remove",
                "task_id": task_id,
                "message": f"已刪除排程 {task_id}",
                "tasks_summary": _tasks_summary,
                "instruction": "回覆使用者時必須在末尾附上 tasks_summary 中的排程清單。",
            }, ensure_ascii=False))
        else:
            print(json.dumps({
                "status": "error",
                "message": f"找不到 task_id: {task_id}",
            }, ensure_ascii=False))
        return

    # ── ACTION: pause ──
    if action == "pause":
        if not task_id:
            task_id = _try_extract_task_id_from_request()
        if not task_id:
            if _auto_list_for_selection("pause"):
                return
        task_id = _resolve_task_id(task_id)
        for t in cfg["tasks"]:
            if t["id"] == task_id:
                t["enabled"] = False
                config_path.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
                print(json.dumps({
                    "status": "success",
                    "action": "pause",
                    "task_id": task_id,
                    "message": f"已暫停排程 {task_id}",
                }, ensure_ascii=False))
                return
        print(json.dumps({"status": "error", "message": f"找不到 task_id: {task_id}"}, ensure_ascii=False))
        return

    # ── ACTION: resume ──
    if action == "resume":
        if not task_id:
            task_id = _try_extract_task_id_from_request()
        if not task_id:
            if _auto_list_for_selection("resume"):
                return
        task_id = _resolve_task_id(task_id)
        for t in cfg["tasks"]:
            if t["id"] == task_id:
                t["enabled"] = True
                config_path.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
                print(json.dumps({
                    "status": "success",
                    "action": "resume",
                    "task_id": task_id,
                    "message": f"已恢復排程 {task_id}",
                }, ensure_ascii=False))
                return
        print(json.dumps({"status": "error", "message": f"找不到 task_id: {task_id}"}, ensure_ascii=False))
        return

    # ── ACTION: trigger ──
    if action == "trigger":
        if not task_id:
            task_id = _try_extract_task_id_from_request()
        if not task_id:
            if _auto_list_for_selection("trigger"):
                return
        task_id = _resolve_task_id(task_id)
        # Mark for immediate execution by setting last_run to None
        # and cron to current time
        for t in cfg["tasks"]:
            if t["id"] == task_id:
                now = datetime.now()
                t["cron_parsed"]["hour"] = now.hour
                t["cron_parsed"]["minute"] = now.minute
                t["last_run"] = None
                config_path.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
                print(json.dumps({
                    "status": "success",
                    "action": "trigger",
                    "task_id": task_id,
                    "message": f"已排入立即執行：{t['name']}，將在下一分鐘推送。",
                }, ensure_ascii=False))
                return
        print(json.dumps({"status": "error", "message": f"找不到 task_id: {task_id}"}, ensure_ascii=False))
        return

    print(json.dumps({"status": "error", "message": f"不支援的操作: {action}"}, ensure_ascii=False))


if __name__ == "__main__":
    main()
