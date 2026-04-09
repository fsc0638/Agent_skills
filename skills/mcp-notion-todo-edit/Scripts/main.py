"""
mcp-notion-todo-edit — Notion ToDo 單筆編輯 / 刪除

支援動作:
  update: 更新指定頁面的欄位（狀態、負責人、到期日、專案、標題）
  delete: 封存（軟刪除）指定頁面
"""

import os
import json

import requests

# ── Configuration ────────────────────────────────────────────────────────────

NOTION_API_BASE = "https://api.notion.com/v1"
NOTION_VERSION = "2022-06-28"


def _headers(token: str) -> dict:
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Notion-Version": NOTION_VERSION,
    }


# ── Update ───────────────────────────────────────────────────────────────────

def action_update(token: str, page_id: str, status: str | None,
                  assignee: str | None, due_date: str | None,
                  project: str | None, todo_title: str | None) -> dict:
    """Update specified fields on a Notion page."""
    properties = {}
    updated_fields = []

    if todo_title:
        properties["ToDo"] = {"title": [{"text": {"content": todo_title}}]}
        updated_fields.append("ToDo")

    if status:
        properties["狀態"] = {"status": {"name": status}}
        updated_fields.append("狀態")

    if assignee:
        # Support comma-separated multiple assignees
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
        return {
            "status": "error",
            "message": "未指定任何要更新的欄位，請至少提供 status / assignee / due_date / project / todo_title 其中之一",
        }

    resp = requests.patch(
        f"{NOTION_API_BASE}/pages/{page_id}",
        headers=_headers(token),
        json={"properties": properties},
        timeout=15,
    )

    if resp.ok:
        return {
            "status": "success",
            "action": "update",
            "page_id": page_id,
            "updated_fields": updated_fields,
            "message": f"已成功更新 {len(updated_fields)} 個欄位：{'、'.join(updated_fields)}",
        }
    else:
        err = resp.json()
        return {
            "status": "error",
            "action": "update",
            "page_id": page_id,
            "message": f"Notion API 錯誤：{err.get('message', resp.status_code)}",
        }


# ── Delete (Archive) ─────────────────────────────────────────────────────────

def action_delete(token: str, page_id: str) -> dict:
    """Archive a Notion page (soft delete)."""
    resp = requests.patch(
        f"{NOTION_API_BASE}/pages/{page_id}",
        headers=_headers(token),
        json={"archived": True},
        timeout=15,
    )

    if resp.ok:
        return {
            "status": "success",
            "action": "delete",
            "page_id": page_id,
            "message": "已成功封存該待辦項目（可在 Notion 垃圾桶中還原）",
        }
    else:
        err = resp.json()
        return {
            "status": "error",
            "action": "delete",
            "page_id": page_id,
            "message": f"Notion API 錯誤：{err.get('message', resp.status_code)}",
        }


# ── Main Entry Point ─────────────────────────────────────────────────────────

def main():
    action = os.getenv("SKILL_PARAM_ACTION", "").strip().lower()
    page_id = os.getenv("SKILL_PARAM_PAGE_ID", "").strip()
    status = os.getenv("SKILL_PARAM_STATUS", "").strip() or None
    assignee = os.getenv("SKILL_PARAM_ASSIGNEE", "").strip() or None
    due_date = os.getenv("SKILL_PARAM_DUE_DATE", "").strip() or None
    project = os.getenv("SKILL_PARAM_PROJECT", "").strip() or None
    todo_title = os.getenv("SKILL_PARAM_TODO_TITLE", "").strip() or None

    # Credentials
    token = os.getenv("NOTION_TOKEN", "")

    if not token:
        print(json.dumps({
            "status": "error",
            "message": "缺少 NOTION_TOKEN，請在 .env 中配置",
        }, ensure_ascii=False))
        return

    if not page_id:
        print(json.dumps({
            "status": "error",
            "message": "缺少 page_id，請先透過 mcp-notion-query 查詢取得目標項目的 page_id",
        }, ensure_ascii=False))
        return

    if action not in ("update", "delete"):
        print(json.dumps({
            "status": "error",
            "message": f"不支援的動作：{action}，請使用 update 或 delete",
        }, ensure_ascii=False))
        return

    try:
        if action == "update":
            result = action_update(token, page_id, status, assignee, due_date, project, todo_title)
        else:
            result = action_delete(token, page_id)

        print(json.dumps(result, ensure_ascii=False))

    except Exception as e:
        print(json.dumps({
            "status": "error",
            "message": f"執行失敗：{e}",
        }, ensure_ascii=False))


if __name__ == "__main__":
    main()
