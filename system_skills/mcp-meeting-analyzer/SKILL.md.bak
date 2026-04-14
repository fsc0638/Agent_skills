---
name: mcp-meeting-analyzer
provider: mcp
version: 1.0.0
description: >
  會議逐字稿結構化分析工具。將會議逐字稿經過 AI 處理
  （文本清洗→人員歸戶），產出乾淨書面文本與組織識別資料。
  輸出可直接回覆使用者，或搭配 mcp-notion-crud 寫入 Notion。
  當使用者提到「整理會議紀錄」「摘要逐字稿」「會議重點」
  「歸納會議內容」「整理這段文字」「會議摘要」「meeting summary」
  「幫我整理會議」「分析會議內容」時觸發此技能。
  【重要】呼叫此技能時，必須將使用者訊息中的完整逐字稿或會議記錄文字
  作為 transcript 參數傳入，不可省略或留空。
parameters:
  type: object
  properties:
    transcript:
      type: string
      description: "會議逐字稿內容（純文字）。可為使用者直接輸入的文字、或從上傳檔案/mcp-transcribe 中提取的內容。"
    language:
      type: string
      description: "目標輸出語言，預設繁體中文"
      default: "繁體中文"
    department_code:
      type: string
      description: "選填。指定責任部門代碼（如 Y200、T251），會覆蓋 AI 自動判斷結果"
  required: [transcript]
runtime_requirements: [openai]
estimated_tokens: 800
execution_timeout: 60
risk_level: low
---

# 會議逐字稿結構化分析工具 (mcp-meeting-analyzer)

## 說明

此技能將會議逐字稿進行 2 階段 AI 處理，產出結構化的中間產物。
不綁定任何外部系統，輸出可供 LLM 直接組織為可讀文字回覆使用者，
或由 LLM 串接 mcp-notion-crud 寫入 Notion。

## 處理流程

```
逐字稿輸入
  → Phase 1: 文本清洗（去噪 + 語意重組 + 翻譯）
  → Phase 2: 人員歸戶（人名識別 + 部門映射 + 角色區分）
  → 結構化 JSON 輸出
```

## 環境變數需求

| 變數 | 說明 |
|------|------|
| `OPENAI_API_KEY` | Phase 1-2 LLM 呼叫（必要） |

## 輸出格式

```json
{
  "status": "success",
  "cleaned_text": "Phase 1 清洗後的書面文本...",
  "org_data": {
    "識別人員": ["范書愷", "趙嘉浩"],
    "負責人": ["范書愷"],
    "執行人": ["趙嘉浩"],
    "職稱或單位": ["研發中心"],
    "責任部門": "研發中心-開發處",
    "責任部門代碼": "Y200"
  },
  "metadata": {
    "language": "繁體中文",
    "department_code": "Y200"
  }
}
```

## 下游串接

LLM 可根據使用者意圖決定如何使用輸出：
1. **直接回覆**：將 cleaned_text + org_data 組織成可讀文字
2. **寫入 Notion**：呼叫 mcp-notion-crud 的 create_batch action，
   傳入 cleaned_text 和 org_data_json
