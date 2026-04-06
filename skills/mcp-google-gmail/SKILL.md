---
name: mcp-google-gmail
provider: mcp
version: 1.0.0
runtime_requirements: [google-api-python-client, google-auth]
description: >
  Gmail 郵件管理工具。搜尋信件、讀取信件內容、發送信件、回覆信件、建立草稿。
  當使用者提到「信件」「email」「寄信」「收件匣」「有沒有信」「回覆郵件」
  「幫我寫一封信」「查一下信箱」「草稿」「mail」等與電子郵件相關的意圖時使用此工具。
  注意：此工具處理的是使用者本人的 Gmail 帳號，需要 Google OAuth 授權。
parameters:
  type: object
  properties:
    action:
      type: string
      description: >
        操作類型。
        list=列出最近信件、
        search=依關鍵字搜尋信件、
        read=讀取指定信件內文、
        send=發送新信件、
        reply=回覆指定信件、
        draft=建立草稿（不發送）
      enum: ["list", "search", "read", "send", "reply", "draft"]
    query:
      type: string
      description: "[search] Gmail 搜尋語法，例如 'from:boss@co.com subject:報告 after:2026/04/01'"
    max_results:
      type: integer
      description: "[list/search] 最多回傳幾筆，預設 10"
    message_id:
      type: string
      description: "[read/reply] 要讀取或回覆的信件 ID"
    to:
      type: array
      items:
        type: string
      description: "[send] 收件人 email 列表"
    cc:
      type: array
      items:
        type: string
      description: "[send/reply] 副本 email 列表（選填）"
    subject:
      type: string
      description: "[send/draft] 信件主旨"
    body:
      type: string
      description: "[send/reply/draft] 信件內文（純文字或 HTML）"
    body_format:
      type: string
      description: "[send/reply/draft] 內文格式，預設 plain"
      enum: ["plain", "html"]
  required: [action]
estimated_tokens: 120
risk_level: high
risk_description: >
  發送 (send) 和回覆 (reply) 操作會從使用者的 Gmail 帳號寄出真實信件，
  收件人會收到通知。此操作不可撤回。
  查詢類操作 (list/search/read) 和草稿 (draft) 為安全操作。
execution_timeout: 30
---

# MCP Google Gmail（Gmail 郵件管理工具）

## 說明
此技能透過 Gmail API 管理使用者的電子郵件。

## 使用時機
- 使用者說「看一下最近有什麼信」「John 有寄信給我嗎」
- 使用者說「回覆他說好」「寄一封信給 Amy」「幫我存草稿」

## 不適用場景
- 行程管理 → 請用 mcp-google-calendar
- 視訊會議 → 請用 mcp-google-meet
- LINE 推播 → 請用 mcp-schedule-manager

## 風險分級
- `list` / `search` / `read` / `draft` → 唯讀或草稿，自動放行
- `send` / `reply` → 寄出真實信件，觸發 Auth Modal 確認

## 隱私保護
- 群組聊天中（session_id 為 `line_group_*`）僅回傳信件摘要（寄件人 + 主旨）
- 不在群組中洩漏信件全文

## 搜尋語法
支援 Gmail 原生搜尋語法：
- `from:` — 寄件人
- `to:` — 收件人
- `subject:` — 主旨
- `after:` / `before:` — 日期範圍
- `has:attachment` — 有附件
- `is:unread` — 未讀

## 輸出格式
### list / search
```json
{
  "status": "success",
  "emails": [
    {"message_id": "...", "from": "...", "subject": "...", "snippet": "...", "date": "...", "unread": true}
  ]
}
```

### read
```json
{
  "status": "success",
  "from": "...", "to": ["..."], "subject": "...",
  "body": "...", "date": "...",
  "attachments": [{"filename": "...", "size": "..."}]
}
```

### send / reply
```json
{"status": "success", "message_id": "...", "thread_id": "..."}
```
