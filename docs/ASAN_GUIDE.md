# 用 AddressSanitizer 抓疊層的記憶體越界

疊層合成不是偶爾跑一次的程式碼:每一幀都把整個 320×200 的遊戲畫面重新映射、升採樣到 overlay
的實際尺寸,再把中文畫上去。而 overlay 的尺寸不是常數(Retina 回報物理像素、玩家改縮放倍率、
比例校正、切全螢幕都會變),所以那些索引每一輪都在不同的數字上算。算錯一格就是越界。

麻煩的是這種錯不會準時發作。越界**寫**通常很快炸,因為它破壞了別人的資料;越界**讀**不會 ——
它只是讀到隔壁的記憶體,拿到一個看起來合理的值,程式繼續跑,頂多畫面內容不太對。
會不會 SIGSEGV 取決於當下的記憶體佈局:那塊記憶體有沒有被映射、裡面是什麼。

實測對照就是這個形狀:第一顆疊層越界在無頭 Linux 上**一次都沒重現過**,而玩家的 macOS
上玩一陣子就掛(`AGOS_PITFALLS.md` §3.2)。後來為了確認修正有效而做的壓力測試,
單輪 500 次密集互動、跑了兩輪(兩種顯示後端各一),同樣一次都沒觸發。所以在這個專案裡,
「跑跑看沒問題」不構成證據 —— 要換一種工具,讓「讀到不該讀的位置」這件事本身當場報錯,
而不是等它剛好造成後果。AddressSanitizer(ASan)做的就是這件事。

---

## ASan 在做什麼

兩件事:編譯時對每個記憶體存取插樁,執行時換掉記憶體配置器。

配置器會在每塊配置出來的記憶體前後夾一段被毒化的區域,叫 redzone(紅區);碰到它就報錯。
插樁則是讓每次載入/儲存之前先查一張表,那張表叫 shadow memory(影子記憶體),
用 1/8 的額外記憶體記錄「每 8 bytes 的可定址狀態」。

從這兩個機制可以直接推出它的能力範圍。抓得到的是 heap / stack / global 的越界讀寫、
use-after-free、use-after-return、double-free,以及記憶體洩漏(LeakSanitizer,預設會一起開)。
代價是速度約慢 2 倍、記憶體約 3 倍 —— 互動式遊戲仍然點得動,手動操作與 `xdotool` 腳本都照跑。

---

## [HARD] 它抓不到的三類

### 一、同一塊配置內部的越界

redzone 在**配置的邊界**上,配置內部沒有邊界可言。struct 裡從欄位 A 越界寫到欄位 B、
或一塊大 buffer 內部的子陣列越界,ASan 一聲不吭。

這在本專案真的發生過。`engines/agos/agos.h` 裡:

```cpp
VgaPointersEntry _vgaBufferPointers[450];   // 每個 entry 6 個指標 = 48 bytes
VgaSprite        _vgaSprites[200];
VgaSleepStruct   _onStopTable[60];
```

zone 編號是從圖號算出來的:`zoneNum = vgaSpriteId / 100`。圖號是 16-bit,最大 65535,
所以 zone 算得出 655,而陣列只有 450 個 entry。實際遇到的 zone 650 索引下去,
位址落在陣列尾端之後 (650 − 450) × 48 = **9600 bytes** 處 —— 但那裡是 `_vgaSprites`、
`_onStopTable` 這些同一個 `AGOSEngine` 物件裡的成員,整個物件是一次配置出來的,
**沒有跨過任何 redzone**。ASan 掃十輪都是乾淨的。

這顆是讀程式碼發現的,修法是在索引前先擋上界:

```cpp
if (zoneNum >= ARRAYSIZE(_vgaBufferPointers)) {
    warning("%s: zone %d 超出範圍(sprite id %d), 跳過此圖", __FUNCTION__, zoneNum, vgaSpriteId);
    return;
}
```

順帶一提,上游 `for(;;)` 迴圈裡的 `loadZone()` 有 `CHECK_BOUNDS` 斷言,但迴圈是**先**取
`&_vgaBufferPointers[zoneNum]` 才進 `loadZone` 的 —— 越界讀發生在斷言之前,斷言擋不到。

### 二、邏輯錯誤

(這一顆的完整分析與「為什麼不是把陣列開大」見 `AGOS_PITFALLS.md` §3.8;修正已收進本 repo 的 `patches/agos-cjk.patch`。)

ASan 只管位址合不合法,不管值對不對。`AGOS_PITFALLS.md` §3.7 那顆(遊戲腳本的條件分派
缺 default 分支,讓圖號停在 0,一路走到 `error()` 中止)全程沒有任何非法存取,
ASan 完全看不到。這類問題要靠反組譯與 log。

### 三、資料競爭與未初始化讀取

前者是 TSan 的守備範圍(而且 TSan 不能和 ASan 同時開),後者是 MSan(要整條依賴鏈都插樁,
門檻高)。ASan 對這兩類沒有覆蓋。

**所以「ASan 乾淨」的正確讀法是:沒有跨配置邊界的存取。** 不是「沒有 bug」。

---

## 怎麼編

編譯與連結都要帶旗標,少一邊會連結失敗或靜默失效:

```bash
CXXFLAGS="-fsanitize=address -fno-omit-frame-pointer -g -O1" \
LDFLAGS="-fsanitize=address" \
./configure --disable-all-engines --enable-engine=agos \
    --disable-mad --disable-vorbis --disable-flac --disable-fluidsynth \
    --disable-mpeg2 --disable-theoradec --disable-faad --disable-libcurl
make -j$(nproc)
```

`-fno-omit-frame-pointer` 沒帶的話 stack trace 會殘缺;`-g` 提供符號與行號;
`-O1` 是折衷 —— `-O0` 慢到互動測試點不動,`-O2` 以上可能把出事的那行 inline 掉,行號變得難讀。

### [HARD] 一定要在乾淨的樹編

原本 build 樹裡的 `.o` / `.a` 沒有插樁。混在一起時,那些部分**不會被檢查,而且不會有任何提示**
—— 得到的是一份看起來很漂亮的假乾淨。

```bash
# 複製原始碼到獨立目錄,不帶既有的編譯產物
tar cf - --exclude="*.o" --exclude="*.a" --exclude=".git" --exclude="scummvm" . \
    | tar xf - -C /path/asan-src
cd /path/asan-src && rm -f config.mk config.h     # 舊的 configure 結果也要清
```

同一個坑的另一種形狀:mingw 交叉編譯時,共用樹裡殘留的 ELF `.o` 會被 mingw ld 靜默跳過,
症狀是「符號明明有定義卻連結失敗」。凡是換工具鏈或換旗標,一律用新的樹。

可直接抄的實作在 Elvira 中文化專案的 `scripts/build_asan.sh`(在 docker 內做上面這一整套,
產物落在 `build/asan-src/scummvm`,不動出貨用的 build 樹)。

---

## 怎麼跑

```bash
ASAN_OPTIONS="detect_leaks=0:halt_on_error=1:print_stacktrace=1" \
    ./scummvm -d1 -p /path/game --auto-detect -e null
```

`detect_leaks=0` 關掉 LeakSanitizer:找越界的時候,一整頁「程式結束時沒釋放」的報告只會蓋住重點,
要查洩漏時再單獨開一輪。`halt_on_error=1` 與 `print_stacktrace=1` 是預設值,寫出來是為了明確。

### 一個 process 只報第一顆錯

除非編譯時加 `-fsanitize-recover=address` 並設 `halt_on_error=0`,ASan 報完第一顆就中止。
這直接決定測試怎麼設計:**每個情境各跑一輪獨立的 process**,不要指望一次跑完全部。
第一顆會把後面的完全遮住,而被遮住的那些不會留下任何跡象。

這在本專案有實例。疊層合成的越界(`chtOverlayCompose`)修好之前,同一套操作腳本掃出來只有它;
修好之後再跑同一輪,才浮出第二顆 `stretch200To240Nearest`(§3.4)。
所以修完一顆要重掃,不能假設剩下的乾淨。

---

## 情境矩陣

隨機亂測的覆蓋率很差。有效的作法是沿著程式碼的分支點展開:哪裡有 `if` 決定走不同的記憶體路徑,
就讓每一邊各跑到一輪。疊層這條路上有五個必跑的情境:

| 情境 | 實際的疊層條件 | 為什麼要單獨一輪 |
|---|---|---|
| x2 | 640×480,2 bytes/px,映射 1.00x / 1.20y | 基準,最單純的映射 |
| x3 | 960×720,映射 1.50x / 1.80y | 非整數倍,升採樣的索引計算只在這裡踩到邊界 |
| x4 | 1280×960,映射 2.00x / 2.40y | 等同 Retina 回報物理像素的條件(無頭環境沒有 HiDPI,只能這樣造) |
| OpenGL | 800×600,**4 bytes/px** | 另一條合成分支(SurfaceSDL 是 2 bytes/px) |
| 比例校正 | 640×480 + 200→240 拉伸 | 先前爆掉的組合,緩衝區大小不同 |

跑法(腳本在 `tools/asan_sweep.sh`,參數是 `標籤 display 額外參數`):

```bash
tools/asan_sweep.sh x2      51 --scale-factor=2
tools/asan_sweep.sh x3      52 --scale-factor=3
tools/asan_sweep.sh x4      53 --scale-factor=4
tools/asan_sweep.sh gl      54 --gfx-mode=opengl --scale-factor=3
tools/asan_sweep.sh aspect  55 --aspect-ratio --scale-factor=2
```

腳本在 docker 裡起 Xvfb、等視窗出現、進遊戲,然後用 `xdotool` 做密集互動(移動、動詞面板、
地圖開關、無敵切換、存讀檔的模態選單、場景切換),最後把 ASan 命中的段落抓出來。
用之前要把檔案開頭的 `BIN`(ASan 執行檔目錄)與 `PROJ`(遊戲與 log 所在的專案目錄)
改成自己的路徑。OpenGL 那一輪需要 24 位色深加 `LIBGL_ALWAYS_SOFTWARE=1`,
腳本目前寫死 `x16`,跑之前要改(色深選擇的完整理由見 Elvira 專案的 `docs/TESTING.md`)。

### 跑完先確認條件真的生效

倍率參數沒吃到的話,疊層尺寸不會變,那一輪等於白跑 —— 而結果看起來一樣是「乾淨」。
所以每輪都要看 `CHTOVL:` 那行印出來的實際 overlay 尺寸與 bpp,對得上矩陣裡的數字才算數。
這是整份流程裡最容易自我欺騙的一步。

---

## 判讀報告

```
ERROR: AddressSanitizer: heap-buffer-overflow on address 0x... at pc 0x...
WRITE of size 1280
    #1 stretch200To240Nearest(...)   graphics/scaler/aspect.cpp:123
    #3 SurfaceSdlGraphicsManager::internUpdateScreen()
0x... is located 0 bytes to the right of 614400-byte region
```

讀的順序:

1. **`WRITE` 還是 `READ`,size 多少。** WRITE 通常更急。size 是一次操作的位元組數,
   `1280` 這種數字往往等於「一列的寬度 × 每像素位元組」(640 × 2),能直接反推是哪個迴圈。
2. **`located N bytes to the right of M-byte region`。** `to the right` 是越過尾端,
   `to the left` 是往前越界。`M` 拿去反推「應該是幾乘幾」通常一眼就看出算錯在哪 ——
   `614400 = 640 × 480 × 2`,一個 640×480、2 bytes/px 的 overlay,而 `WRITE` 卻寫到第 575 列。
3. **stack trace 裡第一個專案內的函式。** 前幾層常是 libc 或 sanitizer 自己的框架,
   往下找到 `engines/agos/` 或 `backends/` 的檔名才是現場。
4. **配置點的 trace**(報告後半段的 `allocated by thread T0 here`)。確認那塊記憶體當初照什麼尺寸配的,
   跟第 2 步反推的數字對起來。

### 沒有 ASan 時的等價資訊

只有玩家端 log、自己重現不出來的時候,平台原生的 crash report 提供同樣的判斷材料。
macOS 的 crash report 會印 `KERN_INVALID_ADDRESS at 0x...` 加上一張記憶體區段圖;
如果出事位址正好是某塊 region 的**結束位址 +1**,那就是越界,和 ASan 的
`0 bytes to the right` 是同一件事。

本專案第一顆疊層越界(§3.3)就是這樣定位的 —— 先從玩家的 crash report 讀出「越過緩衝區尾端」,
再在本機用 ASan 重現,兩邊的堆疊完全一致,才確定抓對了。

---

## 驗收

「修完之後掃描乾淨」單獨看沒有意義,可能是修正有效,也可能是這一輪剛好沒走到那條路徑。
要的是**同一組條件、同一份操作腳本**下的前後對照:

| 版本 | 同一輪掃描的結果 |
|---|---|
| 修正前 | 1 顆 `heap-buffer-overflow` @ `stretch200To240Nearest ← internUpdateScreen` |
| 修正後 | 0 |

而且不能只驗「沒有崩潰」。§3.4 改的是顯示邏輯(比例校正的判斷條件),
把越界那行刪掉當然不會再越界,但畫面也沒了 —— 所以那次除了 ASan 歸零,
還要確認 aspect 模式下 640×480 的畫面比例是對的、ScummVM 自己開 GUI 時行為沒變。
凡是動到繪圖路徑的修正,驗收都要同時包含「ASan 乾淨」與「畫面正確」兩項。

判斷一顆越界該歸誰,也是靠對照實驗而不是「函式寫在誰的檔案裡」。
最乾淨的對照是同一個 binary 只切換一個開關 —— 這個專案是把譯表移走讓疊層不啟用,
比拿兩個不同的 build 比可靠得多。

---

## 常見誤判

- **把「ASan 乾淨」當成「程式正確」。** 它只涵蓋記憶體安全,而且對同一塊配置內部的越界無感。
- **就地編。** 混到未插樁的 `.o` / `.a`,掃描結果是假的乾淨,而且沒有任何提示。
- **一輪跑到底。** 第一顆錯會中止 process,把後面所有的遮住。
- **沒確認情境生效。** 倍率或後端參數沒吃到,結果照樣印「乾淨」。
- **忘了關 LeakSanitizer。** 滿版的洩漏報告會把真正的越界蓋掉。
- **只驗不崩潰。** 改顯示邏輯時要一併看畫面。
- **拿無頭環境的結果推論 HiDPI 沒問題。** Xvfb 沒有 HiDPI,overlay 恆為 640×400、映射是恆等的,
  Retina 那一類的越界在預設條件下永遠重現不出來,必須用 `--scale-factor` 主動撐大。

---

## 什麼時候該換工具

| 症狀 | 工具 |
|---|---|
| 越界、use-after-free、double-free | ASan |
| 未初始化的值被使用 | MSan(要整條依賴鏈都插樁) |
| 多執行緒資料競爭 | TSan(不能與 ASan 同時開) |
| 整數溢位、對齊錯誤、null deref 等未定義行為 | UBSan(可與 ASan 同時開) |
| 不能重編、只有 binary | Valgrind memcheck(慢 10–50 倍,不必重編) |
| 邏輯錯、狀態機錯、腳本資料的漏洞 | 都不是。要插樁印狀態或反組譯 |

---

## 相關

- [`AGOS_PITFALLS.md`](AGOS_PITFALLS.md) §3.2–3.8 —— 這裡引用的那幾顆越界的完整根因與修法。
- [AddressSanitizer 演算法與 redzone / shadow memory 設計](https://github.com/google/sanitizers/wiki/AddressSanitizer)
- [ASAN_OPTIONS 旗標清單](https://github.com/google/sanitizers/wiki/SanitizerCommonFlags)
