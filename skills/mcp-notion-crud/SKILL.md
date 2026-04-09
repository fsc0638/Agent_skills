---
name: mcp-notion-crud
provider: mcp
version: 1.0.0
description: >
  Notion ToDo 資料庫完整操作工具。支援新增、查詢、更新、刪除待辦事項，
  以及從結構化會議資料批次匯入。
  當使用者提到「查待辦」「我的任務」「Notion 進度」「todo list」
  「哪些未完成」「任務查詢」「待辦清單」「進度查詢」
  「新增待辦」「加一筆任務」「建立todo」
  「更新待辦」「改狀態」「標記完成」「修改todo」
  「刪除任務」「移除待辦」「刪掉那筆」
  「上傳Notion」「寫入Notion」「匯入待辦」時觸發此技能。
  【必填參數】呼叫此工具時必須傳入 action 參數，可選值：
  create（新增單筆，需帶 todo_title）、
  create_batch（批次匯入，需帶 items_json 或 cleaned_text + org_data_json）、
  list（查詢列表，可帶 filter_status / filter_assignee / filter_project / keyword）、
  summary（進度摘要，無額外參數）、
  update（更新欄位，需帶 page_id）、
  delete（封存刪除，需帶 page_id）。
parameters:
  type: object
  properties:
    action:
      type: string
      description: >
        操作類型。
        create: 新增單筆 ToDo；
        create_batch: 從結構化 JSON 批次新增（搭配 mcp-meeting-analyzer 輸出使用，支援 Upsert）；
        list: 列出待辦事項（可搭配篩選條件）；
        summary: 產出整體進度摘要（各狀態數量統計）；
        update: 更新指定頁面的欄位；
        delete: 封存（軟刪除）指定頁面。
      enum: [create, create_batch, list, summary, update, delete]
    page_id:
      type: string
      description: "Notion 頁面 ID。action=update/delete 時必填，從 list 查詢結果的 page_id 欄位取得。"
    todo_title:
      type: string
      description: "ToDo 標題。action=create 時必填；action=update 時選填。"
    status:
      type: string
      description: "狀態：未開始、進行中、已完成。action=create/update 時選填。"
    assignee:
      type: string
      description: "負責人名稱（多人以逗號分隔）。action=create/update 時選填。"
    due_date:
      type: string
      description: "到期日，格式 yyyy-mm-dd。action=create/update 時選填。"
    project:
      type: string
      description: "專案名稱（多個以逗號分隔）。action=create/update 時選填。"
    source:
      type: string
      description: "來源（多個以逗號分隔）。action=create 時選填。"
    keywords:
      type: string
      description: "關鍵詞（多個以逗號分隔）。action=create 時選填。"
    items_json:
      type: string
      description: >
        action=create_batch 時必填。結構化 JSON 字串，格式為陣列，
        每個元素包含 ToDo / 專案 / 負責人 / 來源 / 狀態 / 到期日 / 關鍵詞 等欄位。
        通常由 mcp-meeting-analyzer 的輸出經 Phase 3 Schema Mapping 後產生。
    language:
      type: string
      description: "目標語言，用於 create_batch 的 Schema Mapping。預設繁體中文。"
      default: "繁體中文"
    meeting_date:
      type: string
      description: "會議日期（yyyy-mm-dd），用於 create_batch 的專案前綴與到期日推算。"
    cleaned_text:
      type: string
      description: "清洗後的會議文本，用於 create_batch 的 Phase 3 Schema Mapping。由 mcp-meeting-analyzer 產出。"
    org_data_json:
      type: string
      description: "組織識別 JSON 字串，用於 create_batch 的 Phase 3。由 mcp-meeting-analyzer 產出。"
    filter_status:
      type: string
      description: "篩選狀態：未開始、進行中、已完成。action=list 時選填。"
    filter_assignee:
      type: string
      description: "篩選負責人名稱（模糊匹配）。action=list 時選填。"
    filter_project:
      type: string
      description: "篩選專案名稱（模糊匹配）。action=list 時選填。"
    keyword:
      type: string
      description: "關鍵字搜尋，在 ToDo 標題中匹配。action=list 時選填。"
    limit:
      type: integer
      description: "回傳筆數上限，預設 20，最大 100。action=list 時選填。"
      default: 20
  required: [action]
runtime_requirements: [requests, openai]
estimated_tokens: 1000
execution_timeout: 120
risk_level: high
risk_description: >
  此技能可對 Notion 資料庫執行寫入操作（新增、更新、封存頁面）。
  action=list 和 action=summary 為唯讀操作，不會修改任何資料。
  action=create/create_batch/update/delete 會修改外部系統資料。
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
