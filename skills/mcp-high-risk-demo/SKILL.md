---
name: mcp-high-risk-demo
provider: mcp
version: 1.0.0
runtime_requirements: []
risk_level: high
risk_description: 此技能為 Phase 3 授權攔截測試用途。模擬高風險操作（刪除臨時檔案），需使用者授權後才可執行。
description: >
  [TEST] Phase 3 高風險授權攔截測試技能。
  當使用者要求「執行高風險測試」或「demo高風險」時觸發此技能。
parameters:
  type: object
  properties:
    target:
      type: string
      description: 模擬操作目標說明（僅測試用，不會實際刪除任何東西）
  required: []
---

# MCP High-Risk Demo（Phase 3 測試技能）

## 說明
此技能專用於測試 Phase 3 的高風險授權攔截機制（Auth Modal）。

## 行為
執行後會印出一段模擬訊息，**不會**實際執行任何危險操作。
