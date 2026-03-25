---
name: mcp-schedule-manager
provider: mcp
version: 1.0.0
runtime_requirements: []
description: >
  定時推送與提醒管理工具。當使用者要求「每天早上推送新聞」、「每週五下班前提醒我」、
  「定時推送工作摘要」、「幫我設定排程」、「取消推送」等帶有時間排程意圖的指令時，
  必須使用此工具。此工具可新增、列出、刪除、暫停及恢復排程任務。
  支援類型：news（新聞摘要）、work_summary（工作重點）、language（語言學習）、custom（自訂內容）。
  注意：一次性提醒（如「10分鐘後提醒我」）也使用此工具，type 設為 reminder。
parameters:
  type: object
  properties:
    action:
      type: string
      description: >
        操作類型。add=新增排程、list=列出所有排程、remove=刪除排程、
        pause=暫停排程、resume=恢復排程、trigger=立即執行一次
      enum: ["add", "list", "remove", "pause", "resume", "trigger"]
    task_type:
      type: string
      description: >
        推送內容類型（僅 add 時需要）。
        news=新聞摘要、work_summary=工作項目統整、language=語言詞彙學習、
        custom=自訂內容、reminder=一次性提醒
      enum: ["news", "work_summary", "language", "custom", "reminder"]
    name:
      type: string
      description: "任務名稱，用於顯示。例如「每日科技新聞」「日文N3學習」"
    cron:
      type: string
      description: >
        排程時間。支援格式：
        - 簡單時間：'08:30' 表示每天 08:30
        - 工作日：'weekday 09:00' 表示週一到週五 09:00
        - 完整 cron：'30 8 * * 1-5' 表示平日 08:30
        - 一次性：'once +10m' 表示 10 分鐘後（用於 reminder）
    config:
      type: object
      description: >
        【重要：必須完整填入使用者的需求細節】任務設定（依 task_type 不同）：
        news: {"topic": "經濟", "count": 20, "detail": "detailed", "extra_instructions": "包含國際趨勢與房市股市，標記出處，統整成PDF供下載"}
          - topic: 新聞主題關鍵字
          - count: 新聞數量
          - detail: 摘要深度，三種等級：
            "brief"（精簡：5-10句）
            "normal"（正常：10-20句，預設）
            "detailed"（詳盡：至少25句深度報導）
            使用者說「詳盡/詳細/深入」→ "detailed"，說「簡單/精簡/簡要」→ "brief"，其他→ "normal"
          - extra_instructions: 額外需求（如特定子主題、產出PDF等）
        work_summary: {"days": 7}
        language: {"language": "日文", "level": "N3", "count": 5, "topic": "商務"}
        custom: {"prompt": "使用者的完整指令內容"}
        reminder: {"message": "提醒內容"}
        注意：使用者提到的數量、主題、格式要求（如製作PDF）等，都必須填入 config 中。
        若使用者有特殊需求（如產出PDF、包含特定主題），請填入 extra_instructions 欄位。
    task_id:
      type: string
      description: "任務 ID（remove/pause/resume/trigger 時需要）"
  required: [action]
estimated_tokens: 50
risk_level: low
execution_timeout: 10
---

# MCP Schedule Manager（定時推送與提醒管理）

## 說明
管理 LINE Bot 的定時推送排程。使用者透過自然語言設定排程，由 LLM 語意判斷後呼叫此工具。

## 使用時機
- 使用者說「每天推送…」、「定時推送…」、「排程…」、「幫我設定提醒」
- 使用者說「每天早上X點推Y則新聞」
- 使用者說「取消/暫停/恢復推送」
- 使用者說「查看我的排程」
- 使用者說「10分鐘後提醒我…」

## 不適用場景
- 單純聊天或問答
- 檔案分析或生成
- 即時搜尋（非定時）

## 參數說明
- **action**（必填）：操作類型
- **task_type**（add 時必填）：推送內容類型
- **name**（add 時建議）：任務顯示名稱
- **cron**（add 時必填）：排程時間表達式
- **config**（add 時選填）：內容設定
- **task_id**（remove/pause/resume 時必填）：目標任務 ID
