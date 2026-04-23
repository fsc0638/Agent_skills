---
name: mcp-web-search
skillk_id: SkillK_EfhXruaQ2sGCoexdp2wc
display_name: "網路搜尋"
category: System
version: "1.0.0"
description: >
  全網搜尋與精準網頁內容擷取工具 (Tavily 驅動)。當需要獲取即時網路資訊或分析特定網址內容時使用。
runtime_requirements: []
risk_level: high
recommended_models:
  openai: gpt-4.1-nano
  gemini: gemini-2.0-flash
  claude: claude-haiku-4-5
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