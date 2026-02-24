---

name: webapp-testing
version: "1.0.0"
description: 使用 Playwright 與本地網頁應用程式互動及執行測試的工具組。支援驗證前端功能、除錯 UI 行為、擷取瀏覽器螢幕截圖及查看瀏覽器日誌。
license: Complete terms in LICENSE.txt
---

# 網頁應用程式測試

要測試本地網頁應用程式，請撰寫原生 Python Playwright 腳本。

**可用的輔助腳本**：
- `scripts/with_server.py` - 管理伺服器生命週期（支援多個伺服器）

**務必先使用 `--help` 執行腳本**，以查看使用說明。除非嘗試執行腳本後確實需要自訂解決方案，否則不要讀取原始碼。這些腳本可能非常大，載入上下文視窗會造成汙染。它們的設計是作為黑箱腳本直接呼叫，而非載入到上下文視窗中。

## 決策樹：選擇方法

```
使用者任務 → 是靜態 HTML 嗎？
    ├─ 是 → 直接讀取 HTML 檔案以識別選擇器
    │         ├─ 成功 → 使用選擇器撰寫 Playwright 腳本
    │         └─ 失敗 / 不完整 → 視為動態（如下）
    │
    └─ 否（動態網頁應用程式）→ 伺服器已在執行嗎？
        ├─ 否 → 執行：python scripts/with_server.py --help
        │        然後使用輔助腳本 + 撰寫簡化的 Playwright 腳本
        │
        └─ 是 → 偵察後行動：
            1. 導覽並等待 networkidle
            2. 拍截圖或檢查 DOM
            3. 從渲染後的狀態識別選擇器
            4. 使用找到的選擇器執行動作
```

## 範例：使用 with_server.py

要啟動伺服器，先執行 `--help`，然後使用輔助腳本：

**單一伺服器：**
```bash
python scripts/with_server.py --server "npm run dev" --port 5173 -- python your_automation.py
```

**多個伺服器（例如後端 + 前端）：**
```bash
python scripts/with_server.py \
  --server "cd backend && python server.py" --port 3000 \
  --server "cd frontend && npm run dev" --port 5173 \
  -- python your_automation.py
```

建立自動化腳本時，只包含 Playwright 邏輯（伺服器由輔助腳本自動管理）：
```python
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)  # 務必以 headless 模式啟動 chromium
    page = browser.new_page()
    page.goto('http://localhost:5173')  # 伺服器已在執行並就緒
    page.wait_for_load_state('networkidle')  # 關鍵：等待 JS 執行完畢
    # ... 自動化邏輯
    browser.close()
```

## 偵察後行動模式

1. **檢查渲染後的 DOM**：
   ```python
   page.screenshot(path='/tmp/inspect.png', full_page=True)
   content = page.content()
   page.locator('button').all()
   ```

2. **從檢查結果識別選擇器**

3. **使用找到的選擇器執行動作**

## 常見陷阱

❌ **不要**在動態應用程式上等待 `networkidle` 之前就檢查 DOM
✅ **要**在檢查前先等待 `page.wait_for_load_state('networkidle')`

## 最佳實踐

- **將捆綁腳本當作黑箱使用** — 要完成任務時，先考慮 `scripts/` 中的腳本是否有幫助。這些腳本可靠地處理常見且複雜的工作流程，同時不會汙染上下文視窗。使用 `--help` 查看說明，然後直接呼叫。
- 使用 `sync_playwright()` 執行同步腳本
- 完成後務必關閉瀏覽器
- 使用描述性選擇器：`text=`、`role=`、CSS 選擇器或 ID
- 加入適當的等待：`page.wait_for_selector()` 或 `page.wait_for_timeout()`

## 參考檔案

- **examples/** — 展示常見模式的範例：
  - `element_discovery.py` — 在頁面上發現按鈕、連結和輸入框
  - `static_html_automation.py` — 使用 file:// URL 操作本地 HTML
  - `console_logging.py` — 在自動化期間擷取主控台日誌