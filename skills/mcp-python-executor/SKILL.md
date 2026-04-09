---
name: mcp-python-executor
provider: mcp
version: "1.0.0"
description: >
  強大的 Python 程式碼執行工具。強制規定：不得只在文字中提供程式碼；當使用者要求執行計算、驗證結果或執行腳本時，必須使用此工具實際執行程式碼。 LLM（大腦）須提供原始 Python 程式碼，並以此工具作為與系統邏輯互動的主要方式。
runtime_requirements: []
---

# MCP Python Executor（Python 執行工具）

## 說明
此技能作為 LLM 推理與實際執行之間的直接橋樑。
LLM 可以撰寫腳本來解決使用者的問題，此工具將負責執行它。

## 使用方式
- **code（字串）**：要執行的完整 Python 程式碼。
  - 使用 `print()` 輸出結果——輸出內容將回傳給 LLM。
  - 允許使用標準函式庫。

## 檔案下載特別指令 (LINE 專用)
若要提供檔案供使用者下載（例如總結報告、數據等）：
1. **存放路徑**：檔案必須儲存在 `workspace/downloads/` 目錄下。
2. **範例程式碼**：
   ```python
   import os
   target_dir = os.path.join(os.getcwd(), 'workspace', 'downloads')
   os.makedirs(target_dir, exist_ok=True)
   file_path = os.path.join(target_dir, 'summary.txt')
   with open(file_path, 'w', encoding='utf-8') as f:
       f.write('您的資料總結內容...')
   print(f"檔案已備妥：summary.txt")
   ```
3. **回傳連結**：執行完畢後，請根據系統提示中提供的 `BASE_URL` 組合下載連結回傳給使用者。

## 數據圖表繪製指令
當使用者上傳 xlsx/csv 並要求繪製圖表（長條圖、折線圖、圓餅圖等）時：
1. 使用 `pandas` 讀取數據，`matplotlib` 繪圖
2. 設定中文字型：`plt.rcParams['font.sans-serif'] = ['Microsoft JhengHei', 'SimHei', 'Arial Unicode MS']`
3. 圖片儲存到 CWD（已自動設為 workspace/downloads/）
4. **重要**：使用 `{BASE_URL}/images/{filename}` 格式回傳圖片 URL（非 /downloads/），以確保 LINE 能以圖片訊息顯示

範例：
```python
import pandas as pd
import matplotlib.pyplot as plt

plt.rcParams['font.sans-serif'] = ['Microsoft JhengHei', 'SimHei']
plt.rcParams['axes.unicode_minus'] = False

df = pd.read_excel('uploaded_file.xlsx')
fig, ax = plt.subplots(figsize=(10, 6))
df.plot(kind='bar', x='月份', y='營收', ax=ax)
ax.set_title('月營收統計圖')
plt.tight_layout()
plt.savefig('chart.png', dpi=150)
print("圖表已生成：chart.png")
```
