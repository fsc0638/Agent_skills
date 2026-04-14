---
name: mcp-transcribe
display_name: "音訊逐字稿工具"
version: "1.0.0"
description: >
  音訊逐字稿工具。將音訊檔案（MP3、WAV、M4A、FLAC 等）轉換為文字逐字稿，使用 Gemini API 音訊理解能力。當使用者需要將錄音、語音備忘錄或任何音訊檔案轉換為文字時使用。【必填參數】呼叫此工具時必須傳入 file_path 參數，值為音訊檔案的完整絕對路徑（例如：C:/path/to/audio.m4a）。請從使用者訊息中擷取檔案路徑後傳入。
runtime_requirements: [google.genai]
risk_level: low
execution_timeout: 120
---

# Transcribe（音訊逐字稿）

## 說明
此工具呼叫 Gemini API 將音訊檔案轉換為文字逐字稿。
- 檔案 **≤ 15 MB**：以 base64 inline 方式傳送
- 檔案 **> 15 MB**：透過 Gemini File API 上傳（支援最大 2 GB）

## 使用時機
- 使用者提供音訊檔案路徑，要求轉換為文字
- 使用者說「幫我轉逐字稿」、「把這個錄音轉成文字」等

## 參數說明
- **file_path**（必填）：音訊檔案的路徑

## 輸出
工具執行後回傳 JSON：
```json
{
  "status": "success",
  "transcript": "逐字稿內容...",
  "file_path": "/path/to/audio.mp3",
  "message": "逐字稿已完成"
}
```

## 回應原則
- 直接將 `transcript` 內容呈現給使用者
- 若使用者有需要，可建議將逐字稿儲存為文字檔
- 保留原始音訊語言，不自動翻譯