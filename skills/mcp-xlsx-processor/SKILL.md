---
name: mcp-xlsx-processor
version: "1.0.0-lite"
description: "Excel 試算表 (.xlsx, .csv) 處理【指令手冊】。僅供查詢處理指令，不可直接執行。執行分析請改用 mcp-python-executor。"
---

# Excel 處理指令手冊 (精簡版)

> [!IMPORTANT]
> 本工具僅提供處理邏輯說明。請在閱讀完此手冊後，立即呼叫 `mcp-python-executor` 並根據以下範例撰寫程式碼來分析文件。

## 讀取與分析內容
請使用 `mcp-python-executor` 執行以下指令：

### 1. 使用 Pandas 高速讀取 (推薦)
```python
import pandas as pd
# 讀取首個分頁
df = pd.read_excel("絕對路徑.xlsx")
# 查看數據摘要
print(df.info())
print(df.head())
```

### 2. 使用 openpyxl 讀取公式
```python
from openpyxl import load_workbook
wb = load_workbook("絕對路徑.xlsx", data_only=False)
sheet = wb.active
print(sheet["A1"].value) # 若為公式則顯示公式字串
```