"""
mcp-notion-query — Notion ToDo 資料庫唯讀查詢

支援動作:
  list:    依狀態/負責人/專案/關鍵字篩選待辦事項
  summary: 整體進度摘要（各狀態統計 + 逾期/即將到期）
"""

import os
import sys
import json
from datetime import datetime, timedelta

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


# ── Notion Query ─────────────────────────────────────────────────────────────

def query_database(token: str, database_id: str, filter_obj: dict | None = None,
                   page_size: int = 100, max_pages: int = 3) -> list:
    """
    Query Notion database with optional filter. Handles pagination up to max_pages.
    Returns list of raw page objects.
    """
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
            headers=headers,
            json=body,
            timeout=15,
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
    if date:
        return date.get("start")
    return None


def extract_number(prop: dict) -> float | None:
    return prop.get("number")


def extract_rich_text(prop: dict) -> str:
    parts = prop.get("rich_text", [])
    return "".join(p.get("plain_text", "") for p in parts)


def extract_created_time(prop: dict) -> str | None:
    # created_time type returns ISO string directly
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

    # Add page metadata
    item["_page_id"] = page.get("id", "")
    item["_last_edited"] = page.get("last_edited_time", "")

    return item


# ── Filter Builder ───────────────────────────────────────────────────────────

def build_notion_filter(filter_status: str | None, filter_assignee: str | None,
                        filter_project: str | None) -> dict | None:
    """Build Notion API filter object from user parameters."""
    conditions = []

    if filter_status:
        conditions.append({
            "property": "狀態",
            "status": {"equals": filter_status},
        })

    if filter_assignee:
        # 負責人 in Notion is named "負責人 / PM"
        conditions.append({
            "property": "負責人 / PM",
            "multi_select": {"contains": filter_assignee},
        })

    if filter_project:
        conditions.append({
            "property": "專案",
            "multi_select": {"contains": filter_project},
        })

    if not conditions:
        return None
    if len(conditions) == 1:
        return conditions[0]
    return {"and": conditions}


# ── Local Post-Filters (for keyword search) ──────────────────────────────────

def apply_keyword_filter(items: list, keyword: str) -> list:
    """Filter items by keyword in ToDo title (case-insensitive)."""
    kw = keyword.lower()
    return [item for item in items if kw in item.get("ToDo", "").lower()]


# ── Actions ──────────────────────────────────────────────────────────────────

def action_list(token: str, db_id: str, filter_status: str | None,
                filter_assignee: str | None, filter_project: str | None,
                keyword: str | None, limit: int) -> dict:
    """List todo items with filters."""
    notion_filter = build_notion_filter(filter_status, filter_assignee, filter_project)
    pages = query_database(token, db_id, filter_obj=notion_filter)
    items = [parse_page(p) for p in pages]

    # Apply keyword filter locally (Notion API doesn't support title contains for title type)
    if keyword:
        items = apply_keyword_filter(items, keyword)

    # Apply limit
    total = len(items)
    items = items[:limit]

    # Clean output: remove internal fields
    clean_items = []
    for item in items:
        clean = {k: v for k, v in item.items() if not k.startswith("_") and v is not None}
        clean_items.append(clean)

    return {
        "status": "success",
        "action": "list",
        "total": total,
        "returned": len(clean_items),
        "items": clean_items,
    }


def action_summary(token: str, db_id: str) -> dict:
    """Generate progress summary."""
    pages = query_database(token, db_id, max_pages=5)
    items = [parse_page(p) for p in pages]

    today = datetime.now().strftime("%Y-%m-%d")
    today_dt = datetime.now()

    # Status counts
    status_counts = {}
    overdue = []
    due_soon = []  # within 7 days

    for item in items:
        status = item.get("狀態", "未知")
        status_counts[status] = status_counts.get(status, 0) + 1

        due_date = item.get("到期日")
        if due_date and status not in ("已完成", "完成"):
            try:
                due_dt = datetime.strptime(due_date[:10], "%Y-%m-%d")
                if due_dt < today_dt:
                    overdue.append({
                        "ToDo": item.get("ToDo", ""),
                        "到期日": due_date,
                        "負責人": item.get("負責人 / PM", item.get("負責人", [])),
                        "狀態": status,
                    })
                elif due_dt <= today_dt + timedelta(days=7):
                    due_soon.append({
                        "ToDo": item.get("ToDo", ""),
                        "到期日": due_date,
                        "負責人": item.get("負責人 / PM", item.get("負責人", [])),
                        "狀態": status,
                    })
            except ValueError:
                pass

    # Assignee workload
    assignee_counts = {}
    for item in items:
        assignees = item.get("負責人 / PM", item.get("負責人", []))
        if isinstance(assignees, list):
            for a in assignees:
                if a and a != "待指派":
                    assignee_counts[a] = assignee_counts.get(a, 0) + 1

    return {
        "status": "success",
        "action": "summary",
        "total_items": len(items),
        "by_status": status_counts,
        "overdue": overdue[:20],
        "due_within_7_days": due_soon[:20],
        "by_assignee": assignee_counts,
        "as_of": today,
    }


# ── Main Entry Point ─────────────────────────────────────────────────────────

def main():
    # Read parameters from environment (injected by UMA ExecutionEngine)
    action = os.getenv("SKILL_PARAM_ACTION", "list").strip().lower()
    filter_status = os.getenv("SKILL_PARAM_FILTER_STATUS", "").strip() or None
    filter_assignee = os.getenv("SKILL_PARAM_FILTER_ASSIGNEE", "").strip() or None
    filter_project = os.getenv("SKILL_PARAM_FILTER_PROJECT", "").strip() or None
    keyword = os.getenv("SKILL_PARAM_KEYWORD", "").strip() or None
    limit = int(os.getenv("SKILL_PARAM_LIMIT", "20"))
    limit = max(1, min(limit, 100))

    # Credentials
    token = os.getenv("NOTION_TOKEN", "")
    db_id = os.getenv("NOTION_DATABASE_ID", "")

    if not token or not db_id:
        print(json.dumps({
            "status": "error",
            "message": "缺少 Notion 設定：請在 .env 中配置 NOTION_TOKEN 和 NOTION_DATABASE_ID",
        }, ensure_ascii=False))
        return

    try:
        if action == "summary":
            result = action_summary(token, db_id)
        else:
            result = action_list(token, db_id, filter_status, filter_assignee,
                                 filter_project, keyword, limit)

        print(json.dumps(result, ensure_ascii=False))

    except Exception as e:
        print(json.dumps({
            "status": "error",
            "message": f"查詢失敗：{e}",
        }, ensure_ascii=False))


if __name__ == "__main__":
    main()
