---

name: web-artifacts-builder
version: "1.0.0"
description: 使用現代前端網頁技術（React、Tailwind CSS、shadcn/ui）建立精緻多元件 Claude.ai HTML 成品的工具套件。適用於需要狀態管理、路由或 shadcn/ui 元件的複雜成品——不適用於簡單的單檔案 HTML/JSX 成品。
license: Complete terms in LICENSE.txt
---

# Web Artifacts Builder（網頁成品建構器）

要建立強大的前端 Claude.ai 成品，請依照以下步驟：
1. 使用 `scripts/init-artifact.sh` 初始化前端專案
2. 編輯生成的程式碼來開發成品
3. 使用 `scripts/bundle-artifact.sh` 將所有程式碼打包成單一 HTML 檔案
4. 向使用者展示成品
5. （選填）測試成品

**技術堆疊**：React 18 + TypeScript + Vite + Parcel（打包）+ Tailwind CSS + shadcn/ui

## 設計與樣式指南

非常重要：為避免常見的「AI 感」美學，不要過度使用置中版型、紫色漸層、統一的圓角和 Inter 字體。

## 快速開始

### 步驟 1：初始化專案

執行初始化腳本以建立新的 React 專案：
```bash
bash scripts/init-artifact.sh <project-name>
cd <project-name>
```

這將建立一個完整配置的專案，包含：
- ✅ React + TypeScript（via Vite）
- ✅ Tailwind CSS 3.4.1 及 shadcn/ui 主題系統
- ✅ 路徑別名（`@/`）配置完成
- ✅ 預先安裝 40+ 個 shadcn/ui 元件
- ✅ 包含所有 Radix UI 相依套件
- ✅ Parcel 打包配置完成（via .parcelrc）
- ✅ Node 18+ 相容性（自動偵測並固定 Vite 版本）

### 步驟 2：開發成品

要建立成品，請編輯生成的檔案。具體指引請見下方的**常見開發任務**。

### 步驟 3：打包成單一 HTML 檔案

要將 React 應用程式打包成單一 HTML 成品：
```bash
bash scripts/bundle-artifact.sh
```

這將建立 `bundle.html` — 一個包含所有 JavaScript、CSS 和相依套件的自包含成品，可直接在 Claude 對話中作為成品分享。

**需求**：專案根目錄中必須有 `index.html`。

**腳本執行內容**：
- 安裝打包相依套件（parcel、@parcel/config-default、parcel-resolver-tspaths、html-inline）
- 建立帶路徑別名支援的 `.parcelrc` 配置
- 用 Parcel 建置（無 source maps）
- 用 html-inline 將所有資產內嵌到單一 HTML 中

### 步驟 4：與使用者分享成品

最後，在對話中與使用者分享打包好的 HTML 檔案，讓他們可以作為成品查看。

### 步驟 5：測試 / 視覺化成品（選填）

注意：此為完全選填的步驟，只在必要或被要求時執行。

要測試 / 視覺化成品，請使用可用工具（包括其他技能或內建的 Playwright 或 Puppeteer 工具）。一般情況下，避免事先測試成品，因為這會增加請求與完成成品之間的延遲。如有需要或發現問題，在展示成品後再測試。

## 參考

- **shadcn/ui 元件**：https://ui.shadcn.com/docs/components