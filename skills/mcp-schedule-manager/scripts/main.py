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
    cron_str = cron_str.strip()

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
                import sys
                print(f"[AUTO-INFER] Filled missing news fields: {inferred}", file=sys.stderr)
        return task_type, task_config

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
    task_id = os.getenv("SKILL_PARAM_TASK_ID", "")

    # Session info from environment (injected by adapter)
    session_id = os.getenv("SESSION_ID", "")
    chat_id = os.getenv("CHAT_ID", "")
    user_original_request = os.getenv("USER_ORIGINAL_REQUEST", "")

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

    # ── ACTION: add ──
    if action == "add":
        # Always store the user's original request for fallback prompt generation
        if user_original_request and "original_request" not in task_config:
            task_config["original_request"] = user_original_request

        # ── Auto-correct: fix LLM type misclassification before saving ──
        task_type, task_config = _auto_correct_task_type(task_type, task_config, user_original_request)

        # ── Guard: Validate cron against user's actual request ──────────
        # LLM sometimes carries over cron from previous conversation turn.
        # If user_original_request explicitly says "X分鐘後" but cron doesn't match, fix it.
        if user_original_request and cron.startswith("once"):
            import re as _re
            _time_m = _re.search(r'(\d+)\s*分鐘[後后]?', user_original_request)
            if _time_m:
                _req_min = int(_time_m.group(1))
                _cron_m = _re.search(r'\+(\d+)\s*m', cron)
                _cron_min = int(_cron_m.group(1)) if _cron_m else None
                if _cron_min is not None and _cron_min != _req_min:
                    _old = cron
                    cron = f"once +{_req_min}m"
                    import sys
                    print(f"[GUARD] Corrected cron: {_old} → {cron} (user said {_req_min}分鐘)", file=sys.stderr)
            else:
                _time_h = _re.search(r'(\d+)\s*小時[後后]?', user_original_request)
                if _time_h:
                    _req_hr = int(_time_h.group(1))
                    _cron_h = _re.search(r'\+(\d+)\s*h', cron)
                    _cron_hr = int(_cron_h.group(1)) if _cron_h else None
                    if _cron_hr is not None and _cron_hr != _req_hr:
                        _old = cron
                        cron = f"once +{_req_hr}h"
                        import sys
                        print(f"[GUARD] Corrected cron: {_old} → {cron} (user said {_req_hr}小時)", file=sys.stderr)

        # ── Guard: Auto-correct name if it doesn't match task type ──────
        # LLM sometimes copies name from previous task (e.g. "提醒看手機" for a news task)
        _REMINDER_NAME_KW = {"提醒", "看手機", "開會", "買", "記得"}
        if task_type == "news" and name and any(kw in name for kw in _REMINDER_NAME_KW):
            _topic = task_config.get("topic", "綜合")
            name = f"{_topic}新聞統整"
            if task_config.get("extra_instructions") and "pdf" in task_config["extra_instructions"].lower():
                name += "PDF"
            import sys
            print(f"[GUARD] Corrected name to: {name}", file=sys.stderr)

        if not name:
            type_names = {
                "news": "每日新聞摘要",
                "work_summary": "工作重點摘要",
                "language": "語言學習",
                "custom": "自訂推送",
                "reminder": "提醒",
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

        cfg["tasks"].append(task)
        config_path.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")

        print(json.dumps({
            "status": "success",
            "action": "add",
            "task": task,
            "message": f"排程「{name}」已建立，時間：{cron}",
            "instruction": (
                "【重要】排程已建立，任務將在指定時間由排程系統自動執行。"
                "你現在只需要回覆使用者確認訊息（如「已幫你設定X分鐘後的任務」），"
                "絕對不要自己立刻執行任務內容（不要搜尋新聞、不要生成檔案、不要呼叫其他工具）。"
                "排程系統會在時間到時自動完成所有工作。"
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
        for t in tasks:
            summary.append({
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

    # ── ACTION: remove ──
    if action == "remove":
        if not task_id:
            print(json.dumps({
                "status": "error",
                "message": "請提供要刪除的 task_id",
            }, ensure_ascii=False))
            return

        original_len = len(cfg["tasks"])
        cfg["tasks"] = [t for t in cfg["tasks"] if t["id"] != task_id]
        if len(cfg["tasks"]) < original_len:
            config_path.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
            print(json.dumps({
                "status": "success",
                "action": "remove",
                "task_id": task_id,
                "message": f"已刪除排程 {task_id}",
            }, ensure_ascii=False))
        else:
            print(json.dumps({
                "status": "error",
                "message": f"找不到 task_id: {task_id}",
            }, ensure_ascii=False))
        return

    # ── ACTION: pause ──
    if action == "pause":
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
