---
name: mcp-google-meet
provider: mcp
version: 1.0.0
runtime_requirements: [googleapiclient, google.auth]
description: >
  Google Meet 會議連結建立工具。建立即時或排程的 Google Meet 會議，並回傳會議連結。
  當使用者說「開一個 Meet」「建立視訊會議連結」「幫我開 Google Meet」
  「產生會議連結」「建立線上會議」「video call」時使用此工具。
  此工具透過 Google Calendar API 建立含 conferenceData 的事件來產生 Meet 連結。
  注意：若使用者只是查詢或管理日曆行程（不需要 Meet 連結），請改用 mcp-google-calendar。
parameters:
  type: object
  properties:
    action:
      type: string
      description: >
        操作類型。
        create=建立新的 Google Meet 會議（含日曆事件 + Meet 連結）、
        instant=建立即時會議（現在開始，預設 1 小時）、
        get_link=從既有日曆事件取得 Meet 連結
      enum: ["create", "instant", "get_link"]
    title:
      type: string
      description: "[create] 會議標題，預設為「線上會議」"
    start:
      type: string
      description: "[create] 會議開始時間，ISO 8601 格式含時區。instant 模式不需要。"
    duration_minutes:
      type: integer
      description: "[create/instant] 會議時長（分鐘），預設 60"
    attendees:
      type: array
      items:
        type: string
      description: "[create/instant] 受邀者 email 列表（選填），會收到含 Meet 連結的日曆邀請"
    event_id:
      type: string
      description: "[get_link] 要查詢 Meet 連結的日曆事件 ID"
  required: [action]
estimated_tokens: 80
risk_level: low
execution_timeout: 30
---

# MCP Google Meet（Google Meet 會議連結建立工具）

## 說明
此技能透過 Google Calendar API 建立含 conferenceData 的事件，自動產生 Google Meet 連結。

## 使用時機
- 使用者說「開一個 Meet」「幫我建會議連結」「現在馬上開一個視訊會議」
- 使用者說「明天 3 點的會議要 Meet 連結」

## 不適用場景
- 查詢行程 → 請用 mcp-google-calendar
- 純提醒 → 請用 mcp-schedule-manager
- 寄信通知 → 請用 mcp-google-gmail

## 技術實作
透過 Calendar API `events.insert()` 搭配：
- `conferenceDataVersion=1`
- `conferenceData.createRequest.requestId` (UUID)
- `conferenceData.createRequest.conferenceSolutionKey.type = "hangoutsMeet"`

## 風險分級
- `get_link` → 唯讀，自動放行
- `create` / `instant` → 建立操作，觸發 Auth Modal

## 輸出格式
```json
{
  "status": "success",
  "meet_link": "https://meet.google.com/abc-def-ghi",
  "event_id": "...",
  "html_link": "https://calendar.google.com/event?eid=..."
}
```
