---

name: mcp-builder
version: "1.0.0"
description: 建立高品質 MCP（Model Context Protocol）伺服器的指南，讓 LLM 能透過精心設計的工具與外部服務互動。在建立 MCP 伺服器以整合外部 API 或服務時使用，無論是 Python（FastMCP）或 Node/TypeScript（MCP SDK）皆適用。
license: Complete terms in LICENSE.txt
---

# MCP 伺服器開發指南

## 概覽

建立 MCP（Model Context Protocol）伺服器，讓 LLM 能透過精心設計的工具與外部服務互動。MCP 伺服器的品質取決於其能在多大程度上幫助 LLM 完成真實世界的任務。

---

# 流程

## 🚀 高層次工作流程

建立高品質的 MCP 伺服器包含四個主要階段：

### 第 1 階段：深入研究與規劃

#### 1.1 理解現代 MCP 設計

**API 覆蓋範圍 vs. 工作流程工具：**
平衡全面的 API 端點覆蓋與專業化工作流程工具。工作流程工具對特定任務更方便，而全面覆蓋則讓代理有靈活性來組合操作。效能因客戶端而異——有些客戶端受益於結合基本工具的程式碼執行，而其他客戶端則更適合高層次工作流程。不確定時，優先考慮全面的 API 覆蓋。

**工具命名與可發現性：**
清晰、描述性的工具名稱幫助代理快速找到正確工具。使用一致的前綴（例如 `github_create_issue`、`github_list_repos`）和以動作為導向的命名。

**上下文管理：**
代理受益於簡潔的工具描述和過濾 / 分頁結果的能力。設計回傳聚焦、相關數據的工具。有些客戶端支援程式碼執行，可幫助代理有效過濾和處理數據。

**可操作的錯誤訊息：**
錯誤訊息應透過具體建議和後續步驟引導代理找到解決方案。

#### 1.2 研究 MCP 協定文件

**瀏覽 MCP 規格說明：**

從網站地圖開始找到相關頁面：`https://modelcontextprotocol.io/sitemap.xml`

然後以 `.md` 後綴取得 markdown 格式的特定頁面（例如 `https://modelcontextprotocol.io/specification/draft.md`）。

需要審查的關鍵頁面：
- 規格說明概覽和架構
- 傳輸機制（streamable HTTP、stdio）
- 工具、資源和提示定義

#### 1.3 研究框架文件

**建議技術堆疊：**
- **語言**：TypeScript（高品質 SDK 支援，以及在許多執行環境（如 MCPB）中的良好相容性。此外，AI 模型擅長生成 TypeScript 程式碼，受益於其廣泛使用、靜態型別和良好的語法檢查工具）
- **傳輸**：遠端伺服器使用 Streamable HTTP，採用無狀態 JSON（比有狀態會話和串流回應更易於擴展和維護）。本地伺服器使用 stdio。

**載入框架文件：**

- **MCP 最佳實踐**：[📋 查看最佳實踐](./reference/mcp_best_practices.md) — 核心指南

**TypeScript（建議）：**
- **TypeScript SDK**：使用 WebFetch 載入 `https://raw.githubusercontent.com/modelcontextprotocol/typescript-sdk/main/README.md`
- [⚡ TypeScript 指南](./reference/node_mcp_server.md) — TypeScript 模式和範例

**Python：**
- **Python SDK**：使用 WebFetch 載入 `https://raw.githubusercontent.com/modelcontextprotocol/python-sdk/main/README.md`
- [🐍 Python 指南](./reference/python_mcp_server.md) — Python 模式和範例

#### 1.4 規劃實作

**理解 API：**
審查服務的 API 文件，識別關鍵端點、驗證需求和數據模型。視需要使用網路搜尋和 WebFetch。

**工具選擇：**
優先考慮全面的 API 覆蓋。列出要實作的端點，從最常見的操作開始。

---

### 第 2 階段：實作

#### 2.1 設置專案結構

語言特定的設置指南請見：
- [⚡ TypeScript 指南](./reference/node_mcp_server.md) — 專案結構、package.json、tsconfig.json
- [🐍 Python 指南](./reference/python_mcp_server.md) — 模組組織、相依套件

#### 2.2 實作核心基礎設施

建立共用工具：
- 帶驗證的 API 客戶端
- 錯誤處理輔助函數
- 回應格式化（JSON/Markdown）
- 分頁支援

#### 2.3 實作工具

對每個工具：

**輸入結構（Schema）：**
- 使用 Zod（TypeScript）或 Pydantic（Python）
- 包含限制條件和清晰描述
- 在欄位描述中加入範例

**輸出結構（Schema）：**
- 盡可能定義 `outputSchema` 以獲得結構化數據
- 在工具回應中使用 `structuredContent`（TypeScript SDK 功能）
- 幫助客戶端理解和處理工具輸出

**工具描述：**
- 功能的簡潔摘要
- 參數描述
- 回傳型別結構

**實作：**
- 非同步 / await 用於 I/O 操作
- 具有可操作訊息的適當錯誤處理
- 在適用處支援分頁
- 使用現代 SDK 時同時回傳文字內容和結構化數據

**注解：**
- `readOnlyHint`：true/false
- `destructiveHint`：true/false
- `idempotentHint`：true/false
- `openWorldHint`：true/false

---

### 第 3 階段：審查與測試

#### 3.1 程式碼品質

審查：
- 無重複程式碼（DRY 原則）
- 一致的錯誤處理
- 完整的型別覆蓋
- 清晰的工具描述

#### 3.2 建置與測試

**TypeScript：**
- 執行 `npm run build` 驗證編譯
- 用 MCP Inspector 測試：`npx @modelcontextprotocol/inspector`

**Python：**
- 驗證語法：`python -m py_compile your_server.py`
- 用 MCP Inspector 測試

詳細測試方法和品質清單請見各語言特定指南。

---

### 第 4 階段：建立評估

實作 MCP 伺服器後，建立全面的評估來測試其有效性。

**載入 [✅ 評估指南](./reference/evaluation.md) 以獲得完整的評估指南。**

#### 4.1 理解評估目的

使用評估來測試 LLM 是否能有效使用您的 MCP 伺服器回答現實、複雜的問題。

#### 4.2 建立 10 個評估問題

建立有效評估時，依照評估指南中的流程：

1. **工具檢查**：列出可用工具並了解其功能
2. **內容探索**：使用唯讀操作探索可用數據
3. **問題生成**：建立 10 個複雜、真實的問題
4. **答案驗證**：自行解決每個問題以驗證答案

#### 4.3 評估要求

確保每個問題：
- **獨立**：不依賴其他問題
- **唯讀**：只需要非破壞性操作
- **複雜**：需要多次工具呼叫和深入探索
- **真實**：基於人們真正關心的實際使用場景
- **可驗證**：有單一、明確可透過字串比對驗證的答案
- **穩定**：答案不會隨時間改變

#### 4.4 輸出格式

建立具有以下結構的 XML 檔案：

```xml
<evaluation>
  <qa_pair>
    <question>找出關於以動物代號命名的 AI 模型發布的討論。有一個模型需要使用 ASL-X 格式的特定安全級別。那個以斑點野貓命名的模型，X 是多少？</question>
    <answer>3</answer>
  </qa_pair>
<!-- 更多 qa_pairs... -->
</evaluation>
```

---

# 參考檔案

## 📚 文件函式庫

開發過程中依需要載入這些資源：

### 核心 MCP 文件（首先載入）
- **MCP 協定**：從 `https://modelcontextprotocol.io/sitemap.xml` 開始，然後以 `.md` 後綴取得特定頁面
- [📋 MCP 最佳實踐](./reference/mcp_best_practices.md) — 通用 MCP 指南，包含：
  - 伺服器和工具命名規範
  - 回應格式指南（JSON vs Markdown）
  - 分頁最佳實踐
  - 傳輸選擇（streamable HTTP vs stdio）
  - 安全和錯誤處理標準

### SDK 文件（第 1/2 階段載入）
- **Python SDK**：從 `https://raw.githubusercontent.com/modelcontextprotocol/python-sdk/main/README.md` 取得
- **TypeScript SDK**：從 `https://raw.githubusercontent.com/modelcontextprotocol/typescript-sdk/main/README.md` 取得

### 語言特定實作指南（第 2 階段載入）
- [🐍 Python 實作指南](./reference/python_mcp_server.md) — 完整的 Python/FastMCP 指南，包含：
  - 伺服器初始化模式
  - Pydantic 模型範例
  - 使用 `@mcp.tool` 的工具註冊
  - 完整的運作範例
  - 品質清單

- [⚡ TypeScript 實作指南](./reference/node_mcp_server.md) — 完整的 TypeScript 指南，包含：
  - 專案結構
  - Zod schema 模式
  - 使用 `server.registerTool` 的工具註冊
  - 完整的運作範例
  - 品質清單

### 評估指南（第 4 階段載入）
- [✅ 評估指南](./reference/evaluation.md) — 完整的評估建立指南，包含：
  - 問題建立指南
  - 答案驗證策略
  - XML 格式規格
  - 範例問答
  - 使用提供的腳本執行評估
