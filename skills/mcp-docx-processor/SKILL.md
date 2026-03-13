---
name: mcp-docx-processor
version: "1.0.0-lite"
description: "Word 文件 (.docx) 處理【指令手冊】。僅供查詢處理指令，不可直接執行。執行分析請改用 mcp-python-executor。"
---

# Word 處理指令手冊 (精簡版)

> [!IMPORTANT]
> 本工具僅提供處理邏輯說明。請在閱讀完此手冊後，立即呼叫 `mcp-python-executor` 並根據以下範例撰寫程式碼來分析文件。

## 讀取與分析內容
請使用 `mcp-python-executor` 執行以下指令：

### 1. 快速提取文字 (推薦)
使用 `pandoc` 將 docx 轉為 markdown，可同時看到追蹤修訂。
```python
import subprocess
# --track-changes=all 會保留修改痕跡
cmd = ["pandoc", "--track-changes=all", "絕對路徑.docx", "-o", "output.md"]
subprocess.run(cmd)
with open("output.md", "r", encoding="utf-8") as f:
    print(f.read())
```

### 2. 使用 python-docx 讀取
```python
from docx import Document
doc = Document("絕對路徑.docx")
full_text = [para.text for para in doc.paragraphs]
print("\n".join(full_text))
```