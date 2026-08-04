# scummvm-agos-cjk

給 ScummVM **AGOS 引擎**(Elvira 1/2、Waxworks、Simon 1/2、Feeble Files)做 CJK 中文化的
共用基礎:引擎 patch、字型工具、驗證腳本,以及一份把踩過的坑寫清楚的文件。

AGOS 跟 SCUMM 不一樣 —— **丟字型檔進去是沒用的**。它的文字渲染是固定的英文小點陣、
不認雙位元組,硬編碼的 UI 不經字串表,320×200 的畫布也塞不下全形中文。
所以 AGOS 的中文化一定要改引擎,而每個做這件事的人都會撞上同一批問題。
這個 repo 就是把那批問題的解法集中起來,不必每款遊戲重踩一次。

## ⚠️ 高成本事故警告：翻譯只能用於顯示，不能改變程式語意

這條規則必須在開始中文化前就處理，不能等玩家當機後才補救。一次看似方便的
「在 `getStringPtrByID()` 統一回傳譯文」，已在三款遊戲造成兩類完全不同的異常，
並浪費大量除錯、編譯、跨平台打包與 AI token 成本：

- **Elvira 1（已證實）**：腳本用英文敵人名稱做分類比較；全域翻譯改變比較值，
  使戰鬥圖片編號停在 0，最後誤載不存在的 `002.VGA`。
- **Elvira 2（已證實的程式路徑）**：`oe1_loadGame()` 的 `Start` 是重新開始狀態的
  **實體檔名**，不是按鈕文字。翻成「開始」後，程式會嘗試開啟不存在的中文檔名。
- **Waxworks（已證實的程式路徑）**：同一 opcode 使用 `START` 載入初始狀態；翻譯後
  同樣找不到檔案，呼叫端又未中止流程，可能讓遊戲帶著殘留或未完成狀態繼續執行。

根本原則只有一句：

> **翻譯是顯示層資料；比較、檔名、資源鍵、存讀檔、序列化與腳本識別值必須保留原文。**

正確 API 應讓顯示呼叫預設本地化，語意呼叫則明確停用本地化，例如：

```cpp
const byte *getStringPtrByID(uint16 stringId,
                             bool upperCase = false,
                             bool localize = true);

// 顯示文字：允許翻譯
showText(getStringPtrByID(stringId));

// 內部檔名：必須取得原文
loadGame((const char *)getStringPtrByID(stringId, false, false), true);
```

### 動手修改前的強制稽核

不要只修已出錯的那個呼叫點。任何全域翻譯掛勾上線前，必須盤點其所有呼叫者，
並至少分成以下兩組：

| 用途 | 是否可翻譯 | 必查範例 |
|---|---:|---|
| 畫面、對話、選單、提示 | 是 | render、print、message、caption |
| 條件比較、物件分類 | 否 | compare、isCalled、equals、switch key |
| 檔案與資源查找 | 否 | loadGame、open、Path、VGA、zone、音訊名稱 |
| 存讀檔與序列化 | 否 | save slot、restart state、config key、archive member |
| 腳本與跨系統識別值 | 否 | opcode 參數、ID 對映、協定欄位 |

建議先搜尋 `getStringPtrByID`、譯表查詢及所有等價入口，再沿每個呼叫點追到最終用途。
如果用途無法立刻證明是顯示，就先按「不可翻譯」處理並記為待查，不能用調整個別譯文
來配合隱藏規則。完整設計說明見
[中文化的顯示與語意隔離](docs/LOCALIZATION_SEMANTIC_ISOLATION.md)。

### 防止再次浪費 token 的最小驗收閘門

1. **語意 A/B**：同一流程分別開啟／關閉翻譯；除畫面文字外，檔名、ID、分支與狀態必須一致。
2. **負向測試**：故意把 `Start`／`START` 翻成完全不同的合理譯文，語意路徑仍須開啟原檔。
3. **乾淨 patch**：從指定 ScummVM tag 套用 canonical patch；被忽略的 build tree 成功不算。
4. **兩種套用器**：同時通過 `patch -p1 --dry-run` 與 `git apply --check`。兩者容錯不同；
   本次 Waxworks patch 曾出現前者接受、後者判定 `corrupt patch`，造成一次無效 macOS CI。
5. **乾淨完整編譯**：不能只看 patch 套用成功或單一物件檔編過。
6. **玩家路徑與實際封包**：驗證受影響流程及 Linux、Windows、macOS 的真實成品；
   Windows ZIP 另查 UTF-8 檔名旗標與 README UTF-8 BOM。
7. **最後才跨平台重打包**：上述便宜閘門全部通過後才啟動 MinGW 與 macOS universal CI，
   避免用昂貴建置反覆驗證本可由靜態稽核立即發現的錯誤。

證據分級：Elvira 1 已有玩家繁中／英文 A/B 與 log 證實完整症狀；Elvira 2 與
Waxworks 已由腳本 opcode、翻譯表、實體檔名及引擎呼叫鏈證實舊路徑必然查錯檔名，
修正亦通過乾淨編譯與三平台建置，但不應把尚未取得的特定玩家症狀描述成已實機重現。

## 這裡有什麼

| 目錄 | 內容 |
|---|---|
| `patches/` | 對 ScummVM 的引擎 patch,以及對應的版本記錄 |
| `src/` | 中文化新增的檔案(字型／譯表載入器) |
| `tools/` | 字型烘焙(TTF 與倚天點陣字)、疊層座標回歸測試、ASan 掃描 |
| `docs/` | [**AGOS_PITFALLS.md**](docs/AGOS_PITFALLS.md) — 踩過的坑總覽,每條含根因與驗證方法 |
| `docs/` | [**ASAN_GUIDE.md**](docs/ASAN_GUIDE.md) — 用 ASan 抓疊層越界:怎麼編、五個情境怎麼跑、報告怎麼讀 |
| `docs/` | [**LOCALIZATION_SEMANTIC_ISOLATION.md**](docs/LOCALIZATION_SEMANTIC_ISOLATION.md) — 翻譯與腳本語意的責任邊界 |

## 核心解法:用 overlay 層當 hi-res compositor

原生 320×200 塞不下清晰中文,而引擎給 PC-98 版準備的 640×400 雙層畫布在 DOS 版
強套會 heap 損壞崩潰(佈局相依的 heisenbug,插樁就消失)。

可行的路是**用 ScummVM 自己的 overlay 層**:每幀把穩定的遊戲畫面升採進 overlay,
在上面畫中文,遊戲的渲染路徑完全不碰。

這條路的關鍵教訓是 **overlay 的尺寸不是常數**:Retina 高 DPI 會回報物理像素
(實測 2788×1768)、玩家改縮放倍率、切全螢幕、開比例校正都會變,
而且 SurfaceSDL 後端的 overlay 是 2 bytes/px、OpenGL 是 4。
座標寫死任何倍率遲早會咬人 —— 正解是把座標寫在「基準空間 640×400」,
繪製時用**區間映射**換算到實際尺寸(細節見 `AGOS_PITFALLS.md` §2.2)。

## 工具

```bash
# 字型:TTF → DCJK 點陣 atlas(注意高度要比行距小,見 PITFALLS §4)
python3 tools/build_cjk_font.py --size 16 --height 15 --font <ttf> --out zh16.dcjk

# 字型:倚天中文系統原生點陣字 → DCJK(1990 年 DOS 中文的字形原貌)
python3 tools/build_eten_font.py --size 15 --std stdfont.15 --spc SPCFONT.15 --out zh16.dcjk
python3 tools/build_eten_font.py --size 15 --bold --std stdfont.15 --spc SPCFONT.15 --out zh16b.dcjk

# 疊層座標回歸測試:各倍率截圖比對(x2 是基準,x4 等同 Retina 條件)
tools/qa_overlay_scale.sh x4 4 1280 800
tools/qa_overlay_check.sh x2 x4

# ASan 掃描:越界讀不會立刻崩潰,靠「跑跑看」測不出來,要用這個
tools/asan_sweep.sh x4 51 --no-aspect-ratio --scale-factor=4
```

## 為什麼不送去上游

ScummVM 上游不會收「某個語言的中文化」這種改動,而等待與追版本的成本比自己維護高。
這裡的作法是**對特定 ScummVM 版本維護 patch**(目前基準 v2.9.1),
換版本時重對一次並記錄在 `patches/UPSTREAM.md`。

patch 裡也包含一處 backend 的修正(`surfacesdl-graphics.cpp`):比例校正誤判
「overlay 顯示中 = GUI 開著」,遇到持續顯示的疊層會把畫面校正兩次而寫出緩衝區。
改動對 ScummVM 原本的行為零影響,根因與驗證見 `AGOS_PITFALLS.md` §3.4。

## 使用這套的專案

- [古堡禁地 Elvira: Mistress of the Dark (1990) 繁中化](https://github.com/wicanr2/Elvira-Mistress_of_the_Dark_1990-cht)

## 案例研究

[**不會當場炸的越界:zone 上界失守與隨機當機**](docs/BUG_ZONE_BOUNDS.md)
—— 圖號 ÷ 100 算出的 zone 可達 655,陣列只有 450,而上游是先取元素才做邊界檢查。
越界的位置落在 `AGOSEngine` 物件內部,所以不會當場崩潰,而是拿到垃圾指標後在無關的地方倒下。
**ASan 抓不到這一類**(同一塊配置內部的越界),五輪掃描全乾淨,是讀程式碼才發現的。
內含上界怎麼從實際資料量出來、為什麼加大陣列解決不了,以及一個假驗證的教訓。

[`Can't load 002.VGA` 追查報告](https://github.com/wicanr2/Elvira-Mistress_of_the_Dark_1990-cht/blob/main/docs/BUG_002VGA_ZONE0.md)
—— 玩家繁中／英文對照證實，全域翻譯掛勾污染了敵人名稱的腳本比較，使戰鬥圖片
編號停在 0。報告保留早期把問題誤判為資料漏洞與座標錯位的證據鏈，也說明為何
「缺圖就略過」會把中止改成凍結。共用設計原則見 `LOCALIZATION_SEMANTIC_ISOLATION.md`。

## 授權

引擎 patch 衍生自 ScummVM,依 **GPLv3** 釋出。
工具腳本同樣 GPLv3。字型檔本身不隨庫散布 —— 倚天中文系統的點陣字模有版權,
`build_eten_font.py` 只是格式轉換工具,需自備原始字模。
