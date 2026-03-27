---
name: mcp-schedule-manager
provider: mcp
version: 1.7.0
runtime_requirements: []
description: >
  定時推送與提醒管理工具。當使用者要求「每天早上推送新聞」、「每週五下班前提醒我」、
  「定時推送工作摘要」、「幫我設定排程」、「取消推送」等帶有時間排程意圖的指令時，
  必須使用此工具。此工具可新增、列出、刪除、暫停及恢復排程任務。
  支援類型：news（新聞摘要）、work_summary（工作重點）、language（語言學習）、custom（自訂內容）、pipeline（複合多技能任務）。
  注意：一次性提醒（如「10分鐘後提醒我」）也使用此工具，type 設為 reminder。
parameters:
  type: object
  properties:
    action:
      type: string
      description: >
        操作類型。add=新增排程、list=列出所有排程、remove=刪除排程、
        pause=暫停排程、resume=恢復排程、trigger=立即執行一次
      enum: ["add", "list", "remove", "pause", "resume", "trigger"]
    task_type:
      type: string
      description: >
        推送內容類型（僅 add 時需要）。
        news=新聞摘要、work_summary=工作項目統整、language=語言詞彙學習、
        custom=自訂內容、reminder=一次性提醒、pipeline=複合多技能任務。
        【極重要】必須根據下方「類型判定規則」正確選擇，不可隨意使用 custom。
      enum: ["news", "work_summary", "language", "custom", "reminder", "pipeline"]
    name:
      type: string
      description: "任務名稱，用於顯示。例如「每日科技新聞」「日文N3學習」"
    cron:
      type: string
      description: >
        排程時間。支援格式：
        - 簡單時間：'08:30' 表示每天 08:30
        - 工作日：'weekday 09:00' 表示週一到週五 09:00
        - 完整 cron：'30 8 * * 1-5' 表示平日 08:30
        - 一次性：'once +10m' 表示 10 分鐘後（用於 reminder 或一次性任務）
        - 間隔循環：'every +10m' 表示每 10 分鐘執行一次（支援任意分鐘數）
    config:
      type: object
      description: "任務設定，依 task_type 填入對應欄位。絕不可填入未定義的欄位。"
      properties:
        topic:
          type: string
          description: "[適用 news/language] 主題或關鍵字"
        count:
          type: integer
          description: "[適用 news/language] 數量"
        detail:
          type: string
          enum: ["detailed", "brief", "normal"]
          description: "[適用 news] 摘要深度"
        extra_instructions:
          type: string
          description: "[適用 news] 額外需求，例如產出PDF或指定來源"
        days:
          type: integer
          description: "[適用 work_summary] 統整天數"
        language:
          type: string
          description: "[適用 language] 語言種類"
        level:
          type: string
          description: "[適用 language] 難度等級，如 N3"
        prompt:
          type: string
          description: "[適用 custom] 完整使用者原文"
        message:
          type: string
          description: "[適用 reminder] 提醒內容"
        output_format:
          type: string
          enum: ["text", "pdf", "docx"]
          description: "[所有類型適用] 指定輸出格式。提到「PDF/下載/檔案」→ pdf；提到「Word/docx」→ docx；其他留空（預設 text）"
      additionalProperties: false
    task_id:
      type: string
      description: "任務 ID（remove/pause/resume/trigger 時需要）"
  required: [action]
estimated_tokens: 50
risk_level: low
execution_timeout: 10
---

# MCP Schedule Manager（定時推送與提醒管理）

## 說明
管理 LINE Bot 的定時推送排程。使用者透過自然語言設定排程，由 LLM 語意判斷後呼叫此工具。

## 使用時機
- 使用者說「每天推送…」、「定時推送…」、「排程…」、「幫我設定提醒」
- 使用者說「每天早上X點推Y則新聞」
- 使用者說「取消/暫停/恢復推送」
- 使用者說「查看我的排程」
- 使用者說「10分鐘後提醒我…」、「2分鐘後幫我做…」

## 不適用場景
- 單純聊天或問答
- 檔案分析或生成（無排程意圖）
- 即時搜尋（非定時）

---

## ⚠️ 結構化欄位拆解規則（極重要 — 參照 AutoScan 欄位對齊邏輯）

### # Role
你是一位專門負責排程任務結構化的專家。你的任務是將「使用者自然語言」拆解為多個獨立欄位，
對應排程系統的 task_type + config 結構。**禁止將所有資訊堆進 original_request，必須拆解到對應欄位。**

### # Constraints（核心約束）
1. **禁止堆疊**：嚴禁將所有資訊塞入 config.original_request 或 config.prompt。必須拆解到各欄位。
2. **資訊拆解**：將主題、數量、深度、格式需求、子主題分別提取到對應欄位。
3. **類型判定優先**：先匹配專用類型（news > work_summary > language > reminder），都不匹配才用 custom。
4. **時間基準約束**：所有排程時間預設為本地時間（GMT+8）。當使用者給出絕對時間（如「明天下午3點」）且非循環任務時，若不支援絕對日期格式，必須轉換為等效的相對時間 `once +Xm` 或標準排程格式。嚴禁輸出排程引擎無法識別的格式（如「tomorrow 15:00」、中文時間描述）。
5. **間隔循環格式**：當使用者說「每 X 分鐘」、「每隔 X 分鐘」，cron 必須用 `every +Xm`（例如 `every +10m`），**嚴禁使用 `*/X` 字串或中文描述作為 cron 值**。

### # Field Mapping Logic（欄位對齊邏輯）

**第一步：判定 task_type**
| 優先序 | 類型 | 判定條件（語意掃描） | 範例輸入 |
|--------|------|----------------------|----------|
| 1 | **news** | 出現「新聞/頭條/時事/報導/財經資訊」 | 「統整新聞」「推送20則經濟新聞」「新聞給我」 |
| 2 | **work_summary** | 出現「工作摘要/工作統整/週報/工作重點」 | 「推送工作摘要」 |
| 3 | **language** | 出現「學習/詞彙/單字」且有語種 | 「日文N3詞彙」 |
| 4 | **reminder** | 純粹提醒，**完全不需要 LLM 生成內容** | 「提醒我開會」「提醒我買牛奶」 |
| 5 | **pipeline** | 跨域複合需求：涉及 2+ 種不同技能且有資料依賴（搜尋→轉換→生成、分析→整理→輸出）| 見下方說明 |
| 6 | **custom** | 以上全部不匹配（最後手段） | 「推送勵志名言」「推送笑話」 |

⚠️ **「X分鐘後」是排程時間，不是類型判定依據！**
- 「2分鐘後統整新聞」→ type=**news**（有「新聞」）, cron="once +2m"
- 「10分鐘後提醒我開會」→ type=**reminder**（純提醒，語氣請幽默風趣切勿死板）

### 🔀 pipeline 判定規則

**使用 pipeline 的條件**：需求中包含**跨域技能組合**，各步驟之間有資料流依賴關係。

| 判斷問題 | 是 → | 否 → |
|----------|------|------|
| 需要 2 種以上不同類別的技能？ | 繼續判斷 | 用對應專用類型 |
| 各步驟之間有「前一步輸出→下一步輸入」的依賴？ | **pipeline** | custom |

**pipeline 適用範例：**
- 「搜尋台灣股市新聞 + 翻成日文 + 整理成 PDF」（搜尋→翻譯→生成檔案）
- 「查詢今天匯率 + 計算我的日幣換算 + 回報結果」（搜尋→計算→輸出）
- 「抓取天氣預報 + 判斷是否適合出遊 + 給出建議」（搜尋→推理→輸出）
- 「蒐集競品資訊 + 比較分析 + 製作 DOCX 報告」（搜尋×多次→分析→生成檔案）

**pipeline 不適用範例（改用對應專用類型）：**
- 「整理新聞做成 PDF」→ **news**（output_format=pdf，news 已內建此能力）
- 「日文詞彙學習」→ **language**
- 「提醒我開會」→ **reminder**

**pipeline config 必填欄位：**
- `original_request`：使用者完整原文（自動填入，不需 LLM 手動設定）
- `output_format`：若需要檔案輸出，設定 pdf / docx（選填）

### 🚨 多排程獨立性（嚴禁繼承前一次參數）
每次呼叫 mcp-schedule-manager **必須從使用者當前訊息重新解析所有欄位**。
**嚴禁**從對話歷史中的前一次排程結果複製 cron、name 或 config：

❌ 錯誤行為：使用者先建了 `once +40m` 的提醒，下次又說「2分鐘後統整新聞」，
   你卻複製前次的 `cron="once +40m"` 和 `name="看手機提醒"`
✅ 正確行為：每次都從「當前訊息」獨立解析 → `cron="once +2m"`, `name="社會案件新聞統整PDF"`

每個排程呼叫都是獨立的 — 當前訊息說「X分鐘」就用 X，說什麼主題就用什麼 name。

**第二步：提取 config 欄位（依 task_type）**

#### news 欄位拆解：
| 欄位 | 提取邏輯 | 範例 |
|------|----------|------|
| `topic` | 提取**主題/領域關鍵字**，不是動作詞。掃描：經濟/股市/房市/科技/AI/國際/政治/金融/產業/能源/醫療... 也掃「XXX相關議題」中的XXX | 「股市新聞」→`"股市"`, 「經濟新聞，股市相關議題」→`"經濟 股市"` |
| `count` | 提取數字+則/條/篇 | 「20則」→`20`, 未指定→`10` |
| `detail` | 「詳盡/詳細/深入/越X越好」→`"detailed"`, 「簡要/精簡」→`"brief"`, 其他→`"normal"` | 「越詳盡越好」→`"detailed"` |
| `extra_instructions` | 提取：格式需求(PDF/DOCX)、子主題(包含...)、出處要求 | 「包含國際趨勢，標記出處，統整成PDF」 |

🚨 **topic 禁止填入**：動作詞（統整/推送/給我）、時間（分鐘後/每天）、格式（PDF）、數量（20則）

**所有類型共用 — output_format 提取規則：**
| 使用者說 | output_format 值 |
|---------|-----------------|
| 「PDF」「下載」「生成PDF」「PDF供下載」 | `"pdf"` |
| 「Word」「docx」「Word檔」 | `"docx"` |
| 未提及 | 不填（留空，預設 text） |

⚠️ `output_format` 適用於所有 task_type（news/work_summary/language/custom）。
   news 類型若設定 output_format=pdf，**同時仍需** 在 extra_instructions 填入「統整成PDF供下載」（雙重觸發保障）。

### 🚫 絕對禁止
- **禁止把新聞需求設為 custom 或 reminder** — 只要出現「新聞」，type 必須是 `news`
- **禁止把所有需求都設為 custom** — custom 是最後手段
- **禁止 config 為空 `{}`** — 必須拆解到對應欄位
- **reminder 僅用於零內容生成的純提醒** — 需要 LLM 搜尋/生成 → 絕對不是 reminder

### 🔀 多內容類型請求 → 必須分拆為多次呼叫（Constraint #6）
當使用者的一句需求同時包含多種 `content_type` 或跨 task_type 內容，**必須分別呼叫 add 多次**：
- 「每天 8:30 推送 3 個 N1 文法和 10 個 N1 單字」→ **呼叫 2 次**：
  1. `add(type=language, config={content_type:"grammar", count:3, ...})`
  2. `add(type=language, config={content_type:"vocabulary", count:10, ...})`
- 「每天推送新聞和工作摘要」→ **呼叫 2 次**：
  1. `add(type=news, ...)`
  2. `add(type=work_summary, ...)`
- 每次呼叫成功後才進行下一個
- 確認訊息必須列出**實際建立的每一個** task 名稱，不得用「都設好了」等概括語
- ⚠️ 嚴禁將多種內容塞進一個 task — 一個 task 只能有一種 content_type

### 🔄 更新排程 → 直接 add，禁止 remove+add（Constraint #7）
當使用者要修改既有排程的參數（如「改成20則」「換成N2」），**直接呼叫 add**，傳入新參數。
系統有內建重複偵測：同 cron + 同 type → 自動更新既有 task，不會重複建立。

- ✅ 正確：直接 `add(type=news, cron="08:30", config={count:20, topic:"科技", ...})`
- ❌ 錯誤：先 `remove(task_id=...)` 再 `add(...)` — 你不一定有 task_id，且刪除會失敗
- ❌ 錯誤：問使用者「要我先查 task_id 嗎？」— 不需要，直接 add 就會自動更新

### ⚡ 建立排程後的行為規則
- 排程建立成功後，你只需要回覆使用者確認訊息（如「已幫你設定2分鐘後的任務」）
- **絕對禁止在建立排程後自己立刻執行任務內容**（不要搜尋、不要生成檔案、不要呼叫其他工具）
- 任務會由排程系統在指定時間自動執行

---

## Config 完整規格（依 task_type 分類）

### 📰 news — 新聞摘要
```json
{
  "topic": "經濟",
  "count": 20,
  "detail": "detailed",
  "extra_instructions": "包含國際趨勢與房市股市，標記出處，統整成PDF供下載"
}
```

| 欄位 | 必填 | 說明 |
|------|------|------|
| `topic` | ✅ | 新聞主題關鍵字（如「經濟」「科技」「AI」「國際」） |
| `count` | ✅ | 新聞數量（使用者說「20則」→ 20，未指定 → 10） |
| `detail` | ✅ | 摘要深度（見下方判定規則） |
| `extra_instructions` | 選填 | 額外需求 |

**detail 判定規則：**
| 使用者用語 | detail 值 |
|-----------|-----------|
| 「詳盡」「詳細」「深入」「越詳盡越好」「內容越詳細越好」 | `"detailed"` |
| 「簡要」「精簡」「簡單」「摘要就好」 | `"brief"` |
| 其他或未指定 | `"normal"` |

**extra_instructions 判定規則（從使用者原文提取）：**
- 提到「PDF」「下載」「檔案」→ 加入「統整成PDF供下載」
- 提到「包含…」「涵蓋…」→ 加入子主題要求
- 提到「出處」「來源」「標記出處」→ 加入「標記出處」
- 多個需求用逗號分隔

### 📋 work_summary — 工作重點摘要
```json
{
  "days": 7
}
```

| 欄位 | 必填 | 說明 |
|------|------|------|
| `days` | 選填 | 統整天數（預設 7 天） |

### 📖 language — 語言詞彙學習
```json
{
  "language": "日文",
  "level": "N3",
  "count": 5,
  "topic": "商務"
}
```

| 欄位 | 必填 | 說明 |
|------|------|------|
| `language` | ✅ | 語言（日文/英文/韓文等） |
| `level` | 選填 | 難度等級（N1-N5 / 初級/中級/高級） |
| `count` | 選填 | 詞彙數量（預設 5） |
| `topic` | 選填 | 主題領域（商務/旅遊/日常等） |

### ✏️ custom — 自訂內容（最後手段）
```json
{
  "prompt": "使用者的完整指令內容，逐字保留不可省略"
}
```

| 欄位 | 必填 | 說明 |
|------|------|------|
| `prompt` | ✅ | 使用者原文需求（完整保留） |

### ⏰ reminder — 一次性提醒
```json
{
  "message": "下午3點要開會"
}
```

| 欄位 | 必填 | 說明 |
|------|------|------|
| `message` | ✅ | 提醒內容 |

### 🔀 pipeline — 複合多技能任務
```json
{
  "original_request": "搜尋台灣股市新聞，翻成日文，整理成 PDF 供下載",
  "output_format": "pdf"
}
```

| 欄位 | 必填 | 說明 |
|------|------|------|
| `original_request` | ✅ | 使用者完整原文（系統自動填入，LLM 不需手動設定） |
| `output_format` | 選填 | 若需要檔案輸出：`pdf` / `docx`（未提及則不填） |

⚠️ pipeline 的 config 只需 `original_request` + `output_format`（選填）。
   **禁止**把其他 task_type 的欄位（topic/count/prompt 等）塞入 pipeline config。

---

## 正確範例 ✅ vs 錯誤範例 ❌

### 範例 1：新聞需求
使用者：「2分鐘後統整20則經濟新聞給我，包含國際趨勢與房市股市相關議題，內容越詳盡越好，請標記出處，並統整成PDF給我下載」

✅ **正確：**
```json
{
  "action": "add",
  "task_type": "news",
  "name": "2分鐘後經濟新聞統整PDF",
  "cron": "once +2m",
  "config": {
    "topic": "經濟",
    "count": 20,
    "detail": "detailed",
    "extra_instructions": "包含國際趨勢與房市股市相關議題，標記出處，統整成PDF供下載"
  }
}
```

❌ **錯誤（絕對禁止）：**
```json
{
  "action": "add",
  "task_type": "custom",
  "name": "2分鐘後統整20則經濟新聞並製成PDF",
  "cron": "once +2m",
  "config": {
    "original_request": "2分鐘後統整20則經濟新聞..."
  }
}
```
→ 提到「新聞」就必須用 `news`，且必須拆解出 topic/count/detail/extra_instructions

### 範例 2：語言學習
使用者：「每天早上9點推送5個日文N3商務詞彙」

✅ **正確：**
```json
{
  "action": "add",
  "task_type": "language",
  "name": "每日日文N3商務學習",
  "cron": "09:00",
  "config": {
    "language": "日文",
    "level": "N3",
    "count": 5,
    "topic": "商務"
  }
}
```

### 範例 3：一次性提醒
使用者：「10分鐘後提醒我去開會」

✅ **正確：**
```json
{
  "action": "add",
  "task_type": "reminder",
  "name": "開會提醒",
  "cron": "once +10m",
  "config": {
    "message": "該去開會了！"
  }
}
```

### 範例 4：間隔循環（每 X 分鐘）
使用者：「請設定每 10 分鐘傳給我 10 個義大利文詞彙（不能重複）」

✅ **正確：**
```json
{
  "action": "add",
  "task_type": "language",
  "name": "每10分鐘義大利文詞彙學習",
  "cron": "every +10m",
  "config": {
    "language": "義大利文",
    "count": 10
  }
}
```

❌ **錯誤：**
```json
{ "cron": "*/10" }          // 不支援
{ "cron": "*/10 * * * *" }  // 不支援（LLM 不可自行發明 cron 語法）
```

### 範例 5：複合跨域任務（pipeline）
使用者：「每天早上8點幫我搜尋台灣股市走勢，翻成日文，做成 PDF 給我下載」

✅ **正確：**
```json
{
  "action": "add",
  "task_type": "pipeline",
  "name": "每日股市日文PDF報告",
  "cron": "08:00",
  "config": {
    "output_format": "pdf"
  }
}
```
（`original_request` 由系統自動填入，不需 LLM 設定）

❌ **錯誤：**
```json
{ "task_type": "news" }   // 雖有新聞，但還需翻譯+轉語言 → 跨域依賴 → pipeline
{ "task_type": "custom", "config": { "prompt": "..." } }  // custom 無法自動規劃多步驟工具鏈
```

### 範例 6：真正的 custom（非新聞/非工作/非語言/非間隔/非複合）
使用者：「每天早上推送一則勵志名言給我」

✅ **正確（這才是 custom 的正確使用場景）：**
```json
{
  "action": "add",
  "task_type": "custom",
  "name": "每日勵志名言",
  "cron": "08:00",
  "config": {
    "prompt": "請生成一則勵志名言，包含名言內容、出處作者、以及一段30字以內的心得感悟。用繁體中文。"
  }
}
```

---

## 參數說明
- **action**（必填）：操作類型
- **task_type**（add 時必填）：推送內容類型，**必須根據「類型判定規則」正確選擇**
- **name**（add 時建議）：任務顯示名稱
- **cron**（add 時必填）：排程時間表達式
- **config**（add 時必填）：內容設定，**必須根據 task_type 填入對應欄位，禁止為空**
- **task_id**（remove/pause/resume/trigger 時必填）：目標任務 ID

---

## 執行後回覆規範 (Post-Action Response)

當成功呼叫此工具並取得成功回應後，你對使用者的最終回覆必須「**簡潔且僅確認狀態**」。

🚫 **嚴禁在回覆中附加任何以下內容：**
- 預覽或預先生成的任務內容（新聞摘要、提醒文字、工作統整等）
- 「以下是即將為您推送的內容…」之類的預覽
- 「系統正在為您準備…」之類的進度說明

### ✅ Post-Action 排程清單確認（強制執行）
每次 **add / remove / pause / resume** 操作完成後，**必須**接著呼叫 `list` 取得最新排程清單，
然後在確認訊息末尾附上格式化清單：

```
✅ 已為您設定排程：**[任務名稱]**
系統將會在 **[排程時間]** 自動為您執行。

📋 目前排程（共 N 個）：
① [task名稱] — [cron時間描述]
② [task名稱] — [cron時間描述]
...
```

**範例（建立 2 個語言學習 task 後）：**
> ✅ 已設定 2 個排程任務！
>
> 📋 目前排程（共 2 個）：
> ① 每日N1文法 — 每天 08:30
> ② 每日N1單字 — 每天 08:30
>
> 系統將在指定時間自動推送，有需要調整隨時告訴我！

⚠️ 此清單是從實際 JSON 取得的真實資料，不是 LLM 自行編造。若清單與使用者預期不符，主動說明差異並詢問是否補齊。
