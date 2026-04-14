---

name: mcp-image-generator
display_name: "圖像生成"
provider: mcp
version: "1.0.0"
description: >
  AI 圖片生成工具。根據使用者的自然語言描述，呼叫 OpenAI gpt-image-1 模型產出插圖或概念圖。 當使用者要求「畫一張…」、「生成圖片…」、「製作插圖…」等帶有視覺創作意圖的指令時，必須使用此工具。 注意：此工具用於 AI 創意插圖生成，若使用者需要的是數據圖表（長條圖、折線圖、圓餅圖等）， 請改用 mcp-python-executor 搭配 matplotlib 繪製。
runtime_requirements: [openai]
risk_level: low
execution_timeout: 120
recommended_models:
  openai: gpt-4.1-nano
  gemini: gemini-2.0-flash
  claude: claude-haiku-4-5
---


# MCP Image Generator（AI 圖片生成工具）

## 說明
此技能呼叫 OpenAI `gpt-image-1` 模型，根據文字描述生成高品質圖片。

## 使用時機
- 使用者要求繪製插圖、概念圖、Logo、海報等創意圖片
- 使用者說「畫」、「生成圖片」、「做一張圖」等

## 不適用場景
- 數據圖表（長條圖、圓餅圖等）→ 請用 `mcp-python-executor` + matplotlib
- 文件排版（Word、PDF）→ 請用對應的文件工具

## 參數說明
- **prompt**（必填）：英文提示詞。若使用者以中文描述，請翻譯為英文。
- **size**（選填）：圖片尺寸，預設 `1024x1024`
- **quality**（選填）：品質等級，預設 `medium`

## 輸出
工具執行後會回傳 JSON：
```json
{
  "status": "success",
  "image_url": "{BASE_URL}/images/{filename}.png",
  "filename": "{filename}.png",
  "message": "圖片已生成"
}
```
請將 `image_url` 回傳給使用者，LINE 平台會自動以圖片訊息顯示。