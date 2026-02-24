---

name: slack-gif-creator
version: "1.0.0"
description: 為 Slack 優化的 GIF 動畫製作知識與工具組。提供規格限制、驗證工具和動畫概念。當使用者要求製作 Slack 用的 GIF 動畫時使用，例如「幫我做一個 X 在做 Y 的 Slack 用 GIF」。
license: Complete terms in LICENSE.txt
---

# Slack GIF Creator（Slack GIF 動畫製作工具）

提供工具和知識，用於建立針對 Slack 優化的 GIF 動畫的工具組。

## Slack 規格要求

**尺寸：**
- 表情符號 GIF：128x128（建議）
- 訊息 GIF：480x480

**參數：**
- FPS：10-30（愈低 = 檔案愈小）
- 顏色數：48-128（愈少 = 檔案愈小）
- 時長：表情符號 GIF 保持在 3 秒以內

## 核心工作流程

```python
from core.gif_builder import GIFBuilder
from PIL import Image, ImageDraw

# 1. 建立 builder
builder = GIFBuilder(width=128, height=128, fps=10)

# 2. 生成畫格
for i in range(12):
    frame = Image.new('RGB', (128, 128), (240, 248, 255))
    draw = ImageDraw.Draw(frame)

    # 使用 PIL 基本圖形繪製動畫
    # （圓形、多邊形、線條等）

    builder.add_frame(frame)

# 3. 儲存並優化
builder.save('output.gif', num_colors=48, optimize_for_emoji=True)
```

## 繪製圖形

### 處理使用者上傳的圖片
若使用者上傳了圖片，考慮他們是想要：
- **直接使用**（例如「幫這個加上動畫」、「把這個分割成畫格」）
- **作為靈感**（例如「做一個像這樣的」）

使用 PIL 載入並處理圖片：
```python
from PIL import Image

uploaded = Image.open('file.png')
# 直接使用，或僅作為顏色 / 風格的參考
```

### 從頭繪製
從頭繪製圖形時，使用 PIL ImageDraw 基本圖形：

```python
from PIL import ImageDraw

draw = ImageDraw.Draw(frame)

# 圓形 / 橢圓
draw.ellipse([x1, y1, x2, y2], fill=(r, g, b), outline=(r, g, b), width=3)

# 星形、三角形、任何多邊形
points = [(x1, y1), (x2, y2), (x3, y3), ...]
draw.polygon(points, fill=(r, g, b), outline=(r, g, b), width=3)

# 線條
draw.line([(x1, y1), (x2, y2)], fill=(r, g, b), width=5)

# 矩形
draw.rectangle([x1, y1, x2, y2], fill=(r, g, b), outline=(r, g, b), width=3)
```

**不要使用：** 表情符號字體（跨平台不可靠）或假設此技能中有預先打包的圖形。

### 讓圖形看起來精緻

圖形應看起來精緻有創意，而不是基本款。方法如下：

**使用較粗的線條** — 輪廓和線條務必設定 `width=2` 或更高。細線條（width=1）看起來粗糙業餘。

**增加視覺層次感**：
- 使用漸層作為背景（`create_gradient_background`）
- 疊加多個形狀增加複雜度（例如一個大星形中有一個小星形）

**讓形狀更有趣**：
- 不要只畫一個普通圓形——加上高光、圓環或圖案
- 星形可以有光暈效果（在後面繪製更大的半透明版本）
- 組合多個形狀（星形 + 閃光、圓形 + 光環）

**注意顏色**：
- 使用鮮豔的對比色
- 增加對比度（淺色形狀配深色輪廓，深色形狀配淺色輪廓）
- 考慮整體構圖

**複雜形狀**（愛心、雪花等）：
- 使用多邊形和橢圓的組合
- 仔細計算點的位置以保持對稱
- 添加細節（愛心可以有高光曲線，雪花有精緻分支）

發揮創意並注重細節！好的 Slack GIF 應看起來精緻，而不是佔位符圖形。

## 可用工具

### GIFBuilder（`core.gif_builder`）
組合畫格並針對 Slack 優化：
```python
builder = GIFBuilder(width=128, height=128, fps=10)
builder.add_frame(frame)  # 新增 PIL Image
builder.add_frames(frames)  # 新增畫格列表
builder.save('out.gif', num_colors=48, optimize_for_emoji=True, remove_duplicates=True)
```

### Validators（`core.validators`）
確認 GIF 是否符合 Slack 要求：
```python
from core.validators import validate_gif, is_slack_ready

# 詳細驗證
passes, info = validate_gif('my.gif', is_emoji=True, verbose=True)

# 快速確認
if is_slack_ready('my.gif'):
    print("就緒！")
```

### Easing Functions（`core.easing`）
平滑動作，而非線性移動：
```python
from core.easing import interpolate

# 進度從 0.0 到 1.0
t = i / (num_frames - 1)

# 套用緩動
y = interpolate(start=0, end=400, t=t, easing='ease_out')

# 可用：linear、ease_in、ease_out、ease_in_out、
#        bounce_out、elastic_out、back_out
```

### Frame Helpers（`core.frame_composer`）
常見需求的便利函數：
```python
from core.frame_composer import (
    create_blank_frame,         # 純色背景
    create_gradient_background,  # 垂直漸層
    draw_circle,                # 圓形輔助函數
    draw_text,                  # 簡單文字渲染
    draw_star                   # 五角星
)
```

## 動畫概念

### 搖晃 / 震動
用振盪偏移物件位置：
- 使用 `math.sin()` 或 `math.cos()` 搭配畫格索引
- 加入小幅隨機變化以獲得自然感
- 套用於 x 和 / 或 y 位置

### 脈動 / 心跳
有節奏地縮放物件大小：
- 使用 `math.sin(t * frequency * 2 * math.pi)` 實現平滑脈動
- 心跳效果：兩次快速脈動後停頓（調整正弦波）
- 在基本尺寸的 0.8 到 1.2 之間縮放

### 彈跳
物件落下並彈起：
- 落地時使用 `interpolate()` 搭配 `easing='bounce_out'`
- 下落時使用 `easing='ease_in'`（加速）
- 每幀增加 y 速度以模擬重力

### 旋轉 / 自轉
繞中心旋轉物件：
- PIL：`image.rotate(angle, resample=Image.BICUBIC)`
- 晃動效果：使用正弦波控制角度而非線性

### 淡入 / 淡出
逐漸出現或消失：
- 建立 RGBA 圖片，調整 alpha 通道
- 或使用 `Image.blend(image1, image2, alpha)`
- 淡入：alpha 從 0 到 1
- 淡出：alpha 從 1 到 0

### 滑動
物件從畫面外移動到目標位置：
- 起始位置：畫格邊界外
- 結束位置：目標位置
- 使用 `interpolate()` 搭配 `easing='ease_out'` 實現平滑停止
- 超過目標：使用 `easing='back_out'`

### 縮放
縮放和定位以產生縮放效果：
- 放大：從 0.1 縮放到 2.0，裁切中心
- 縮小：從 2.0 縮放到 1.0
- 可加入動態模糊增加戲劇感（PIL filter）

### 爆炸 / 粒子爆發
建立向外輻射的粒子：
- 以隨機角度和速度生成粒子
- 每幀更新：`x += vx`、`y += vy`
- 加入重力：`vy += gravity_constant`
- 隨時間淡出粒子（降低 alpha）

## 優化策略

只有在被要求縮小檔案大小時，才實施以下幾種方法：

1. **減少畫格數** — 降低 FPS（10 而非 20）或縮短時長
2. **減少顏色數** — `num_colors=48` 而非 128
3. **縮小尺寸** — 128x128 而非 480x480
4. **移除重複畫格** — 在 save() 中設定 `remove_duplicates=True`
5. **表情符號模式** — `optimize_for_emoji=True` 自動優化

```python
# 表情符號最大優化
builder.save(
    'emoji.gif',
    num_colors=48,
    optimize_for_emoji=True,
    remove_duplicates=True
)
```

## 設計理念

此技能提供：
- **知識**：Slack 的規格要求和動畫概念
- **工具組**：GIFBuilder、validators、easing functions
- **靈活性**：使用 PIL 基本圖形建立動畫邏輯

不包含：
- 固定的動畫範本或預製函數
- 表情符號字體渲染（跨平台不可靠）
- 預先打包的圖形函式庫

**關於使用者上傳**：此技能不含預製圖形，但若使用者上傳了圖片，可用 PIL 載入並處理——根據他們的請求判斷是直接使用還是作為靈感。

發揮創意！組合各種概念（彈跳 + 旋轉、脈動 + 滑動等），充分運用 PIL 的所有功能。

## 相依套件

```bash
pip install pillow imageio numpy
```
