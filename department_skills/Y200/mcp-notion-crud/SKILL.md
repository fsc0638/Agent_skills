---
name: mcp-notion-crud
skillk_id: SkillK_dXanFjI1wZZEgnkeUDu1
display_name: "Notion ToDo"
category: Department
provider: mcp
version: "1.0.0"
description: >
  Notion ToDo 資料庫完整操作工具。支援新增、查詢、更新、刪除待辦事項，
  以及從結構化會議資料批次匯入，並支援條件式批次更新與批次刪除。
  當使用者提到「查待辦」「我的任務」「Notion 進度」「todo list」
  「哪些未完成」「任務查詢」「待辦清單」「進度查詢」
  「新增待辦」「加一筆任務」「建立todo」
  「更新待辦」「改狀態」「標記完成」「修改todo」「批次更新」「全部標記完成」
  「刪除任務」「移除待辦」「刪掉那筆」「批次刪除」「清除已完成」
  「上傳Notion」「寫入Notion」「匯入待辦」時觸發此技能。
  【必填參數】呼叫此工具時必須傳入 action 參數，可選值：
  create（新增單筆，需帶 todo_title）、
  create_batch（批次匯入，需帶 items_json 或 cleaned_text + org_data_json）、
  list（查詢列表，可帶 filter_status / filter_assignee / filter_project / keyword / filter_date / filter_due_date / limit / offset）、
  summary（進度摘要，無額外參數）、
  find_duplicates（找出重複項目並分組，可帶 filter_* / keyword 縮小範圍；dedupe_by 預設 ToDo、keep 預設 oldest，scope_mode 預設 auto）、
  update（更新單筆欄位，帶 page_id 或 keyword 定位）、
  update_batch（條件式批次更新，帶篩選條件 + set_status / set_assignee 等目標值）、
  delete（封存單筆，帶 page_id 或 keyword 定位）、
  delete_batch（條件式批次刪除，帶篩選條件）。
  【去重流程】當使用者提到「有重複嗎」「幫我刪重複」「清掉重複的」時，
  第一步必呼叫 action=find_duplicates（套用使用者當下的 filter_* 範圍），
  取回 groups 與 all_delete_ids；第二步呼叫 action=delete_batch 並把 all_delete_ids 當 page_ids 傳入
  （先不帶 confirm 取得 preview，再帶 confirm=true 實際執行）。
  【範圍繼承（強制）】
  若上一輪剛用 action=list 列出清單，使用者接著問「有哪些重複 / 有沒有重複 / 刪除其中一個」，
  find_duplicates 必須沿用最近一次 list 的範圍（scope_mode 用 auto 或 list），不得改查整個 Notion。
  只有當使用者明確提到「重新搜尋」「重新查」「整個 Notion」「全資料庫」時，
  才可用 scope_mode="global"（或提供新的 filter_*）改為全庫搜尋。
  嚴禁自行用標題字串推測哪些是重複並把整批項目刪除。
  【find_duplicates 後的刪除規則 — 強制】
  只要上一輪 find_duplicates 的結果仍在對話脈絡（groups / delete_suggestion / all_delete_ids 可取得），
  使用者接著說「刪除其中一個」「刪掉那筆重複的」「刪掉第N組的重複」時，
  必須直接用 action=delete_batch 搭配 page_ids=[對應的 delete_suggestion page_id] + confirm=true 執行；
  嚴禁改用 action=delete 搭配 keyword=標題字串去找同一筆（LLM 可能插入多餘空白或序號差異導致 0 筆命中）。
  若只要刪單一組的其中一筆，從 groups[i].delete_suggestion[0] 取出該 UUID 即可。
  【篩選語法】filter_status 支援 "not:已完成"（排除）；
  filter_date 支援 "before:2026-04-15"（之前）、"after:2026-04-15"（之後含當日）；
  filter_due_date 同樣支援 before:/after: 語法；
  filter_hours 支援 "8"、">=8"、"<4"、"5:10"（範圍）等數值語法；
  filter_logic="or" 可將多個 filter_* 條件以 OR 串接（預設 AND）。
  【兩段式刪除】delete_batch 若只帶 filter_* 條件（無 page_ids）會先回傳 status=preview，
  列出命中清單；確認無誤後請第二次呼叫帶 confirm=true（或直接帶 page_ids）才會實際執行。
  【重要】update 和 delete 可用 keyword 參數以名稱查找（若僅匹配 1 筆則自動執行，多筆則回傳候選清單）。
  也可用 page_id（Notion UUID 格式如 "343e791c-b3f0-8130-8b47-c0e50ee40a53"）。
  【分頁參數】list 預設每次回傳 20 筆（limit=20），若 total 大於 returned，
  回傳結果會包含 next_offset 值，請用 offset=next_offset 取得下一頁，直到所有資料取完。
  使用者要求「列出全部」時，請自動用 offset 逐頁取完所有資料再一次呈現。
  若使用者說「刪除第N項」或「更新第N項」，請從最近一次 list 回傳的 items[N-1].page_id 取 UUID 再呼叫。
  【嚴禁 UUID 幻覺】絕不可從前一筆 UUID 修改幾個字元當新 UUID 使用；若對話史上找不到目標項目的 page_id，
  請先重新呼叫 action=list（可帶 keyword 縮小範圍）取得 items[*].page_id 再刪除/更新，
  或改用 action=delete/update 搭配 keyword 參數讓系統查找。
runtime_requirements: [requests, openai]
risk_level: low
risk_description: >
  此技能可對 Notion 資料庫執行寫入操作（新增、更新、封存頁面）。 action=list 和 action=summary 為唯讀操作，不會修改任何資料。 action=create/create_batch/update/delete 會修改外部系統資料。
execution_timeout: 120
recommended_models:
  openai: gpt-4.1-nano
  gemini: gemini-2.0-flash
  claude: claude-haiku-4-5

# Workflow 設計器可讀的參數 schema — 讓 block config 面板能渲染出
# 具體欄位（enum 會變下拉、description 顯示在 label 下方）。
parameters:
  type: object
  properties:
    action:
      type: string
      enum: [list, summary, find_duplicates, create, create_batch, update, update_batch, delete, delete_batch]
      default: list
      description: "操作類型：list / summary 為唯讀；create / update / delete 會修改 Notion 資料"
    keyword:
      type: string
      description: "篩選關鍵字（標題包含此字串）— 用於 list / update / delete 定位"
    filter_status:
      type: string
      description: "狀態篩選（如「未完成」或「not:已完成」）"
    filter_assignee:
      type: string
      description: "指派對象篩選"
    filter_project:
      type: string
      description: "專案篩選"
    filter_date:
      type: string
      description: "建立日期篩選（支援 before:2026-04-15 / after:2026-04-15）"
    filter_due_date:
      type: string
      description: "到期日篩選（支援 before: / after:）"
    limit:
      type: integer
      minimum: 1
      maximum: 100
      default: 20
      description: "list 查詢每頁筆數（預設 20，最多 100）"
    offset:
      type: integer
      minimum: 0
      default: 0
      description: "list 分頁起始位置"
    todo_title:
      type: string
      description: "create 新增單筆時的標題（action=create 時必填）"
    page_id:
      type: string
      description: "update / delete 的目標頁面 UUID（若用 keyword 定位則可省略）"
    set_status:
      type: string
      description: "update / update_batch 的目標狀態值"
    set_assignee:
      type: string
      description: "update / update_batch 的目標指派對象"
    confirm:
      type: boolean
      default: false
      description: "delete_batch 兩段式確認旗標（true 才真的刪）"
  required: [action]
---

# Notion ToDo CRUD 工具 (mcp-notion-crud)

## 說明

統一的 Notion ToDo 資料庫操作介面，涵蓋完整 CRUD 功能。

## 操作模式

### create — 新增單筆 ToDo

直接建立一筆待辦項目。必填：`todo_title`。

### create_batch — 批次匯入

兩種使用方式：
1. **直接傳入 items_json**：已經是結構化 JSON Array，直接進入 QA 檢核 + Upload。
2. **傳入 cleaned_text + org_data_json**：從 mcp-meeting-analyzer 的輸出接續，
   執行 Phase 3 Schema Mapping → Phase 4 QA → Upload（Upsert）。

### list — 列出待辦

依條件篩選後回傳 ToDo 清單，包含 page_id 供後續 update/delete 使用。

**分頁參數**：
- `limit`：每頁筆數，預設 20，最大 100
- `offset`：跳過前 N 筆，預設 0

回傳結果含 `total`（總筆數）、`returned`（本次回傳筆數）、`offset`、`limit`。
若還有下一頁，會額外回傳 `next_offset`，請用 `offset=next_offset` 取得後續資料。

### summary — 進度摘要

統計各狀態的數量，並列出即將到期與逾期項目。

### find_duplicates — 找出重複項目並分組

將符合 filter_* / keyword 條件的項目依「標題」分組，回傳：
- `groups[*]`：每一組重複項目，含 `items`（各 page_id 與欄位）、`keep_suggestion`（建議保留）、`delete_suggestion`（建議刪除的 page_ids）
- `all_delete_ids`：所有 group 的 delete_suggestion 串接，可直接餵給 delete_batch

**標題正規化**：去除末端 `(1)` / `(2)` 序號、空白正規化、大小寫視為相同，因此
「整理並優化網頁部分內容與結構 (1)」與「整理並優化網頁部分內容與結構」會被視為同一組。

**參數**：
- `dedupe_by`：`ToDo`（預設，依標題）或 `ToDo+專案`（再加上專案串接，避免不同專案的同名項目被誤判）
- `keep`：`oldest`（預設保留最早建立）或 `newest`
- 篩選參數同 list：`filter_status` / `filter_date` / `filter_due_date` / `filter_hours` / `filter_project` / `filter_assignee` / `keyword` / `filter_logic`

**典型流程**：
```
1. find_duplicates(filter_date="2026-04-15")  → 取得 groups + all_delete_ids
2. 向使用者報告有哪幾組重複、將保留/刪除哪些
3. delete_batch(page_ids=all_delete_ids)       → preview（不帶 confirm）
4. delete_batch(page_ids=all_delete_ids, confirm=true)  → 實際封存
```

### update — 更新單筆欄位

僅更新有傳入的欄位，未傳入的欄位維持原值。
定位方式（二擇一）：`page_id`（UUID）或 `keyword`（以名稱查找，僅匹配 1 筆時自動執行）。

### update_batch — 條件式批次更新

依篩選條件查出多筆後，統一更新指定欄位。
- 篩選參數：`filter_status`、`filter_date`、`filter_due_date`、`filter_assignee`、`filter_project`、`keyword`、`page_ids`（JSON Array）
- 目標值參數：`set_status`、`set_assignee`、`set_due_date`、`set_project`
- 範例：將所有 04/15 的項目標記完成 → `filter_date="2026-04-15"`, `set_status="已完成"`

### delete — 封存單筆

將指定頁面設為 archived。
定位方式（二擇一）：`page_id`（UUID）或 `keyword`（以名稱查找，僅匹配 1 筆時自動執行）。

### delete_batch — 條件式批次刪除（兩段式）

依篩選條件查出多筆後，逐筆封存。為避免誤刪，採用**兩段式流程**：

**第一次呼叫**（只帶 filter_*，不帶 confirm）→ 回傳 `status: "preview"` 與命中清單（含 page_ids），**不會刪除任何資料**。
**第二次呼叫**有兩種等效方式：
1. 帶 `confirm=true` + 相同的 filter_* 條件 → 以相同條件重查並執行
2. 直接帶 `page_ids`（從 preview 回傳取得）→ 跳過確認直接執行

- 篩選參數：`filter_status`、`filter_date`、`filter_due_date`、`filter_hours`、`filter_assignee`、`filter_project`、`keyword`、`filter_logic`（`and` / `or`，預設 `and`）
- 直接參數：`page_ids`（JSON Array，帶此參數視為已確認）
- 範例：刪除所有已完成項目 → `filter_status="已完成"` → preview → `confirm=true`
- 範例：刪除到期日是明天的 → `filter_due_date="2026-04-17"` → preview → `confirm=true`
- 範例：刪除 04/15 之前的項目 → `filter_date="before:2026-04-15"` → preview → `confirm=true`

## 參數前綴規則（避免混淆）

不同 action 對「到期日/狀態/負責人/專案」使用不同前綴，請嚴格依下表選用：

| Action | 設定到期日 | 設定狀態 | 設定負責人 | 設定專案 |
|--------|-----------|---------|-----------|---------|
| `create` | `due_date` | `status` | `assignee` | `project` |
| `update` | `due_date` | `status` | `assignee` | `project` |
| `update_batch` | `set_due_date` | `set_status` | `set_assignee` | `set_project` |
| `list` / `delete_batch` | ❌ 不設定 | ❌ 不設定 | ❌ 不設定 | ❌ 不設定 |

`filter_*` 前綴**只用於篩選**（list / update_batch / delete_batch 找出目標），絕不用於設定目標值。

### ❌ 錯誤範例

```json
// 錯：把「設定新到期日」誤用為 filter
{"action": "update", "page_id": "xxx", "filter_due_date": "2026-04-17"}

// 錯：單筆 update 用了 update_batch 的 set_ 前綴
{"action": "update", "page_id": "xxx", "set_due_date": "2026-04-17"}
```

### ✅ 正確範例

```json
// 單筆更新到期日
{"action": "update", "page_id": "xxx", "due_date": "2026-04-17"}

// 批次更新到期日（依條件篩選後統一設定）
{"action": "update_batch", "filter_date": "2026-04-15", "set_due_date": "2026-04-17"}

// 查詢到期日在某日前的項目
{"action": "list", "filter_due_date": "before:2026-04-17"}
```

> 註：為容錯，系統會在 `create` / `update` 收到 `filter_*` 或 `set_*` 前綴時自動映射為直接欄位值，但仍請依正確命名呼叫以免語意誤判。

## 篩選語法說明

| 參數 | 語法 | 說明 |
|------|------|------|
| `filter_status` | `"已完成"` | 精確匹配狀態 |
| `filter_status` | `"not:已完成"` | 排除該狀態（查所有未完成） |
| `filter_date` | `"today"` | 今天建立的 |
| `filter_date` | `"2026-04-15"` | 指定日期建立的 |
| `filter_date` | `"2026-04-01:2026-04-15"` | 日期範圍 |
| `filter_date` | `"before:2026-04-15"` | 該日之前建立的 |
| `filter_date` | `"after:2026-04-15"` | 該日之後建立的（含當日） |
| `filter_due_date` | `"overdue"` | 已逾期 |
| `filter_due_date` | `"upcoming"` | 未來 7 天內到期 |
| `filter_due_date` | `"before:2026-04-15"` | 到期日在該日之前 |
| `filter_due_date` | `"after:2026-04-15"` | 到期日在該日之後 |
| `filter_due_date` | `"2026-04-15:2026-04-20"` | 到期日範圍 |
| `filter_hours` | `"8"` | 工時等於 8 |
| `filter_hours` | `">=8"` / `">8"` | 工時大於等於 / 大於 |
| `filter_hours` | `"<=4"` / `"<4"` | 工時小於等於 / 小於 |
| `filter_hours` | `"5:10"` | 工時範圍 [5, 10] |
| `filter_logic` | `"and"` (預設) / `"or"` | 多個 filter_* 以 AND 或 OR 串接 |

## 環境變數需求

| 變數 | 說明 |
|------|------|
| `NOTION_TOKEN` | Notion Integration Token（必要） |
| `NOTION_DATABASE_ID` | 目標 Notion 資料庫 ID（必要） |
| `OPENAI_API_KEY` | 僅 create_batch 的 Schema Mapping 需要 |

## 輸出格式

所有 action 統一回傳 JSON，含 `status` 和 `action` 欄位。
