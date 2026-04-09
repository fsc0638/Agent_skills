---
name: mcp-meeting-to-notion
provider: mcp
version: "1.0.0"
description: >
  會議紀錄自動上傳 Notion 工具。將會議逐字稿經過 4 階段 AI 處理 （文本清洗→人員歸戶→Schema映射→品質檢核），自動產出結構化 ToDo 並上傳至 Notion 資料庫。支援 Upsert（重複項目自動更新）。 當使用者提到「會議紀錄上傳」「逐字稿上傳Notion」「會議待辦上傳」 「meeting to notion」「會議重點上傳」時觸發此技能。 本技能為獨立完整的 Pipeline，不依賴其他技能。
runtime_requirements: [requests, openai]
risk_level: high
risk_description: >
  此技能會將結構化資料寫入 Notion 資料庫（建立或更新頁面），屬於外部系統寫入操作。 執行後資料將出現在 Notion 工作區中，使用者可於 Notion 上自行修改。
execution_timeout: 120
---

# 會議紀錄自動上傳 Notion (mcp-meeting-to-notion)

## 說明

此技能為獨立完整的 4-Phase AI Pipeline，將會議逐字稿自動轉化為結構化的 Notion ToDo 項目。

## 處理流程

```
逐字稿輸入
  → Phase 1: 文本清洗（去噪 + 語意重組 + 翻譯）
  → Phase 2: 人員歸戶（人名識別 + 部門映射 + 角色區分）
  → Phase 3: Schema 映射（Notion 欄位對應 + 專案前綴 + 時間推論）
  → Phase 4: 品質檢核（格式驗證 + 垃圾詞掃描 + 欄位合法性）
  → Notion Upload（Upsert: 重複更新 / 新建）
```

## 環境變數需求

| 變數 | 說明 |
|------|------|
| `NOTION_TOKEN` | Notion Integration Token（必要） |
| `NOTION_DATABASE_ID` | 目標 Notion 資料庫 ID（必要） |
| `OPENAI_API_KEY` | Phase 1-3 LLM 呼叫（已有） |

## 輸出格式

```json
{
  "status": "success",
  "total": 15,
  "created": 12,
  "updated": 3,
  "errors": [],
  "items": [
    {
      "ToDo": "完成跨境合作合約審閱與法律風險評估",
      "專案": ["Y200_20260323 跨國供應鏈合作"],
      "負責人": ["范書愷"],
      "來源": ["外部合作"],
      "狀態": "未開始",
      "_action": "created"
    }
  ]
}
```
