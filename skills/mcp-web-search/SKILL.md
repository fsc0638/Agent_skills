---
name: mcp-web-search
version: 1.0.0
description: "全網搜尋與精準網頁內容擷取工具 (Tavily 驅動)。當需要獲取即時網路資訊或分析特定網址內容時使用。"
parameters:
  type: object
  properties:
    query:
      type: string
      description: "搜尋關鍵字。若有 target_url，此處可留空或作為輔助資訊。"
    target_url:
      type: string
      description: "選填。若使用者提供完整網址 (https://...)，請務必將其填送至此參數，以進行精準網頁讀取而非模糊搜尋。"
    search_depth:
      type: string
      enum: [basic, advanced]
      description: "搜尋深度。預設為 basic。只有使用者明確要求『深度研究』或『詳細分析』時才使用 advanced。"
    include_domains:
      type: array
      items:
        type: string
      description: "選填。限制搜尋範圍至特定網域清單，例如 ['udn.com', 'ltn.com.tw']。用於地區偏好或來源過濾。"
  required: []
---

# MCP Web Search (Tavily 驅動)

## 說明
此工具使用 Tavily API 進行即時網路搜尋或單一網頁內容提取。

## 核心規則
1. **網址優先**：如果使用者輸入的是一個連結，請務必將該連結放入 `target_url` 參數。
2. **防護機制**：後台已實作 Token 保護，每個網頁僅獲取前 2000 字元，避免超出上下文上限。
3. **來源標註**：回答時必須在文末附上資料來源，格式：`[1] 標題 - 網址`。

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
