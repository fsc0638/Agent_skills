---
name: mcp-sample-converter
provider: mcp
version: 0.1.0
runtime_requirements: []
description: >
  文字格式轉換工具。接受輸入字串與目標格式，
  然後回傳轉換後的結果。支援的轉換方式：文字轉大寫、
  文字轉小寫、文字轉標題格式、字數分析。
  當使用者要求轉換、變形或分析文字內容時，使用此工具。
parameters:
  type: object
  properties:
    input_text:
      type: string
      description: 要處理的文字內容。
    operation:
      type: string
      description: 操作類型，擇一使用："uppercase"、"lowercase"、"titlecase"、"wordcount"。
  required: [input_text, operation]
---

# MCP Sample Converter（文字格式轉換工具）

## 說明
此工具可在各種格式之間轉換文字，並提供基本文字分析功能。

## 使用方式（嚴格模式 / 低自由度）
- 輸入參數：
  - input_text（字串）：要處理的文字內容
  - operation（字串）：操作類型，擇一使用："uppercase"、"lowercase"、"titlecase"、"wordcount"
