# scummvm-agos-cjk

給 ScummVM **AGOS 引擎**(Elvira 1/2、Waxworks、Simon 1/2、Feeble Files)做 CJK 中文化的
共用基礎:引擎 patch、字型工具、驗證腳本,以及一份把踩過的坑寫清楚的文件。

AGOS 跟 SCUMM 不一樣 —— **丟字型檔進去是沒用的**。它的文字渲染是固定的英文小點陣、
不認雙位元組,硬編碼的 UI 不經字串表,320×200 的畫布也塞不下全形中文。
所以 AGOS 的中文化一定要改引擎,而每個做這件事的人都會撞上同一批問題。
這個 repo 就是把那批問題的解法集中起來,不必每款遊戲重踩一次。

## 這裡有什麼

| 目錄 | 內容 |
|---|---|
| `patches/` | 對 ScummVM 的引擎 patch,以及對應的版本記錄 |
| `src/` | 中文化新增的檔案(字型／譯表載入器) |
| `tools/` | 字型烘焙(TTF 與倚天點陣字)、疊層座標回歸測試、ASan 掃描 |
| `docs/` | [**AGOS_PITFALLS.md**](docs/AGOS_PITFALLS.md) — 踩過的坑總覽,每條含根因與驗證方法 |

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

其中若有屬於上游缺陷的部分(見 `AGOS_PITFALLS.md` §3.4),會標註清楚是上游的程式碼、
由什麼條件觸發,方便日後判斷是否值得另外送 patch 給 ScummVM。

## 使用這套的專案

- [古堡禁地 Elvira: Mistress of the Dark (1990) 繁中化](https://github.com/wicanr2/Elvira-Mistress_of_the_Dark_1990-cht)

## 授權

引擎 patch 衍生自 ScummVM,依 **GPLv3** 釋出。
工具腳本同樣 GPLv3。字型檔本身不隨庫散布 —— 倚天中文系統的點陣字模有版權,
`build_eten_font.py` 只是格式轉換工具,需自備原始字模。
