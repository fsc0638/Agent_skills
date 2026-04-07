---
name: mcp-google-calendar
provider: mcp
version: 1.0.0
runtime_requirements: [googleapiclient, google.auth]
description: >
  Google 日曆管理工具。查詢行程、建立事件、修改事件、刪除事件、查詢空閒時段。
  當使用者提到「行程」「日曆」「排程」「幾點有會」「空閒時間」「安排會議」
  「建立事件」「取消會議」「calendar」等與時間管理相關的意圖時使用此工具。
  注意：若使用者要求「開 Google Meet 連結」，請改用 mcp-google-meet。
  若使用者要求「提醒我」但不涉及日曆事件，請改用 mcp-schedule-manager。
parameters:
  type: object
  properties:
    action:
      type: string
      description: >
        操作類型。
        list=列出指定日期範圍的事件、
        today=今日行程一覽、
        get=取得單一事件詳情、
        create=建立新事件、
        update=修改既有事件、
        delete=刪除事件、
        free_busy=查詢空閒時段
      enum: ["list", "today", "get", "create", "update", "delete", "free_busy"]
    title:
      type: string
      description: "[create/update] 事件標題"
    start:
      type: string
      description: "[create/update/list/free_busy] 開始時間，ISO 8601 格式含時區，例如 2026-04-07T10:00:00+08:00"
    end:
      type: string
      description: "[create/update/list/free_busy] 結束時間，ISO 8601 格式。create 時若未指定，預設為 start + 1 小時"
    location:
      type: string
      description: "[create/update] 地點（選填）"
    description:
      type: string
      description: "[create/update] 事件描述（選填）"
    attendees:
      type: array
      items:
        type: string
      description: "[create/update] 受邀者 email 列表（選填）"
    event_id:
      type: string
      description: "[get/update/delete] Google Calendar event ID"
    max_results:
      type: integer
      description: "[list] 最多回傳幾筆事件，預設 10"
  required: [action]
estimated_tokens: 100
risk_level: low
execution_timeout: 30
---

# MCP Google Calendar（Google 日曆管理工具）

## 說明
此技能透過 Google Calendar API 管理使用者的日曆事件。

## 使用時機
- 使用者說「今天有什麼會」「幫我排下週三 10 點開會」「取消明天的 1on1」
- 使用者說「我下午幾點有空」「查一下行程」
- 使用者說「安排會議」「建立事件」

## 不適用場景
- 純提醒（不涉及日曆事件）→ 請用 mcp-schedule-manager
- 開 Google Meet 連結 → 請用 mcp-google-meet
- 寄信通知 → 請用 mcp-google-gmail

## 風險分級邏輯
- `list` / `today` / `get` / `free_busy` → 唯讀操作，自動放行
- `create` / `update` / `delete` → 寫入操作，觸發 Auth Modal 確認

## 時間基準
所有時間預設 GMT+8 (Asia/Taipei)，LLM 必須將使用者描述轉為 ISO 8601 格式。

## 輸出格式
```json
{"status": "success", "events": [{"event_id": "...", "title": "...", "start": "...", "end": "...", "location": "...", "meet_link": null}]}
```
或
```json
{"status": "success", "event_id": "...", "html_link": "https://calendar.google.com/..."}
```
