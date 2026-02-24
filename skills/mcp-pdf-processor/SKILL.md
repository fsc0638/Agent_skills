---

name: pdf
version: "1.0.0"
description: 完整的 PDF 操作工具包，可提取文字與表格、建立新 PDF、合併／拆分文件及處理表單。當需要填寫 PDF 表單，或以程式化方式處理、生成或大規模分析 PDF 文件時使用。
license: Proprietary. LICENSE.txt has complete terms
---

# PDF 處理指南

## 概覽

本指南涵蓋使用 Python 函式庫和命令列工具進行 PDF 處理的基本操作。進階功能、JavaScript 函式庫及詳細範例，請參閱 reference.md。若需要填寫 PDF 表單，請閱讀 forms.md 並依照說明操作。

## 快速開始

```python
from pypdf import PdfReader, PdfWriter

# 讀取 PDF
reader = PdfReader("document.pdf")
print(f"頁數: {len(reader.pages)}")

# 提取文字
text = ""
for page in reader.pages:
    text += page.extract_text()
```

## Python 函式庫

### pypdf — 基本操作

#### 合併 PDF
```python
from pypdf import PdfWriter, PdfReader

writer = PdfWriter()
for pdf_file in ["doc1.pdf", "doc2.pdf", "doc3.pdf"]:
    reader = PdfReader(pdf_file)
    for page in reader.pages:
        writer.add_page(page)

with open("merged.pdf", "wb") as output:
    writer.write(output)
```

#### 拆分 PDF
```python
reader = PdfReader("input.pdf")
for i, page in enumerate(reader.pages):
    writer = PdfWriter()
    writer.add_page(page)
    with open(f"page_{i+1}.pdf", "wb") as output:
        writer.write(output)
```

#### 提取中繼資料
```python
reader = PdfReader("document.pdf")
meta = reader.metadata
print(f"標題: {meta.title}")
print(f"作者: {meta.author}")
print(f"主旨: {meta.subject}")
print(f"建立者: {meta.creator}")
```

#### 旋轉頁面
```python
reader = PdfReader("input.pdf")
writer = PdfWriter()

page = reader.pages[0]
page.rotate(90)  # 順時針旋轉 90 度
writer.add_page(page)

with open("rotated.pdf", "wb") as output:
    writer.write(output)
```

### pdfplumber — 文字與表格提取

#### 提取具版面的文字
```python
import pdfplumber

with pdfplumber.open("document.pdf") as pdf:
    for page in pdf.pages:
        text = page.extract_text()
        print(text)
```

#### 提取表格
```python
with pdfplumber.open("document.pdf") as pdf:
    for i, page in enumerate(pdf.pages):
        tables = page.extract_tables()
        for j, table in enumerate(tables):
            print(f"第 {i+1} 頁的表格 {j+1}:")
            for row in table:
                print(row)
```

#### 進階表格提取
```python
import pandas as pd

with pdfplumber.open("document.pdf") as pdf:
    all_tables = []
    for page in pdf.pages:
        tables = page.extract_tables()
        for table in tables:
            if table:  # 確認表格不為空
                df = pd.DataFrame(table[1:], columns=table[0])
                all_tables.append(df)

# 合併所有表格
if all_tables:
    combined_df = pd.concat(all_tables, ignore_index=True)
    combined_df.to_excel("extracted_tables.xlsx", index=False)
```

### reportlab — 建立 PDF

#### 基本 PDF 建立
```python
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

c = canvas.Canvas("hello.pdf", pagesize=letter)
width, height = letter

# 新增文字
c.drawString(100, height - 100, "Hello World!")
c.drawString(100, height - 120, "This is a PDF created with reportlab")

# 新增線條
c.line(100, height - 140, 400, height - 140)

# 儲存
c.save()
```

#### 建立多頁 PDF
```python
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak
from reportlab.lib.styles import getSampleStyleSheet

doc = SimpleDocTemplate("report.pdf", pagesize=letter)
styles = getSampleStyleSheet()
story = []

# 新增內容
title = Paragraph("Report Title", styles['Title'])
story.append(title)
story.append(Spacer(1, 12))

body = Paragraph("This is the body of the report. " * 20, styles['Normal'])
story.append(body)
story.append(PageBreak())

# 第 2 頁
story.append(Paragraph("Page 2", styles['Heading1']))
story.append(Paragraph("Content for page 2", styles['Normal']))

# 建立 PDF
doc.build(story)
```

## 命令列工具

### pdftotext（poppler-utils）
```bash
# 提取文字
pdftotext input.pdf output.txt

# 保留版面提取文字
pdftotext -layout input.pdf output.txt

# 提取特定頁面
pdftotext -f 1 -l 5 input.pdf output.txt  # 第 1-5 頁
```

### qpdf
```bash
# 合併 PDF
qpdf --empty --pages file1.pdf file2.pdf -- merged.pdf

# 拆分頁面
qpdf input.pdf --pages . 1-5 -- pages1-5.pdf
qpdf input.pdf --pages . 6-10 -- pages6-10.pdf

# 旋轉頁面
qpdf input.pdf output.pdf --rotate=+90:1  # 第 1 頁旋轉 90 度

# 移除密碼
qpdf --password=mypassword --decrypt encrypted.pdf decrypted.pdf
```

### pdftk（如已安裝）
```bash
# 合併
pdftk file1.pdf file2.pdf cat output merged.pdf

# 拆分
pdftk input.pdf burst

# 旋轉
pdftk input.pdf rotate 1east output rotated.pdf
```

## 常見任務

### 從掃描 PDF 提取文字
```python
# 需要: pip install pytesseract pdf2image
import pytesseract
from pdf2image import convert_from_path

# 將 PDF 轉換為圖片
images = convert_from_path('scanned.pdf')

# 對每頁進行 OCR
text = ""
for i, image in enumerate(images):
    text += f"Page {i+1}:\n"
    text += pytesseract.image_to_string(image)
    text += "\n\n"

print(text)
```

### 新增浮水印
```python
from pypdf import PdfReader, PdfWriter

# 建立或載入浮水印
watermark = PdfReader("watermark.pdf").pages[0]

# 套用至所有頁面
reader = PdfReader("document.pdf")
writer = PdfWriter()

for page in reader.pages:
    page.merge_page(watermark)
    writer.add_page(page)

with open("watermarked.pdf", "wb") as output:
    writer.write(output)
```

### 提取圖片
```bash
# 使用 pdfimages（poppler-utils）
pdfimages -j input.pdf output_prefix

# 提取所有圖片為 output_prefix-000.jpg、output_prefix-001.jpg 等
```

### 密碼保護
```python
from pypdf import PdfReader, PdfWriter

reader = PdfReader("input.pdf")
writer = PdfWriter()

for page in reader.pages:
    writer.add_page(page)

# 新增密碼
writer.encrypt("userpassword", "ownerpassword")

with open("encrypted.pdf", "wb") as output:
    writer.write(output)
```

## 快速參考

| 任務 | 最佳工具 | 指令 / 程式碼 |
|------|----------|--------------|
| 合併 PDF | pypdf | `writer.add_page(page)` |
| 拆分 PDF | pypdf | 每頁一個檔案 |
| 提取文字 | pdfplumber | `page.extract_text()` |
| 提取表格 | pdfplumber | `page.extract_tables()` |
| 建立 PDF | reportlab | Canvas 或 Platypus |
| 命令列合併 | qpdf | `qpdf --empty --pages ...` |
| 掃描 PDF OCR | pytesseract | 先轉換為圖片 |
| 填寫 PDF 表單 | pdf-lib 或 pypdf（見 forms.md） | 見 forms.md |

## 下一步

- 進階 pypdfium2 用法，請見 reference.md
- JavaScript 函式庫（pdf-lib），請見 reference.md
- 若需填寫 PDF 表單，請依照 forms.md 的說明操作
- 疑難排解指南，請見 reference.md
