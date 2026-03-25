---
name: mcp-schedule-manager
provider: mcp
version: 1.3.0
runtime_requirements: []
description: >
  定時推送與提醒管理工具。當使用者要求「每天早上推送新聞」、「每週五下班前提醒我」、
  「定時推送工作摘要」、「幫我設定排程」、「取消推送」等帶有時間排程意圖的指令時，
  必須使用此工具。此工具可新增、列出、刪除、暫停及恢復排程任務。
  支援類型：news（新聞摘要）、work_summary（工作重點）、language（語言學習）、custom（自訂內容）。
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
        custom=自訂內容、reminder=一次性提醒。
        【極重要】必須根據下方「類型判定規則」正確選擇，不可隨意使用 custom。
      enum: ["news", "work_summary", "language", "custom", "reminder"]
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

### # Field Mapping Logic（欄位對齊邏輯）

**第一步：判定 task_type**
| 優先序 | 類型 | 判定條件（語意掃描） | 範例輸入 |
|--------|------|----------------------|----------|
| 1 | **news** | 出現「新聞/頭條/時事/報導/財經資訊」 | 「統整新聞」「推送20則經濟新聞」「新聞給我」 |
| 2 | **work_summary** | 出現「工作摘要/工作統整/週報/工作重點」 | 「推送工作摘要」 |
| 3 | **language** | 出現「學習/詞彙/單字」且有語種 | 「日文N3詞彙」 |
| 4 | **reminder** | 純粹提醒，**完全不需要 LLM 生成內容** | 「提醒我開會」「提醒我買牛奶」 |
| 5 | **custom** | 以上全部不匹配（最後手段） | 「推送勵志名言」「推送笑話」 |

⚠️ **「X分鐘後」是排程時間，不是類型判定依據！**
- 「2分鐘後統整新聞」→ type=**news**（有「新聞」）, cron="once +2m"
- 「10分鐘後提醒我開會」→ type=**reminder**（純提醒，語氣請幽默風趣切勿死板）

**第二步：提取 config 欄位（依 task_type）**

#### news 欄位拆解：
| 欄位 | 提取邏輯 | 範例 |
|------|----------|------|
| `topic` | 提取**主題/領域關鍵字**，不是動作詞。掃描：經濟/股市/房市/科技/AI/國際/政治/金融/產業/能源/醫療... 也掃「XXX相關議題」中的XXX | 「股市新聞」→`"股市"`, 「經濟新聞，股市相關議題」→`"經濟 股市"` |
| `count` | 提取數字+則/條/篇 | 「20則」→`20`, 未指定→`10` |
| `detail` | 「詳盡/詳細/深入/越X越好」→`"detailed"`, 「簡要/精簡」→`"brief"`, 其他→`"normal"` | 「越詳盡越好」→`"detailed"` |
| `extra_instructions` | 提取：格式需求(PDF/DOCX)、子主題(包含...)、出處要求 | 「包含國際趨勢，標記出處，統整成PDF」 |

🚨 **topic 禁止填入**：動作詞（統整/推送/給我）、時間（分鐘後/每天）、格式（PDF）、數量（20則）

### 🚫 絕對禁止
- **禁止把新聞需求設為 custom 或 reminder** — 只要出現「新聞」，type 必須是 `news`
- **禁止把所有需求都設為 custom** — custom 是最後手段
- **禁止 config 為空 `{}`** — 必須拆解到對應欄位
- **reminder 僅用於零內容生成的純提醒** — 需要 LLM 搜尋/生成 → 絕對不是 reminder

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

### 範例 4：真正的 custom（非新聞/非工作/非語言）
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

✅ **標準回覆格式（照此輸出，不可偏離）：**

```
✅ 已為您設定排程：**[任務名稱]**
系統將會在 **[排程時間/觸發條件]** 自動為您執行。
```

**範例：**
> ✅ 已為您設定排程：**2分鐘後社會案件新聞統整**
> 系統將會在 **2 分鐘後（14:57）** 自動為您執行。
