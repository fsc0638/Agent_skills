---
name: mcp-notion-todo-edit
provider: mcp
version: 1.0.0
description: >
  編輯或刪除 Notion ToDo 項目。支援更新狀態、負責人、到期日、專案等欄位，
  以及封存（軟刪除）指定項目。需搭配 mcp-notion-query 先查詢取得 page_id。
  當使用者提到「更新待辦」「改狀態」「標記完成」「修改todo」「刪除任務」
  「移除待辦」「刪掉那筆」「把...改成」時觸發此技能。
parameters:
  type: object
  properties:
    action:
      type: string
      description: >
        操作類型。
        update: 更新指定頁面的欄位（僅更新有傳入的欄位，其餘不動）；
        delete: 封存（軟刪除）指定頁面，可在 Notion 中還原。
      enum: [update, delete]
    page_id:
      type: string
      description: "Notion 頁面 ID，從 mcp-notion-query 查詢結果的 page_id 欄位取得。"
    status:
      type: string
      description: "更新狀態。可選值：未開始、進行中、已完成。僅 action=update 時有效。"
    assignee:
      type: string
      description: "更新負責人名稱（會取代現有負責人）。僅 action=update 時有效。"
    due_date:
      type: string
      description: "更新到期日，格式 yyyy-mm-dd。僅 action=update 時有效。"
    project:
      type: string
      description: "更新專案名稱。僅 action=update 時有效。"
    todo_title:
      type: string
      description: "更新 ToDo 標題文字。僅 action=update 時有效。"
  required: [action, page_id]
runtime_requirements: [requests]
estimated_tokens: 600
execution_timeout: 30
risk_level: high
risk_description: >
  此技能會修改或封存 Notion 資料庫中的頁面，屬於外部系統寫入操作。
  更新操作會覆寫指定欄位，刪除操作會將頁面封存（可在 Notion 還原）。
---

# Notion ToDo 編輯工具 (mcp-notion-todo-edit)

## 說明

針對單筆 Notion ToDo 項目進行欄位更新或封存刪除。
需先透過 `mcp-notion-query` 查詢取得目標項目的 `page_id`。

## 操作模式

### update — 更新欄位

僅更新有傳入的欄位，未傳入的欄位維持原值。支援欄位：
- `status`：狀態（未開始 / 進行中 / 已完成）
- `assignee`：負責人
- `due_date`：到期日
- `project`：專案
- `todo_title`：ToDo 標題

### delete — 封存刪除

將指定頁面設為 archived，不會永久刪除，可在 Notion 中還原。

## 環境變數需求

| 變數 | 說明 |
|------|------|
| `NOTION_TOKEN` | Notion Integration Token（必要） |

## 輸出格式

```json
{
  "status": "success",
  "action": "update",
  "page_id": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
  "updated_fields": ["狀態", "到期日"],
  "message": "已成功更新 1 筆待辦項目"
}
```
