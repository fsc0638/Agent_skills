---

name: xlsx
version: "1.0.0"
description: "全面的試算表建立、編輯與分析工具，支援公式、格式設定、數據分析與視覺化。當需要處理試算表（.xlsx、.xlsm、.csv、.tsv 等）時使用，包含：(1) 建立含公式與格式的新試算表，(2) 讀取或分析數據，(3) 在保留公式的情況下修改現有試算表，(4) 試算表中的數據分析與視覺化，(5) 重新計算公式。"
license: Proprietary. LICENSE.txt has complete terms
---

# 輸出要求

## 所有 Excel 檔案

### 零公式錯誤
- 每個 Excel 模型交付時必須**零公式錯誤**（#REF!、#DIV/0!、#VALUE!、#N/A、#NAME?）

### 保留現有範本（更新範本時）
- 修改檔案時，需仔細研究並**完全匹配**現有格式、樣式與規範
- 不得對具有既定樣式的檔案強制套用標準化格式
- 現有範本規範**永遠優先**於此指南

## 財務模型

### 色彩編碼標準
除非使用者或現有範本另有指示

#### 業界標準色彩規範
- **藍色文字（RGB: 0,0,255）**：硬碼輸入值，使用者在情境模擬中會變動的數字
- **黑色文字（RGB: 0,0,0）**：所有公式與計算結果
- **綠色文字（RGB: 0,128,0）**：從同一活頁簿其他工作表引用的連結
- **紅色文字（RGB: 255,0,0）**：連結到其他外部檔案的連結
- **黃色背景（RGB: 255,255,0）**：需要注意的關鍵假設或需要更新的儲存格

### 數字格式標準

#### 必要格式規則
- **年份**：格式化為文字字串（例如 "2024" 而非 "2,024"）
- **貨幣**：使用 $#,##0 格式；**務必**在欄位標題中標示單位（例如 "Revenue ($mm)"）
- **零值**：使用數字格式將所有零值顯示為 "-"，包括百分比（例如 "$#,##0;($#,##0);-"）
- **百分比**：預設使用 0.0% 格式（一位小數）
- **倍數**：估值倍數格式使用 0.0x（如 EV/EBITDA、P/E）
- **負數**：使用括號 (123) 而非減號 -123

### 公式建構規則

#### 假設值的放置
- 所有假設值（成長率、利潤率、倍數等）**必須**放在獨立的假設儲存格中
- 在公式中使用儲存格參照，而非硬碼數值
- 範例：使用 =B5*(1+$B$6) 而非 =B5*1.05

#### 公式錯誤預防
- 驗證所有儲存格參照是否正確
- 檢查範圍中的差一錯誤
- 確保所有預測期間的公式一致
- 以邊界情況測試（零值、負數）
- 確認沒有非預期的循環參照

#### 硬碼值的說明文件要求
- 在儲存格旁加上備註（如位於表格末端）。格式："Source: [系統/文件], [日期], [具體參照], [URL（如適用）]"
- 範例：
  - "Source: Company 10-K, FY2024, Page 45, Revenue Note, [SEC EDGAR URL]"
  - "Source: Company 10-Q, Q2 2025, Exhibit 99.1, [SEC EDGAR URL]"
  - "Source: Bloomberg Terminal, 8/15/2025, AAPL US Equity"
  - "Source: FactSet, 8/20/2025, Consensus Estimates Screen"

# XLSX 建立、編輯與分析

## 概覽

使用者可能要求建立、編輯或分析 .xlsx 檔案的內容。對於不同任務，有不同的工具與工作流程。

## 重要需求

**公式重新計算需要 LibreOffice**：可假設已安裝 LibreOffice，以使用 `recalc.py` 腳本重新計算公式值。腳本會在首次執行時自動配置 LibreOffice。

## 讀取與分析數據

### 使用 pandas 進行數據分析
對於數據分析、視覺化及基本操作，使用 **pandas** 提供強大的數據操作能力：

```python
import pandas as pd

# 讀取 Excel
df = pd.read_excel('file.xlsx')  # 預設：第一個工作表
all_sheets = pd.read_excel('file.xlsx', sheet_name=None)  # 以 dict 形式讀取所有工作表

# 分析
df.head()      # 預覽數據
df.info()      # 欄位資訊
df.describe()  # 統計數據

# 寫入 Excel
df.to_excel('output.xlsx', index=False)
```

## Excel 檔案工作流程

## 重要：使用公式，而非硬碼值

**務必使用 Excel 公式，而非在 Python 中計算數值後硬碼。** 這樣可確保試算表保持動態且可更新。

### ❌ 錯誤做法 — 硬碼計算值
```python
# 不好：在 Python 中計算後硬碼結果
total = df['Sales'].sum()
sheet['B10'] = total  # 硬碼為 5000

# 不好：在 Python 中計算成長率
growth = (df.iloc[-1]['Revenue'] - df.iloc[0]['Revenue']) / df.iloc[0]['Revenue']
sheet['C5'] = growth  # 硬碼為 0.15

# 不好：Python 計算平均值
avg = sum(values) / len(values)
sheet['D20'] = avg  # 硬碼為 42.5
```

### ✅ 正確做法 — 使用 Excel 公式
```python
# 好：讓 Excel 計算加總
sheet['B10'] = '=SUM(B2:B9)'

# 好：成長率用 Excel 公式
sheet['C5'] = '=(C4-C2)/C2'

# 好：使用 Excel 函數計算平均
sheet['D20'] = '=AVERAGE(D2:D19)'
```

這適用於所有計算——合計、百分比、比率、差值等。試算表應能在來源數據變更時自動重算。

## 常見工作流程
1. **選擇工具**：pandas 用於數據，openpyxl 用於公式 / 格式
2. **建立 / 載入**：建立新活頁簿或載入現有檔案
3. **修改**：新增 / 編輯數據、公式與格式
4. **儲存**：寫入檔案
5. **重新計算公式（使用公式時為必要步驟）**：使用 recalc.py 腳本
   ```bash
   python recalc.py output.xlsx
   ```
6. **驗證並修正錯誤**：
   - 腳本以 JSON 格式回傳錯誤詳情
   - 若 `status` 為 `errors_found`，查看 `error_summary` 了解錯誤類型與位置
   - 修正已識別的錯誤並再次重算
   - 常見需修正的錯誤：
     - `#REF!`：無效的儲存格參照
     - `#DIV/0!`：除以零
     - `#VALUE!`：公式中的數據類型錯誤
     - `#NAME?`：無法識別的公式名稱

### 建立新 Excel 檔案

```python
# 使用 openpyxl 處理公式與格式
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment

wb = Workbook()
sheet = wb.active

# 新增數據
sheet['A1'] = 'Hello'
sheet['B1'] = 'World'
sheet.append(['Row', 'of', 'data'])

# 新增公式
sheet['B2'] = '=SUM(A1:A10)'

# 格式設定
sheet['A1'].font = Font(bold=True, color='FF0000')
sheet['A1'].fill = PatternFill('solid', start_color='FFFF00')
sheet['A1'].alignment = Alignment(horizontal='center')

# 欄寬
sheet.column_dimensions['A'].width = 20

wb.save('output.xlsx')
```

### 編輯現有 Excel 檔案

```python
# 使用 openpyxl 保留公式與格式
from openpyxl import load_workbook

# 載入現有檔案
wb = load_workbook('existing.xlsx')
sheet = wb.active  # 或 wb['SheetName'] 指定特定工作表

# 處理多個工作表
for sheet_name in wb.sheetnames:
    sheet = wb[sheet_name]
    print(f"Sheet: {sheet_name}")

# 修改儲存格
sheet['A1'] = 'New Value'
sheet.insert_rows(2)  # 在第 2 列插入一列
sheet.delete_cols(3)  # 刪除第 3 欄

# 新增工作表
new_sheet = wb.create_sheet('NewSheet')
new_sheet['A1'] = 'Data'

wb.save('modified.xlsx')
```

## 重新計算公式

由 openpyxl 建立或修改的 Excel 檔案，公式以字串形式存在，尚未計算數值。使用提供的 `recalc.py` 腳本重新計算公式：

```bash
python recalc.py <excel_file> [timeout_seconds]
```

範例：
```bash
python recalc.py output.xlsx 30
```

此腳本：
- 首次執行時自動設定 LibreOffice 巨集
- 重新計算所有工作表中的所有公式
- 掃描所有儲存格中的 Excel 錯誤（#REF!、#DIV/0! 等）
- 以 JSON 格式回傳詳細的錯誤位置與計數
- 可在 Linux 和 macOS 上運作

## 公式驗證清單

快速確認公式正確運作的檢查項目：

### 基本驗證
- [ ] **測試 2-3 個範例參照**：在建立完整模型前，驗證它們是否拉取正確數值
- [ ] **欄位對應**：確認 Excel 欄位是否正確（例如第 64 欄 = BL，而非 BK）
- [ ] **列偏移**：記得 Excel 列數以 1 為基底（DataFrame 第 5 列 = Excel 第 6 列）

### 常見陷阱
- [ ] **NaN 處理**：使用 `pd.notna()` 檢查空值
- [ ] **最右側欄位**：FY 數據通常在第 50+ 欄
- [ ] **多重匹配**：搜尋所有出現位置，而非只有第一個
- [ ] **除以零**：在公式中使用 `/` 前先檢查分母（#DIV/0!）
- [ ] **錯誤參照**：驗證所有儲存格參照指向預期的儲存格（#REF!）
- [ ] **跨工作表參照**：使用正確格式（Sheet1!A1）連結工作表

### 公式測試策略
- [ ] **從小做起**：在廣泛套用前，先對 2-3 個儲存格測試公式
- [ ] **驗證相依性**：確認公式中所有被參照的儲存格都存在
- [ ] **測試邊界情況**：包含零值、負數和極大數值

### 解析 recalc.py 輸出
腳本以 JSON 格式回傳錯誤詳情：
```json
{
  "status": "success",           // 或 "errors_found"
  "total_errors": 0,              // 總錯誤數
  "total_formulas": 42,           // 檔案中的公式數量
  "error_summary": {              // 僅在發現錯誤時存在
    "#REF!": {
      "count": 2,
      "locations": ["Sheet1!B5", "Sheet1!C10"]
    }
  }
}
```

## 最佳實踐

### 函式庫選擇
- **pandas**：最適合數據分析、批量操作與簡單數據匯出
- **openpyxl**：最適合複雜格式設定、公式與 Excel 特有功能

### 使用 openpyxl
- 儲存格索引以 1 為基底（row=1, column=1 代表儲存格 A1）
- 使用 `data_only=True` 讀取已計算的數值：`load_workbook('file.xlsx', data_only=True)`
- **警告**：若以 `data_only=True` 開啟後儲存，公式將被數值取代且永久遺失
- 大型檔案：讀取時使用 `read_only=True`，寫入時使用 `write_only=True`
- 公式會保留但不會計算——使用 recalc.py 更新數值

### 使用 pandas
- 指定數據類型以避免推斷問題：`pd.read_excel('file.xlsx', dtype={'id': str})`
- 大型檔案讀取特定欄位：`pd.read_excel('file.xlsx', usecols=['A', 'C', 'E'])`
- 正確處理日期：`pd.read_excel('file.xlsx', parse_dates=['date_column'])`

## 程式碼風格指南
**重要**：為 Excel 操作生成 Python 程式碼時：
- 撰寫簡潔的 Python 程式碼，不含不必要的註釋
- 避免冗長的變數名稱與多餘的操作
- 避免不必要的 print 陳述式

**對於 Excel 檔案本身**：
- 在具有複雜公式或重要假設的儲存格中加入備註
- 為硬碼值記錄數據來源
- 包含關鍵計算與模型各節的說明