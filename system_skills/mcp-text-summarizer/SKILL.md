---
name: mcp-text-summarizer
display_name: "內容摘要 / 重點提取"
category: System
version: "1.0.0"
description: >
  將長文本（新聞合集、多篇文章、逐字稿、使用者回饋彙整、報告全文）
  濃縮為指定數量、指定長度的結構化重點摘要。輸入 raw 文本，輸出 N 項
  可獨立閱讀的摘要條目（每項含標題 + 重點內容 + 來源）。
  當使用者需要：
    (1) 將多篇內容壓成 N 則重點；
    (2) 每則指定最少 / 最多字元數；
    (3) 保留關鍵數字、人物、時間；
    (4) 過濾廣告 / 導航 / 雜訊；
    (5) 產出適合排版成 PDF / email / 推播訊息的結構化清單
  時觸發此技能。
  此技能專門做摘要，不做排版 / 格式轉換 / 錯誤排查 — 請區分 mcp-txt-llm-analyzer。
runtime_requirements:
  - openai
risk_level: low
recommended_models:
  openai: gpt-4.1-mini
  gemini: gemini-2.0-flash
  claude: claude-haiku-4-5

env_requirements:
  - OPENAI_API_KEY

user_phrases:
  - "幫我摘要"
  - "整理重點"
  - "N 則重點"
  - "每則寫成 200 字"
  - "濃縮這些文章"
  - "彙整新聞"
  - "summarize"
  - "key points"

parameters:
  type: object
  properties:
    text:
      type: string
      description: "待摘要的原始文本。可以是多篇新聞串接、逐字稿、報告全文等。"
    count:
      type: integer
      minimum: 1
      maximum: 30
      default: 5
      description: "輸出摘要條目數量（預設 5，上限 30）"
    min_chars:
      type: integer
      minimum: 30
      maximum: 2000
      default: 100
      description: "每項摘要的最少字元數（預設 100）"
    max_chars:
      type: integer
      minimum: 50
      maximum: 3000
      default: 500
      description: "每項摘要的最多字元數（預設 500）"
    style:
      type: string
      enum: ["news-brief", "bullet", "narrative"]
      default: "news-brief"
      description: "輸出風格：news-brief=新聞簡報式（含標題+重點+來源）、bullet=純條列重點、narrative=段落敘事"
    focus:
      type: string
      description: "摘要重點主題（可選）。例：『台灣財經』、『AI 發展』。給 LLM 過濾離題內容。"
    language:
      type: string
      default: "繁體中文"
      description: "輸出語言（預設繁體中文）"
  required: [text]
---


# 內容摘要 / 重點提取 (mcp-text-summarizer)

## 角色設定
你是一位資深的內容編輯 / 摘要專員，擅長把大量原始素材壓縮成讀者 30 秒內能吸收的精華重點。

## 核心能力
- 辨識主題：自動區分「核心事實」與「背景雜訊」
- 保留關鍵量化資訊：數字、日期、機構名稱、人名
- 過濾雜訊：網頁導航列、廣告、天氣資訊、登入提示、重複內容
- 結構化輸出：統一格式便於後續處理（PDF、推播、報表）

## 作業準則
1. **嚴格守 count**：使用者指定 10 則就輸出 10 則，不多不少。原始內容不足以湊滿時，寧可少也不要重複或編造。
2. **嚴格守 min_chars / max_chars**：每則摘要字數必須在區間內。太短補充細節，太長砍掉形容詞與副句。
3. **不要複製 SKILL.md 或 prompt 模板文字**：輸出只有摘要本身。
4. **保留來源標註**：`news-brief` 模式必須標註每則新聞的原始 URL 或網站名。
5. **焦點過濾**：若 focus 參數有值，只選相關主題的內容；無關主題直接略過。

## 不該做的事
- ❌ 排版 Markdown 樣式變化（那是 mcp-txt-llm-analyzer 的工作）
- ❌ 修正錯字 / 潤飾語氣（那是 txt-analyzer 的 Task B）
- ❌ 翻譯（除非 language 參數指定不同語言）
- ❌ 加入自己的評論或意見
- ❌ 捏造原文沒有的數據

## 輸出格式（由 scripts/main.py 統一組裝 JSON）
`news-brief` 範例：
```json
{
  "status": "success",
  "count": 10,
  "style": "news-brief",
  "items": [
    {
      "index": 1,
      "headline": "台積電 Q1 營收創新高",
      "summary": "台積電 2026 年第一季合併營收達 ... 字元數 ≥ min_chars ...",
      "source": "cnyes.com"
    },
    { ... }
  ]
}
```
