---
name: mcp-google-calendar-digest
provider: mcp
version: 1.0.0
runtime_requirements: [google-api-python-client, google-auth]
description: >
  Google 日曆行程摘要工具。專為定時推播設計，產出格式化的今日/本週行程摘要文字。
  此工具與 mcp-schedule-manager 的 pipeline 類型搭配使用，
  由排程系統在指定時間自動呼叫，將行程摘要推送至 LINE。
  一般使用者直接問「今天行程」時請用 mcp-google-calendar 的 today action，不要用此工具。
parameters:
  type: object
  properties:
    range:
      type: string
      description: "摘要範圍。today=今日、tomorrow=明日、week=本週、next_3days=未來3天"
      enum: ["today", "tomorrow", "week", "next_3days"]
    format:
      type: string
      description: "輸出格式。summary=精簡摘要（適合 LINE 推播）、detailed=包含地點與參與者"
      enum: ["summary", "detailed"]
  required: [range]
estimated_tokens: 60
risk_level: low
execution_timeout: 30
---

# MCP Google Calendar Digest（行程摘要推播工具）

## 說明
此技能專為 ScheduledPushService 的 pipeline 任務設計，查詢 Google Calendar
指定範圍的事件並產出人類可讀的格式化摘要，適合直接推送到 LINE。

## 使用時機
- 被 ScheduledPushService 的 pipeline 任務自動呼叫
- 搭配 mcp-schedule-manager 設定每日行程推播

## 不適用場景
- 使用者即時問「今天有什麼會」→ 請用 mcp-google-calendar action=today
- 使用者要建立/修改行程 → 請用 mcp-google-calendar

## 輸出格式
直接產出人類可讀的格式化文字（非原始 JSON），適合 LINE 直接推送。

### summary 範例
```
📅 今日行程（4/7 週一）

🔵 10:00-11:00 週會（3F會議室）
🔵 14:00-15:00 客戶提案
🟢 15:00-18:00 無行程

共 2 個會議，下午 3 點後有空
```

### detailed 範例
```
📅 本週行程摘要（4/7-4/11）

【週一 4/7】
  10:00 週會 @3F會議室 (Amy, Bob)
  14:00 客戶提案 @Google Meet
【週二 4/8】
  全天無行程
```
