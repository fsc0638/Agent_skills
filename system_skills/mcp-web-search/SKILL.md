---
name: mcp-web-search
skillk_id: SkillK_EfhXruaQ2sGCoexdp2wc
display_name: "網路搜尋"
category: System
version: "1.0.0"
description: >
  全網搜尋與精準網頁內容擷取工具 (Tavily 驅動)。當需要獲取即時網路資訊或分析特定網址內容時使用。
runtime_requirements: []
risk_level: low
recommended_models:
  openai: gpt-4.1-nano
  gemini: gemini-2.0-flash
  claude: claude-haiku-4-5

# ── v2 Schema 欄位（Phase 1 整合報告 §4.2）──
env_requirements:
  - TAVILY_API_KEY
user_phrases:
  - "幫我查一下"
  - "搜尋關於"
  - "找找看"
  - "上網查"
  - "新聞"
  - "最新資訊"
  - "這個網址寫什麼"
  - "抓這個頁面"

input_schema:
  query:
    type: string
    required: false
    description: "搜尋關鍵字。若提供 target_url 則此欄位可省略。"
  target_url:
    type: string
    required: false
    description: "指定要擷取內容的網址（覆寫 query，直接擷取該網頁）"
  search_depth:
    type: string
    required: false
    description: "搜尋深度：'basic'（預設，快速）或 'advanced'（更深入）"
  max_results:
    type: integer
    required: false
    description: "回傳最大結果數（預設 3）"
  include_domains:
    type: array
    required: false
    description: "限制只搜尋這些網域（例：['udn.com','ltn.com.tw']）"

output_schema:
  search_result:
    type: string
    description: "格式化後的搜尋結果，含標題、URL、內文摘要"

# (legacy) parameters — kept for backward compat with older loaders
parameters:
  type: object
  properties:
    query:
      type: string
      description: "搜尋關鍵字。若提供 target_url 則此欄位可省略。"
    target_url:
      type: string
      description: "指定要擷取內容的網址（覆寫 query，直接擷取該網頁）"
    search_depth:
      type: string
      description: "搜尋深度：'basic'（預設，快速）或 'advanced'（更深入）"
    max_results:
      type: integer
      description: "回傳最大結果數（預設 3）"
    include_domains:
      type: array
      description: "限制只搜尋這些網域（例：['udn.com','ltn.com.tw']）"
  required: []
---

# MCP Web Search (Tavily 驅動)

## 說明
此工具使用 Tavily API 進行即時網路搜尋或單一網頁內容提取。
 
## 核心規則
1. **網址優先**：如果使用者輸入的是一個連結，請務必將該連結放入 `target_url` 參數。
2. **防護機制**：後台已實作 Token 保護，每個網頁僅獲取前 2000 字元，避免超出上下文上限。
3. **來源標註**：回答時必須在文末附上資料來源，格式：`[1] 標題 - 網址`。

## 匯出資訊排版規則
請嚴格遵循以下格式匯出：
1. 先總結搜尋到的所有資訊的重點，不超過100字
2. 每條項目都要是各自一個段落
3. 完整標題
4. 重點內容請具體且詳細
5. 有具體可直接連結到正確資訊來源，請附上網址

## 使用範例

### 1. 一般全網搜尋
```python
# 呼叫工具並傳入 query
# AI 腦袋會收到格式化後的 [1] Title: ... URL: ... Content: ...
```

### 2. 精準網址讀取
```python
# 當使用者說「幫我總結這個網頁：https://example.com/news」
# 呼叫工具：target_url="https://example.com/news"
```