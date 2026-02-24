---

name: brand-guidelines
version: "1.0.0"
description: 管理研發組專案的 CIS (Corporate Identity System) 品牌設計規範。包含官方顏色（深邃藍、活力橘）、背景色調與設計意圖。在進行任何 UI 設計、前端開發或畫面美化任務時，必須讀取此規範以維持視覺一致性。
license: Complete terms in LICENSE.txt
---

# 研發組專案 CIS 品牌設計規範

## 核心設計概念

本專案採用「專業與活力並存」的設計語言，主要色調以深邃藍代表研發實力與技術穩定，活力橘代表自動化創新與正能量。

**關鍵字**: branding, CIS, UI design, color palette, R&D Brand, 研發組配色, 視覺規範, 前端開發樣式

## 品牌色彩 (Brand Colors)

### 1. 核心企業色
- **深邃藍 (Brand Blue)**: `#003366`
  - *設計意圖*: 用於標題、品牌 Logo、導覽列背景等需要穩定感的區域。
  - *Hover 效果*: `#002244`
- **活力橘 (Brand Orange)**: `#FF6600`
  - *設計意圖*: 用於關鍵行動按鈕 (CTA)、重要通知、警示提示。
  - *Hover 效果*: `#E65C00`

### 2. 環境與背景色
- **主要背景 (White Dashboard)**: `#FFFFFF` (純白)
- **次要背景 (Sectioning)**: `#F9FAFB` (極淺灰，用於區分不同卡片或區塊)
- **邊框色彩**: `#E5E7EB`

### 3. 文字色調
- **文字主色**: `#111827` (接近黑色的深灰，確保高閱讀對比)
- **文字副色**: `#4B5563`
- **文字靜止/提示**: `#9CA3AF`

## 字體規範 (Typography)

- **主體字形**: `'Inter', 'PingFang TC', -apple-system, sans-serif`
- **設計層級**: 
  - 標題加粗 (Bold/ExtraBold) 使用深邃藍。
  - 內文保持適中行高 (Line-height: 1.5)。

## 執行指令 (Directives)

當 User 要求「設計 UI」、「美化頁面」或「製作組件」時：
1. **必須讀取** 本技能中的規範。
2. **優先調用** `References/cis_standard.md` 查看詳細色值。
3. **強制執行**：產出的 CSS 必須使用上述定義的值。
