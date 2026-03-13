---
name: mcp-pdf-processor
version: "1.0.0-lite"
description: "PDF 文件處理【指令手冊】。僅供查詢處理指令，不可直接執行。執行分析請改用 mcp-python-executor。"
---

# PDF 處理指令手冊 (精簡版)

> [!IMPORTANT]
> 本工具僅提供處理邏輯說明。請在閱讀完此手冊後，立即呼叫 `mcp-python-executor` 並根據以下範例撰寫程式碼來分析文件。

## 讀取與分析內容
請使用 `mcp-python-executor` 執行以下指令：

### 1. 提取文字與版面 (推薦)
```python
import pdfplumber
with pdfplumber.open("絕對路徑.pdf") as pdf:
    for page in pdf.pages:
        print(page.extract_text())
```

### 2. 提取表格數據
```python
import pdfplumber
import pandas as pd
with pdfplumber.open("絕對路徑.pdf") as pdf:
    table = pdf.pages[0].extract_table()
    if table:
        df = pd.DataFrame(table[1:], columns=table[0])
        print(df.head())
```
