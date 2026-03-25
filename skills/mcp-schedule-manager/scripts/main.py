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

        # Always store the user's original request for fallback prompt generation
        if user_original_request and "original_request" not in task_config:
            task_config["original_request"] = user_original_request

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
