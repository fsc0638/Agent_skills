---
name: mcp-notion-query
provider: mcp
version: 1.0.0
description: >
  查詢 Notion ToDo 資料庫工具。支援依狀態、負責人、專案、關鍵字等條件
  篩選待辦事項，並可產出進度摘要。為唯讀操作，不會修改任何資料。
  當使用者提到「查待辦」「我的任務」「Notion 進度」「todo list」
  「哪些未完成」「任務查詢」「待辦清單」「進度查詢」時觸發此技能。
parameters:
  type: object
  properties:
    action:
      type: string
      description: >
        查詢動作類型。
        list: 列出待辦事項（可搭配篩選條件）；
        summary: 產出整體進度摘要（各狀態數量統計）。
      enum: [list, summary]
      default: list
    filter_status:
      type: string
      description: "篩選狀態：未開始、進行中、已完成。留空表示不篩選。"
    filter_assignee:
      type: string
      description: "篩選負責人名稱（模糊匹配）。留空表示不篩選。"
    filter_project:
      type: string
      description: "篩選專案名稱（模糊匹配）。留空表示不篩選。"
    keyword:
      type: string
      description: "關鍵字搜尋，會在 ToDo 標題中進行匹配。留空表示不篩選。"
    limit:
      type: integer
      description: "回傳筆數上限，預設 20，最大 100。"
      default: 20
  required: []
runtime_requirements: [requests]
estimated_tokens: 800
execution_timeout: 30
---

# Notion ToDo 查詢工具 (mcp-notion-query)

## 說明

唯讀查詢 Notion ToDo 資料庫，支援多條件篩選與進度摘要。

## 查詢模式

### list — 列出待辦
依條件篩選後回傳 ToDo 清單，包含各欄位詳細資訊。

### summary — 進度摘要
統計各狀態的數量，並列出即將到期與逾期項目。

## 環境變數需求

| 變數 | 說明 |
|------|------|
| `NOTION_TOKEN` | Notion Integration Token（必要） |
| `NOTION_DATABASE_ID` | 目標 Notion 資料庫 ID（必要） |

## 輸出格式

```json
{
  "status": "success",
  "total": 15,
  "items": [
    {
      "ToDo": "完成跨境合作合約審閱",
      "狀態": "進行中",
      "負責人": ["Jason Fan"],
      "專案": ["KWAY 研發專案"],
      "到期日": "2026-04-15",
      "關鍵詞": ["合約條款", "法律審閱"]
    }
  ]
}
```
