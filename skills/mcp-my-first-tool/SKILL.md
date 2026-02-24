---
name: mcp-my-first-tool
provider: mcp
version: 0.1.0
runtime_requirements: []
description: >
  簡單的問候與回應工具。接受使用者名稱及選填訊息，
  並回傳附有目前時間戳記的個人化問候語。
  當使用者想測試系統或打聲招呼時，使用此工具。
parameters:
  type: object
  properties:
    name:
      type: string
      description: 使用者的姓名。
    message:
      type: string
      description: 要回傳的自訂訊息。
  required: [name]
---

# MCP My First Tool（第一個測試工具）

## 說明
用於端對端測試 UMA 管線的簡單問候工具。

## 使用方式（嚴格模式 / 低自由度）
- 輸入參數：
  - name（字串）：使用者的姓名
  - message（字串，選填）：要回傳的自訂訊息
