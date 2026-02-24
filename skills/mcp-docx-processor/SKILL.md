---

name: docx
version: "1.0.0"
description: "全面的文件建立、編輯與分析工具，支援追蹤修訂、備註、格式保留和文字提取。當 AI 需要處理專業文件（.docx 檔案）以進行：(1) 建立新文件、(2) 修改或編輯內容、(3) 處理追蹤修訂、(4) 新增備註，或任何其他文件任務時使用。"
license: Proprietary. LICENSE.txt has complete terms
---

# DOCX 建立、編輯與分析

## 概覽

使用者可能要求建立、編輯或分析 .docx 檔案的內容。一個 .docx 檔案本質上是一個包含 XML 檔案和其他資源的 ZIP 壓縮檔，可供讀取或編輯。您有不同的工具和工作流程可用於不同的任務。

## 工作流程決策樹

### 讀取 / 分析內容
使用下方的「文字提取」或「直接存取 XML」段落

### 建立新文件
使用「建立新 Word 文件」工作流程

### 編輯現有文件
- **自己建立的文件 + 簡單的修改**
  使用「基本 OOXML 編輯」工作流程

- **他人建立的文件**
  使用 **「紅線標記（Redlining）工作流程」**（推薦的預設選項）

- **法律、學術、商業或政府文件**
  使用 **「紅線標記（Redlining）工作流程」**（強制要求）

## 讀取與分析內容

### 文字提取
如果您只需要讀取文件的文字內容，應使用 pandoc 將文件轉換為 markdown。Pandoc 提供了對保留文件結構的出色支援，且可以顯示追蹤修訂：

```bash
# 將文件轉換為 markdown 並顯示追蹤修訂
pandoc --track-changes=all path-to-file.docx -o output.md
# 選項：--track-changes=accept/reject/all
```

### 直接存取 XML
以下情況需要直接存取 XML：備註、複雜格式、文件結構、嵌入媒體和中繼資料。對於任何這些功能，您需要解開文件並讀取其原始 XML 內容。

#### 解開檔案
`python ooxml/scripts/unpack.py <office_file> <output_directory>`

#### 關鍵檔案結構
* `word/document.xml` - 主要文件內容
* `word/comments.xml` - 在 document.xml 中被引用的備註
* `word/media/` - 嵌入的圖片和媒體檔案
* 追蹤修訂使用 `<w:ins>`（插入）和 `<w:del>`（刪除）標籤

## 建立新 Word 文件

從頭開始建立新的 Word 文件時，請使用 **docx-js**，它允許您使用 JavaScript/TypeScript 建立 Word 文件。

### 工作流程
1. **強制要求 - 閱讀整個檔案**：從頭到尾完整閱讀 [`docx-js.md`](docx-js.md)（約 500 行）。**閱讀此檔案時，絕不要設定任何範圍限制。** 在進行文件建立之前，完整閱讀檔案內容以取得詳細語法、重要的格式化規則和最佳實踐。
2. 使用 Document、Paragraph、TextRun 等元件建立 JavaScript/TypeScript 檔案（您可以假設所有相依套件都已安裝，若否，請參閱下方的相依套件段落）
3. 使用 Packer.toBuffer() 匯出為 .docx

## 編輯現有 Word 文件

編輯現有 Word 文件時，請使用 **Document 函式庫**（一個用於 OOXML 操作的 Python 函式庫）。該函式庫會自動處理基礎設施設定並提供文件操作的方法。對於複雜的情境，您可以透過函式庫直接存取底層的 DOM。

### 工作流程
1. **強制要求 - 閱讀整個檔案**：從頭到尾完整閱讀 [`ooxml.md`](ooxml.md)（約 600 行）。**閱讀此檔案時，絕不要設定任何範圍限制。** 完整閱讀檔案內容以了解 Document 函式庫的 API 以及用於直接編輯文件檔案的 XML 模式。
2. 解開文件：`python ooxml/scripts/unpack.py <office_file> <output_directory>`
3. 使用 Document 函式庫建立並執行 Python 腳本（請參閱 ooxml.md 中的「Document 函式庫」段落）
4. 打包最終文件：`python ooxml/scripts/pack.py <input_directory> <office_file>`

Document 函式庫既提供常用操作的高層次方法，也提供複雜情境的直接 DOM 存取。

## 文件審查的紅線標記（Redlining）工作流程

此工作流程允許您在 OOXML 中實作之前，使用 markdown 規劃全面的追蹤修訂。**關鍵提示**：為確保追蹤修訂完整無缺，您必須有系統地實作「所有」變更。

**分批策略**：將相關變更分組，每批 3-10 個變更。這使除錯既可管理又能保持效率。測試每一批變更後再進入下一批。

**原則：極簡、精確的編輯**
在實作追蹤修訂時，只標記實際更改的文字。重複未更改的文字會使編輯更難以審查，而且顯得不專業。將替換內容分解為：[未更改的文字] + [刪除的部分] + [插入的部分] + [未更改的文字]。保留未更改文字原始 run（`<w:r>`）的 RSID：從原始檔案提取 `<w:r>` 元素並重複使用。

範例 - 將句子中的「30 days」改為「60 days」：
```python
# 錯誤 - 替換了整個句子
'<w:del><w:r><w:delText>The term is 30 days.</w:delText></w:r></w:del><w:ins><w:r><w:t>The term is 60 days.</w:t></w:r></w:ins>'

# 正確 - 只標記有變更的部分，保留未更改文字的原始 <w:r>
'<w:r w:rsidR="00AB12CD"><w:t>The term is </w:t></w:r><w:del><w:r><w:delText>30</w:delText></w:r></w:del><w:ins><w:r><w:t>60</w:t></w:r></w:ins><w:r w:rsidR="00AB12CD"><w:t> days.</w:t></w:r>'
```

### 追蹤修訂工作流程

1. **取得 markdown 表示**：將文件轉換為 markdown 並保留追蹤修訂：
   ```bash
   pandoc --track-changes=all path-to-file.docx -o current.md
   ```

2. **識別並分組變更**：審查文件並識別出「所有」需要的變更，將它們有邏輯地分組：

   **定位方法**（在 XML 中尋找變更）：
   - 章節 / 標題編號（例如「Section 3.2」、「Article IV」）
   - 如果有編號的段落識別碼
   - 帶有獨特周圍文字的 Grep 模式
   - 文件結構（例如「第一段」、「簽名欄」）
   - **不要使用 markdown 的行號** - 它們無法對應到 XML 結構

   **批次組織**（每批聚合 3-10 個相關變更）：
   - 依章節：「第 1 批：Section 2 修改」、「第 2 批：Section 5 更新」
   - 依類型：「第 1 批：日期修正」、「第 2 批：當事人名稱變更」
   - 依複雜度：從簡單的文字替換開始，然後處理複雜的結構變更
   - 依順序：「第 1 批：第 1-3 頁」、「第 2 批：第 4-6 頁」

3. **閱讀文件並解開檔案**：
   - **強制要求 - 閱讀整個檔案**：從頭到尾完整閱讀 [`ooxml.md`](ooxml.md)（約 600 行）。**閱讀此檔案時，絕不要設定任何範圍限制。** 特別注意「Document 函式庫」和「追蹤修訂模式」段落。
   - **解開文件**：`python ooxml/scripts/unpack.py <file.docx> <dir>`
   - **記下建議的 RSID**：解開腳本將建議一個 RSID 供您的追蹤修訂使用。複製此 RSID 以便在步驟 4b 中使用。

4. **分批實作變更**：將變更有邏輯地分組（依章節、依類型或依位置接近程度），然後在單個腳本中集中實作。這種方法：
   - 使除錯更容易（批次越小 = 越容易隔離錯誤）
   - 允許漸進式進展
   - 保持效率（3-10 個變更的批次大小效果最佳）

   **建議的批次分組：**
   - 依檔案章節（例如「Section 3 變更」、「定義」、「終止條款」）
   - 依變更類型（例如「日期變更」、「當事人名稱更新」、「法律術語替換」）
   - 依位置接近程度（例如「第 1-3 頁的變更」、「檔案前半部的變更」）

   對於每一批相關變更：

   **a. 將文字對應至 XML**：在 `word/document.xml` 中使用 grep 搜尋文字，以確認文字如何在 `<w:r>` 元素中被分割。

   **b. 建立並執行腳本**：使用 `get_node` 尋找節點、實作變更，然後執行 `doc.save()`。模式請參閱 ooxml.md 中的 **「Document 函式庫」** 段落。

   **注意**：在撰寫腳本前，請務必先對 `word/document.xml` 執行 grep 搜尋，以取得當前的行號並確認文字內容。每次執行腳本後，行號都會改變。

5. **打包文件**：所有批次完成後，將解開的目錄轉換回 .docx：
   ```bash
   python ooxml/scripts/pack.py unpacked reviewed-document.docx
   ```

6. **最終驗證**：對完整文件進行全面檢查：
   - 將最終文件轉換為 markdown：
     ```bash
     pandoc --track-changes=all reviewed-document.docx -o verification.md
     ```
   - 驗證「所有」變更是否都已正確套用：
     ```bash
     grep "原始短語" verification.md  # 應找不到
     grep "替換的短語" verification.md  # 應能找到
     ```
   - 檢查是否引入了不打算的變更

## 將文件轉換為圖片

為了視覺化分析 Word 文件，可以使用兩步驟過程將它們轉換為圖片：

1. **將 DOCX 轉換為 PDF**：
   ```bash
   soffice --headless --convert-to pdf document.docx
   ```

2. **將 PDF 頁面轉換為 JPEG 圖片**：
   ```bash
   pdftoppm -jpeg -r 150 document.pdf page
   ```
   這會建立像 `page-1.jpg`、`page-2.jpg` 等檔案。

選項：
- `-r 150`：將解析度設定為 150 DPI（可自行調整以平衡品質 / 大小）
- `-jpeg`：輸出 JPEG 格式（如果偏好 PNG，可使用 `-png`）
- `-f N`：第一頁的起始頁碼（例如 `-f 2` 從第 2 頁開始）
- `-l N`：最後一頁的結束頁碼（例如 `-l 5` 在第 5 頁停止）
- `page`：輸出檔案的前綴名稱

針對特定範圍的範例：
```bash
pdftoppm -jpeg -r 150 -f 2 -l 5 document.pdf page  # 只轉換第 2-5 頁
```

## 程式碼樣式指南
**重要提示**：在為 DOCX 操作產生程式碼時：
- 撰寫簡潔的程式碼
- 避免冗長的變數名稱和多餘的操作
- 避免不必要的 print 語句

## 相依套件

必要的相依套件（如無法使用請安裝）：

- **pandoc**：`sudo apt-get install pandoc`（用於文字提取）
- **docx**：`npm install -g docx`（用於建立新文件）
- **LibreOffice**：`sudo apt-get install libreoffice`（用於 PDF 轉換）
- **Poppler**：`sudo apt-get install poppler-utils`（用於 pdftoppm 將 PDF 轉為圖片）
- **defusedxml**：`pip install defusedxml`（用於安全的 XML 解析）