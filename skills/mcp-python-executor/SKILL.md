---
name: mcp-python-executor
provider: mcp
version: 1.0.0
runtime_requirements: []
description: >
  強大的 Python 程式碼執行工具。強制規定：不得只在文字中提供程式碼；當使用者要求執行計算、驗證結果或執行腳本時，必須使用此工具實際執行程式碼。
  LLM（大腦）須提供原始 Python 程式碼，並以此工具作為與系統邏輯互動的主要方式。
parameters:
  type: object
  properties:
    code:
      type: string
      description: 要執行的完整 Python 程式碼。使用 print() 輸出結果。
  required: [code]
---

# MCP Python Executor（Python 執行工具）

## 說明
此技能作為 LLM 推理與實際執行之間的直接橋樑。
LLM 可以撰寫腳本來解決使用者的問題，此工具將負責執行它。

## 使用方式
- **code（字串）**：要執行的完整 Python 程式碼。
  - 使用 `print()` 輸出結果——輸出內容將回傳給 LLM。
  - 允許使用標準函式庫。
