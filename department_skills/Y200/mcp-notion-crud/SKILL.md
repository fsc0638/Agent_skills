---
name: mcp-notion-crud
skillk_id: SkillK_dXanFjI1wZZEgnkeUDu1
display_name: "Notion ToDo 資料庫完整操作工具"
category: Department
provider: mcp
version: "1.0.0"
description: >
  Notion ToDo 資料庫完整操作工具。支援新增、查詢、更新、刪除待辦事項， 以及從結構化會議資料批次匯入。 當使用者提到「查待辦」「我的任務」「Notion 進度」「todo list」 「哪些未完成」「任務查詢」「待辦清單」「進度查詢」 「新增待辦」「加一筆任務」「建立todo」 「更新待辦」「改狀態」「標記完成」「修改todo」 「刪除任務」「移除待辦」「刪掉那筆」 「上傳Notion」「寫入Notion」「匯入待辦」時觸發此技能。 【必填參數】呼叫此工具時必須傳入 action 參數，可選值： create（新增單筆，需帶 todo_title）、 create_batch（批次匯入，需帶 items_json 或 cleaned_text + org_data_json）、 list（查詢列表，可帶 filter_status / filter_assignee / filter_project / keyword / filter_date， 例如查今天建立的項目請用 filter_date="today"）、 summary（進度摘要，無額外參數）、 update（更新欄位，需帶 page_id）、 delete（封存刪除，需帶 page_id）。
runtime_requirements: [requests, openai]
risk_level: low
risk_description: >
  此技能可對 Notion 資料庫執行寫入操作（新增、更新、封存頁面）。 action=list 和 action=summary 為唯讀操作，不會修改任何資料。 action=create/create_batch/update/delete 會修改外部系統資料。
execution_timeout: 120
recommended_models:
  openai: gpt-4.1-nano
  gemini: gemini-2.0-flash
  claude: claude-haiku-4-5
---

# Notion ToDo CRUD 工具 (mcp-notion-crud)

## 說明

統一的 Notion ToDo 資料庫操作介面，涵蓋完整 CRUD 功能。

## 操作模式

### create — 新增單筆 ToDo

直接建立一筆待辦項目。必填：`todo_title`。

### create_batch — 批次匯入

兩種使用方式：
1. **直接傳入 items_json**：已經是結構化 JSON Array，直接進入 QA 檢核 + Upload。
2. **傳入 cleaned_text + org_data_json**：從 mcp-meeting-analyzer 的輸出接續，
   執行 Phase 3 Schema Mapping → Phase 4 QA → Upload（Upsert）。

### list — 列出待辦

依條件篩選後回傳 ToDo 清單，包含 page_id 供後續 update/delete 使用。

### summary — 進度摘要

統計各狀態的數量，並列出即將到期與逾期項目。

### update — 更新欄位

僅更新有傳入的欄位，未傳入的欄位維持原值。必填：`page_id`。

### delete — 封存刪除

將指定頁面設為 archived。必填：`page_id`。

## 環境變數需求

| 變數 | 說明 |
|------|------|
| `NOTION_TOKEN` | Notion Integration Token（必要） |
| `NOTION_DATABASE_ID` | 目標 Notion 資料庫 ID（必要） |
| `OPENAI_API_KEY` | 僅 create_batch 的 Schema Mapping 需要 |

## 輸出格式

所有 action 統一回傳 JSON，含 `status` 和 `action` 欄位。