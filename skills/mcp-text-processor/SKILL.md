---
name: mcp-text-processor
version: "1.0.0"
description: "純文字檔案處理器。當需要讀取、編輯或分析 .txt, .md, .log, .csv 等純文字格式檔案時使用。"
---

# 純文字檔案處理指南

## 概覽
純文字檔案可以直接使用 Python 的內建函式進行讀取與處理。

## 讀取檔案
請使用 `mcp-python-executor` 執行以下邏輯：

```python
with open("絕對路徑", "r", encoding="utf-8") as f:
    content = f.read()
    print(content)
```

## 注意事項
1. **編碼**：預設請優先使用 `utf-8`。若讀取失敗，可嘗試 `big5` 或 `utf-16`。
2. **大檔案**：若檔案過大（超過 1MB），請儘量分段讀取或只讀取關鍵部分。
3. **CSV 檔案**：對於 CSV 檔案，您也可以使用 `pandas` 進階處理。

```python
import pandas as pd
df = pd.read_csv("絕對路徑")
print(df.head())
```
