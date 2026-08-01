# AGOS 引擎中文化:踩過的坑

這份記錄《古堡禁地》(Elvira 1) 繁中化過程中實際踩到的坑,以及每一條的根因與正解。
AGOS 是 ScummVM 底下 Horror Soft／Adventure Soft 系列的引擎(Elvira 1/2、Waxworks、
Simon 1/2、Feeble Files),做這幾款的中文化都會遇到同一批問題。

每條的格式都是:**症狀 → 根因 → 正解 → 怎麼驗**。沒有驗證方法的條目不寫進來。

---

## 0. 最根本的一條:AGOS 沒有 CJK 路徑

SCUMM 系遊戲丟一個字型檔進去就能中文化,因為引擎內建 CJK 渲染、偵測到字型檔就切換。
**AGOS 完全沒有這套**:

1. 文字渲染是固定的英文小點陣(`charset.cpp windowPutChar`),不認雙位元組,
   也沒有「放字型檔就切中文」的分支。
2. 硬編碼 UI(動詞列、存讀檔訊息)寫死在 `switch (_language)` 裡,沒有 ZH 分支就落回英文,
   查字串表攔不到。
3. 文字緩衝區按英文小字算大小,全形字會溢位。
4. 320×200 的畫布塞不下 CJK —— 縮到 8px 高就是一團糊。

**所以 AGOS 中文化一定要改引擎原始碼**,沒有零 patch 的路。
公開發布仍可維持 patch-only(推 `.patch` + 字型 + 譯文,玩家跑 patched ScummVM)。

---

## 1. 文字從哪來、怎麼換

| 類別 | 來源 | 能不能查表換 |
|---|---|---|
| 物品名／房間名／短語 | `GAMEPC` 內建字串表(`stringId < 0x8000`) | ✅ |
| 對白／敘述 | `TEXTxx` 分頁(`stringId >= 0x8000`) | ✅ |
| 動詞列、存讀檔訊息 | 硬編碼在原始碼,或**烘進 VGA 美術** | ❌ 見下 |
| 片頭 logo／面板底圖上的字 | VGA 預繪點陣圖 | ❌ 改字串沒用 |

**注入點只有一個**:`string.cpp getStringPtrByID(stringId)`。前兩類全走這裡,
命中譯表就回 Big5。這也是驗收的錨點 —— 在出口 log「請求了但譯表沒有」的 id,
驗收時該歸零。

### [坑] 動詞面板可能根本不是字串

《古堡禁地》的右側動詞列(OPEN/CLOSE/EXAMINE…)是**烘進 VGA 的美術字**,
不在字串表、不經 `windowPutChar`,改譯表完全沒反應。

判斷方法:在 `windowDrawChar` 加計數 log,進遊戲看那些動詞有沒有被畫過。
0 次就是美術字,只能疊層覆蓋。

> **注意各作不同**:Waxworks 的動詞條也是烘進 VGA(zone1 sprite 106–113),
> 但 Simon 系列是 12 格面板覆蓋層。**每款 subengine 都要先反組譯確認**,別照抄。

### [坑] 文件會說謊,以程式碼為準

專案早期的 RE 筆記寫「Elvira 1 的 verb 來自 MENU 資料檔(`_menuBase`),資料驅動」。
**這對 floppy DOS 版不成立**:`loadMenuFile` 只在 `getFileName(GAME_MENUFILE) != nullptr`
時才被呼叫,而這版遊戲檔根本沒有 MENU 檔,`_menuBase` 是 null。
照那份筆記走會白花很多時間。

---

## 2. 疊層(overlay)—— 坑最集中的地方

### 2.1 為什麼要疊層

原生 320×200 下,動詞列的欄寬只有 ~40px、行距 8.5px。中文塞進去必糊。
拉高畫布是正解,但引擎給 PC-98 版準備的 640×400 dual-layer 在 DOS 版強套會崩潰(見 §3.1)。

最後採用的是**用 ScummVM 自己的 overlay 層當 hi-res compositor**:每幀把穩定的
320×200 遊戲畫面升採進 overlay,在上面畫中文。遊戲的渲染路徑完全不碰。

### 2.2 [坑★] 別假設 overlay 是固定尺寸

這是最貴的一顆,玩家在 macOS 上回報「中文全擠在左上角一小塊、右側面板露出英文、
畫面右緣多一條重複的面板」,而 Linux/Windows 都正常。

**根因**:疊層座標全部寫死「overlay = 遊戲座標 × 2」(= 恆為 640×400)。
這個假設在 Retina 上不成立 —— 高 DPI 下 `getOverlayWidth/Height()` 回報的是**物理像素**。
玩家的實測值:

```
Setting 2788 x 1768 -> 1115 x 707 -- 2.5
```

overlay 是 2788×1768,座標卻按 640×400 畫,中文自然縮在左上四分之一。

**正解**:所有座標常數維持不動,但改變它們的解釋 —— 一律視為「基準空間 640×400」,
繪製時經映射函式換算到實際 overlay 尺寸:

```cpp
static const int kChtBaseW = 640, kChtBaseH = 400;
int chtRX(int bx) const { return bx * _chtOvlW / kChtBaseW; }
int chtRY(int by) const { return by * _chtOvlH / kChtBaseH; }
```

**關鍵是用「區間映射」而不是「乘倍率」**:一個基準像素對應 `RX(x) … RX(x+1)` 這整段區間。
非整數倍(Retina 的任意物理尺寸、aspect 校正的 640×480)才不會留縫或重疊。
字模也用同一套映射展開,所以高 DPI 下中文的視覺大小維持不變,不會縮成一小塊。

overlay 剛好是 640×400 時映射是恆等的,一般螢幕行為完全不變。

### 2.3 [坑★] 升採取樣別用整數倍,會越界

同一顆 bug 的另一個症狀(畫面右緣重複的面板)來自升採迴圈:

```cpp
int sx = ow / gw;                      // 2788 / 320 = 8,真值 8.7
d[ox] = palEnc[srow[ox / sx]];         // ox 最大 2787 → 索引 348 > 319
```

整數除法無條件捨去,`ox / sx` 走到後段就超過遊戲畫面寬度,讀進**下一列**的像素
(畫面看起來像重複),再往後就直接讀出 surface 尾端 → SIGSEGV。

**正解**:比例映射,並 clamp。

```cpp
int sy = oy * gh / oh;  if (sy >= gh) sy = gh - 1;
d[ox] = palEnc[srow[ox * gw / ow]];
```

### 2.4 [坑] overlay 尺寸會變,而且 overlay 會被關掉

兩件相關但不同的事,都會咬人:

1. **尺寸變了要重配 buffer**。Retina、切換 scale factor、視窗 resize 都會改變 overlay 尺寸。
   舊寫法只在 `!_chtOvlBuf` 時配置一次,尺寸變了之後仍以舊的 stride 寫入 → 踩記憶體。

   ```cpp
   if (!_chtOvlBuf || ow != _chtOvlW || oh != _chtOvlH || bpp != _chtOvlBpp) {
       free(...); malloc(...);   // 重配並更新記錄的尺寸
   }
   ```

2. **overlay 可能被後端關掉**。`showOverlay()` 只在進遊戲時呼叫一次是不夠的 ——
   繪圖後端在視窗變動、切全螢幕時會重建圖形狀態並關閉 overlay,
   一旦關掉中文就永久消失,要重開遊戲才回來。每幀確認:

   ```cpp
   if (!_chtOverlayOn || !_system->isOverlayVisible()) {
       _system->showOverlay(false);
       _chtOverlayOn = true;
   }
   ```

> **注意 bpp 不是固定的**:SurfaceSDL 後端的 overlay 實測是 2 bytes/px,
> OpenGL 後端是 4。程式碼要同時支援,別寫死。

### 2.5 [坑] 疊層像素不會自動清

疊層是持久的,畫上去就一直在。一次性的疊字(例如片頭標題)畫完會殘留到後續畫面。
每幀重繪的東西(面板、地圖)會自然覆蓋,但**關閉時仍要主動清乾淨**。
一次性疊字必須配一次性清除(用旗標記住已清)。

### 2.6 [坑] 看得到的字 ≠ 點得到的框

點擊判定框(hitarea)是遊戲腳本定義的固定矩形,跟疊層無關。
中文畫在哪裡不影響「點了會發生什麼」—— 決定權在那個看不見的框。
字與框錯開就會「看得到、點不到」或「點到隔壁」。

**凡是可點的中文,一律以判定框中心為錨點直接畫**,不要走一般文字排版路徑
(對白用的壓縮格排版與判定框格線不同,綁判定框的選單走它必然錯位)。

判定框真值從 `boxController` dump 出來,別目測。

---

## 3. 崩潰與記憶體

### 3.1 [坑] 別在 DOS 版強套 PC-98 的 dual-layer

引擎為 Elvira 1 的 **PC-98 版**準備了 `_backBuf`(320×200)+ `_scaleBuf`(640×400)
的雙層畫布。在 DOS 版強制開啟會 heap 損壞崩潰,而且是**佈局相依的 heisenbug**:

AGOS 本身就有 pre-existing 的繪圖越界(vanilla 撞到的是無害記憶體,所以沒人發現),
hi-res 多配的大 buffer 改變了 heap 佈局,越界就撞上關鍵資料。
gdb / ASan / valgrind 一插樁就消失(改了時序與佈局)。

**別在這條路上耗**。改用 ScummVM overlay 層(§2.1),完全不碰遊戲的渲染 buffer。

### 3.2 [坑★] 越界讀不會立刻炸 —— 所以無頭測試測不出來

玩家回報「玩一陣子會當機」,而我們的自動化測試跑同樣條件從來沒事。原因:

那是**越界讀**。每一幀都在讀出界,但只要越界那段記憶體剛好還是已映射的,
程式就繼續跑(只是畫面內容不對);要等到越界正好落在未映射的頁面才 SIGSEGV。
**會不會炸取決於當下的記憶體佈局**,換場景、開選單、配置變動之後就可能踩中。

實測對照:同一顆 bug,在無頭 Linux 上跑 100 輪密集互動**不會崩潰**,
但在玩家的 macOS 上玩一陣子就掛。

**教訓**:「測起來正常」不等於沒有越界。這類問題要用 ASan,不能靠「跑跑看有沒有掛」。

### 3.3 ASan 是這類問題的正解

```bash
CXXFLAGS="-fsanitize=address -fno-omit-frame-pointer -g -O1" \
LDFLAGS="-fsanitize=address" \
  ./configure --disable-all-engines --enable-engine=agos
make -j$(nproc)

ASAN_OPTIONS="detect_leaks=0:halt_on_error=1:print_stacktrace=1" ./scummvm ...
```

不必等踩到未映射頁,只要越界就立刻報,而且直接給堆疊。
本專案用它做的對照(同一組條件、同一套操作):

| 版本 | ASan 結果 |
|---|---|
| 修復前 | `heap-buffer-overflow` @ `chtOverlayCompose ← displayScreen ← timerProc` |
| 修復後 | `chtOverlayCompose` 不再出現 |

而且修復前那份堆疊與玩家 crash log 的堆疊**完全一致**,等於在本機重現了玩家的當機。

### 3.4 [坑★] `showOverlay(false)` 讓 backend 誤判,踩到比例校正的越界

修復後的 ASan 掃描挖到另一顆,在 ScummVM 上游:

```
WRITE of size 1280
  #1 stretch200To240Nearest(...)
  #3 SurfaceSdlGraphicsManager::internUpdateScreen()
```

`stretch200To240` 是 SurfaceSDL 後端做 4:3 比例校正(200 → 240 行)的函式。
程式碼在 ScummVM 上游,中文化的 patch 沒碰這裡 —— 但**不能因此就說「與我們無關」**。

做對照實驗才問得出真相(同一個 binary、同樣開啟 aspect 校正,只差有沒有啟用中文疊層):

| 條件 | ASan |
|---|---|
| 疊層開啟 | 1 顆:`stretch200To240Nearest` 越界 |
| 疊層關閉(把譯表移走即可) | 乾淨 |
| vanilla ScummVM(完全未套 patch) | 乾淨 |

**結論是「上游的程式碼、我們的使用方式觸發的」**:一般遊戲只在叫出 GUI 選單時
短暫顯示 overlay,而中文化是**全程開著 overlay**,才會每幀走進那條校正路徑。

**不要**因為「程式碼不是我寫的」就結案 —— 觸發條件是我們造成的,
使用者遇到時也不會在意那行程式碼掛在誰的名下。往下再挖一層就找得到修法。

#### 根因:一個沒寫下來的隱含假設

`internUpdateScreen()` 的兩處比例校正,條件都是 `!_overlayInGUI`:

```cpp
if (_videoMode.aspectRatioCorrection && !_overlayInGUI)
    dst_y = real2Aspect(dst_y);
```

這等於假設**「overlay 顯示中」就是「ScummVM 自己的 GUI 開著」**。對 ScummVM 本身成立,
因為它只在開選單時顯示 overlay。但 overlay 也可以被引擎用 `showOverlay(false)` 開啟並持續顯示
—— 那個 `false` 的語意是「這不是 GUI 用途」,於是 `_overlayInGUI` 保持 false、
backend 以為沒有 overlay,對已經是 overlay 尺寸(480 列、已含校正)的畫面**再校正一次**:

```
STRETCH: w=640 h=400 ... maxDstY=479   ← 正常:400 拉成 480,剛好填滿
STRETCH: w=640 h=480 ... maxDstY=575   ← 越界:傳進來的高度已經是校正後的值
```

緩衝區只有 480 列(640 × 480 × 2 = 614400 bytes),寫到第 575 列就出界。

#### 修法

兩處判斷改用 `_overlayVisible`:

```cpp
if (_videoMode.aspectRatioCorrection && !_overlayVisible)
```

ScummVM 自己開 GUI 時兩個旗標同時為 true,兩條件等價,**對原本行為零影響**;
只有「overlay 可見但非 GUI」才有差別,而那正是出問題的情況。
修正後同條件 ASan 從 1 顆歸零,並確認 aspect 模式(640×480)畫面比例正常 ——
這條改的是顯示邏輯,不能只驗「沒有崩潰」。

> 教訓:**用別人的 API 時要留意它有沒有沒寫下來的隱含假設**。`showOverlay(false)`
> 從簽名看只是「開 overlay、不是 GUI」,但 backend 內部把 `_overlayInGUI` 當成
> 「overlay 開了沒」在用。這種假設通常要等到越界之後回頭看才會浮現 ——
> 所以 ASan 的價值不只是抓 bug,是把「隱含假設被違反」變成看得見的訊號。

> 方法論:判斷一顆越界屬於誰,靠的不是「函式在誰的檔案裡」,而是**對照實驗**。
> 最乾淨的對照是同一個 binary 只切換一個開關(這裡是把譯表移走讓疊層不啟用),
> 而不是拿兩個不同的 build 比。

---

### 3.5 [坑★] 同一個誤判的第二處:游標殘影

修好 3.4 之後,同一個假設在 SurfaceSDL 的**游標**路徑上又咬了一次 —— 症狀完全不同:
滑鼠每移動一次就在原地留下一個游標,滿畫面都是箭頭。

`undrawMouse()` 登記「要重畫的區域」時,把座標空間旗標傳成 `_overlayInGUI`:

```cpp
addDirtyRect(_mouseLastRect.x, ..., _overlayInGUI);   // 最後一個參數 = realCoordinates
```

但同一份 dirty rect 清單,在 `internUpdateScreen()` 是**照 `_overlayVisible` 決定來源**的:

```cpp
if (!_overlayVisible) { origSurf = _screen;        width = screenWidth;  scale1 = scaleFactor; }
else                  { origSurf = _overlayscreen; width = overlayWidth; scale1 = 1; }
```

兩邊用不同的旗標判斷同一件事。以 `showOverlay(false)` 開啟疊層時,
`_activeArea` 留在遊戲空間,游標矩形算出來是遊戲座標(如 20,20,16,16),
卻被丟進以疊層座標消化的清單 —— 舊游標所在的區域永遠不會被重畫,殘影就留下來了。

修法是在「疊層可見但非 GUI」時,用**與 `drawMouse()` 相同的換算**先轉到疊層座標
(先 `real2Aspect` 做 200→240 的列映射,再乘 `scaleFactor`),再以 `realCoordinates = true` 登記。

驗證用對照組最快:把譯表移走讓疊層不啟用,同樣移動滑鼠 —— 原版只有一個游標、位置正確,
疊層開啟才有殘影,就確定是自己造成的,不必猜。

> 這兩顆(3.4、3.5)是同一個根:**`_overlayInGUI` 在上游程式碼裡被當成「overlay 開了沒」在用**。
> 找到第一顆之後,值得把整份後端 `grep -n _overlayInGUI` 掃一遍逐處判斷 ——
> 同源缺陷通常不只一處,而它們的表徵可以差很遠(一個是崩潰,一個是畫面殘影)。

### 3.6 [坑★] 同一個誤判的第三處:OpenGL 後端游標整個不見

**狀態:已修復。** 這是玩家最早回報的症狀之一(macOS 預設走 OpenGL,所以會直接撞到)。

症狀:OpenGL 後端 + 中文疊層 → 中文顯示正常,但整個視窗看不到游標。
同一份執行檔把譯表移走(疊層不啟用)游標就正常,所以是疊層與 OpenGL 的互動。

已經確認的事實(每一條都是實測,不是推論):

| 檢查 | 結果 |
|---|---|
| `renderCursor()` 有沒有被呼叫 | 有,每幀都呼叫 |
| 傳進去的座標／尺寸 | 正常(視窗座標、45×54,會跟著滑鼠更新) |
| 繪製順序 | 先疊層後游標(在 `updateScreen()` 裡印序號確認) |
| OpenGL 錯誤 | 無(`OPENGL_DEBUG` 預設就是開的,log 乾淨) |
| 把「畫疊層貼圖」那一行拿掉 | **游標立刻出現** |
| 只保留該步的 `enableBlend`、不畫貼圖 | 游標正常 → 元兇是 `drawTexture` 本身,不是 blend 設定 |

上面那張表看起來像鬼故事:繪製函式有被呼叫、狀態一模一樣、卻沒有輸出。
**問題出在「有被呼叫」這件事本身被我讀錯了。**

破口是換掉量測方式:不再二分,改成**每一幀都印出這幀到底有沒有畫游標**。結果是 185 幀
**全部** `cur=0`,而 `_cursorVisible` 是 1。也就是說,到第四步時 `drawCursor` 早就被關掉了 ——
游標是在**第二步**畫的:

```cpp
if (_libretroPipeline) {
    // If we are in game, draw the cursor through scaler
    // This has the disadvantage of having overlay (subtitles) drawn above it
    // but the cursor will look nicer
    if (!_overlayInGUI && drawCursor) { renderCursor(); drawCursor = false; }
}
```

那句註解**自己就寫明了**:走這條路的游標會被疊層蓋住。上游能接受,是因為它假設
「非 GUI 的疊層」只是字幕那種局部的東西;而 `showOverlay(false)` 開起來鋪滿整個畫面的疊層
會把游標蓋得一乾二淨。`_libretroPipeline` 在 2.9.1 是預設就會建立的縮放路徑,不需要載入任何
shader preset(實測 `libretro=1`)。

修法與前兩處一致:條件改成 `!_overlayVisible`,疊層可見時就留到第四步(疊層之後)再畫。
代價是這種情況下游標不經 scaler、少一點修飾,換到「游標一定看得見」—— 這個取捨很好選。

驗證:OpenGL 模式下游標正常顯示,滑鼠移到兩個位置的 A/B 截圖差異 582 像素(修正前是 0);
SurfaceSDL 迴歸乾淨(單一游標、無殘影)。

> 三個方法論教訓:
> 1. **A/B 差異比對要挑對背景**。用「移動滑鼠到兩個位置各截一張、比對差異」判斷游標有沒有畫出來很好用,
>    但把兩個位置都選在黑色文字框上,再加上「關掉 blend」的變因,黑游標疊黑底就測不出差異 —— 訊號會自相矛盾。
> 2. **探針的取樣範圍會騙人**。`if (n < 40)` 只印前 40 幀,全是早期畫面,一度讓我誤判「游標位置卡住」。
>    而 `SEQ` 探針用兩個獨立計數器,唯一真正有用的訊息其實是「疊層畫的次數比游標多」——
>    那才是後來破案的線索,當時卻被我當成雜訊。
> 3. **訊號開始互相矛盾時,要換的是量測方式,不是切更多刀。** 停手之後改成「每幀印出有沒有畫游標」,
>    一次就中。二分法問的是「哪一行有關」,而真正該問的是「這一幀到底發生了什麼」。


### 3.7 [坑★] 遊戲腳本沒有 default 分支 → 圖號 0 → 上游直接 `error()` 中止

玩家回報:往前走撞到欄杆或牆壁時遊戲整個中止,訊息是

```
ERROR: loadVGAVideoFile: Can't load 002.VGA!
```

**先確認不是自己造成的**:同一個玩家在 SurfaceSDL 與 OpenGL 兩條完全不同的顯示路徑下都遇到;
中文化的 patch 全文 grep 過,沒有碰任何 zone 載入的程式碼(唯一寫腳本變數的地方是 F7 無敵的
`_variableArray[5]`,而玩家的 log 沒有 `CHT: godmode` 訊息,代表他沒按過)。版本也一致
(`Floppy/DOS/English`)。

#### 根因

`002.VGA` 是 **zone 0**。`setImage()` 用 `vgaSpriteId / 100` 算 zone,所以**圖號小於 100
就會落到 zone 0**,而 Elvira 1 的 DOS floppy 版沒有 zone 0 的檔(只有 01–03、06–09、17–74)。

往下追要靠反組譯。VGA 腳本(`dumpAllVgaScriptFiles()`)裡沒有小於 100 的圖號;
真正的來源在 GAMEPC 子程式 —— 有幾處 `PICTURE` 的參數是**變數**而不是常數:

```
PICTURE [221] 4      ; 子程式 50
PICTURE [222] 4      ; 子程式 53
PICTURE [223] 4      ; 子程式 48/51/55
```

而這三個變數只在 `SUB_74` 被指派,那是一段條件 dispatch:

```
CHILD_FR2_IS SUBJECT_ITEM <物件A> ->  SET 221 300   SET 222 301   SET 223 302 …
CHILD_FR2_IS SUBJECT_ITEM <物件B> ->  SET 221 5000  SET 222 5001  SET 223 5002 …
…共 8 組…
```

**八個條件都不符合時沒有 default 分支** —— 221/222/223 保持原值,若從未被設定過就是 0。
接著 `PICTURE [221]` 把 0 送進 `setImage`,zone 算成 0,上游 `loadVGAVideoFile` 找不到檔案就
`error()` 中止整個遊戲。對玩家而言等於當機加進度全失。

> 反組譯的注意事項:`dumpAllSubroutines()` **只會 dump 當下載入在記憶體裡的子程式**。
> Elvira 1 的腳本分散在 11 個 `TABLES*` 分頁,要先跑一輪 `loadTablesIntoMem(id)` 把全部載進來
> 才看得到完整的圖(第一次只 dump 到約 13 萬行,補上載入迴圈後是 17 萬行,
> `SET 221` 那 8 組就是補上之後才出現的)。

#### 修法

這是遊戲資料的邏輯漏洞,不是我們能改的;能改的是**不要讓它殺掉遊戲**。
在 `setImage()` 與 `animate()` 進主迴圈前先試載一次,真的沒有就印警告並跳過這張圖:

```cpp
if (_vgaBufferPointers[zoneNum].vgaFile1 == nullptr) {
    loadZone(zoneNum, false);
    if (_vgaBufferPointers[zoneNum].vgaFile1 == nullptr) {
        warning("%s: zone %d 載不到(sprite id %d), 跳過此圖", __FUNCTION__, zoneNum, vgaSpriteId);
        return;
    }
}
```

**[HARD] 不能只是把 `loadZone` 改成非致命。** 那兩個函式的主迴圈長這樣:

```cpp
for (;;) {
    vpe = &_vgaBufferPointers[zoneNum];
    if (vpe->vgaFile1 != nullptr) break;
    loadZone(zoneNum);
}
```

載入失敗時 `vgaFile1` 永遠是 null,迴圈**永遠跳不出來** —— 把致命錯誤換成當場凍結,更糟。
所以一定要在進迴圈前擋。

驗證:強制走一次失敗路徑(`setImage(99)` → zone 0),修正後印警告並繼續跑滿測試時間;
正常遊玩 80 次移動防護觸發 0 次(完全休眠),畫面與對白正常。

> 順帶查證過:ScummVM 上游到 2026.3.0 為止(v2.9.1 之後三個大版本、58 個 AGOS commit)
> 都沒有處理這個情況,AGOS 的維護集中在 Atari ST / Amiga / Acorn 的音樂與顯示。
> 換言之升級 ScummVM 版本救不了這顆,得自己擋。


### 3.8 [坑★] zone 上界:圖號是 16-bit,zone 陣列只有 450

`setImage()` 與 `animate()` 都用 `vgaSpriteId / 100` 算 zone,而圖號來自腳本、型別是
16-bit。最大值 65535 除以 100 是 **655**,但 `_vgaBufferPointers` 只有 **450** 個項目:

```cpp
VgaPointersEntry _vgaBufferPointers[450];   // agos.h
```

上游的主迴圈是**先取元素、才進 `loadZone()` 的 `CHECK_BOUNDS`**:

```cpp
for (;;) {
    vpe = &_vgaBufferPointers[zoneNum];   // ← 越界讀發生在這裡
    if (vpe->vgaFile1 != nullptr) break;
    loadZone(zoneNum);                    // ← 斷言在這之後才執行
}
```

所以斷言擋不住那次讀取。

**這顆的危險之處在於它不會當場炸。** 每個 entry 是 6 個指標、48 bytes,450 個共 21600 bytes;
索引 650 的位移是 31200,越過陣列尾端 9600 bytes —— 但那個位置**仍然落在 `AGOSEngine` 物件內部**,
讀到的是其他成員變數。於是拿到一個看起來合法的指標,程式繼續跑,然後在**完全無關的地方**崩潰。
這正是玩家回報「玩一玩就 crash」那種找不到規律的症狀。

> **ASan 抓不到這一顆。** redzone 只存在於配置的邊界上,而這是同一塊配置**內部**的越界
> —— 物件成員陣列越界到別的成員。五輪 ASan 掃描全部乾淨,這顆是讀程式碼時才發現的。
> 這也是「ASan 乾淨不等於程式正確」最具體的一個例子。

#### 修法

在碰陣列**之前**先擋上界,`setImage()` 與 `animate()` 各一份:

```cpp
if (zoneNum >= ARRAYSIZE(_vgaBufferPointers)) {
    warning("%s: zone %d 超出範圍(sprite id %d), 跳過此圖", __FUNCTION__, zoneNum, vgaSpriteId);
    return;
}
```

**[HARD] 上界要用陣列大小,不要用 `_numZone`。** Elvira 1 的 `_numZone` 是 74,而遊戲檔裡
**確實有 `741.vga` / `742.vga`,也就是 zone 74**;照慣例寫 `zoneNum >= _numZone` 會把合法的
zone 74 擋掉。看起來更嚴謹的檢查反而誤擋,這種地方寧可保守。

#### 為什麼不是「把陣列開大」

三個理由,由淺入深:

檔名對不上。檔名格式是 `"%.2d%d.VGA"`,zone 650 組出來是 `6502.VGA`,不是遊戲的命名規則
(實際只有 `011.vga`…`742.vga`)。索引就算合法,載入照樣失敗,還是得走「跳過」那條路
—— 加大陣列只是讓錯誤晚一步發生。

它把「狀態已經壞了」永久靜音。zone 650 出現代表某個腳本變數是垃圾值,那是症狀不是容量不足。
陣列開大之後畫面照樣缺圖、狀態照樣是錯的,但再也沒有訊號告訴你出事了。

`450` 有它的理由 —— 那是 Feeble Files 的 `_numZone`。動它等於改 `AGOSEngine` 的物件佈局,
影響所有 subengine,patch 侵入性與跨版本重對的成本都變大。

記憶體成本反而不是考量:450 → 656 只多約 10 KB。這不是「省記憶體 vs 防崩潰」的取捨,
而是**用容量去容納不合法的值,方向本身就錯了**。

#### 驗證

強制打三種壞圖號,確認都不中止:

| 輸入 | 結果 |
|---|---|
| `setImage(99)` → zone 0(不存在的 zone) | 印警告後跳過 |
| `setImage(65000)` → zone 650(超出陣列) | 印警告後跳過,沒有越界讀 |
| `animate(4, 650, 65000, …)` | 印警告後跳過 |

修正後四輪 ASan 掃描(x3、x4、OpenGL、比例校正)全部乾淨,正常遊玩 130 次操作防護觸發 0 次。


---

## 4. 字型

- **編碼用 Big5**。AGOS 走原始碼 patch,`getStringPtrByID` 直接回 Big5、
  `windowPutChar` 自己處理雙位元組,不受 SCUMM 那套 ASCII 限制。
- **[坑] 字模高度要比行距小**。面板列距 16px 時,字模烘成 16×16 就是零間隙,
  上下列會黏在一起;要 16×**15**。用 TTF 烘替代字型時記得指定高度,別只給正方形尺寸。
- **[坑] 一份字型走不了天下**。偏細的字在深色面板上對比不足,加粗後好讀;
  但同一份加粗字放進密集長文,筆劃多的字(爵/籠/罩/鑰)會黏成一塊。
  **面板用加粗、對白用細版**,分兩份。
- **判斷字型好壞不必進遊戲**:寫個小腳本把點陣字型直接渲染成排版圖比對,
  比 headless 截圖快得多也穩得多。
- **[坑★] 字型載入一定要驗 header**。DCJK 這類自訂點陣格式的資料量是
  `numGlyphs × bytesPerRow × height` 算出來的,而 glyph 取用時是拿 `numGlyphs` 驗界。
  如果檔案損毀、被截斷、或玩家放錯檔,這個乘積可能溢位或算出比實際小的值 →
  配置的緩衝區小於索引上限,**驗界形同虛設**,之後每畫一個字都在越界讀。
  這種崩潰完全看記憶體佈局的運氣,極難追。

  載入時至少要擋四件事,任一不成立就當載入失敗(讓引擎落回英文,好過讀壞記憶體):

  ```c
  if (w <= 0 || w > 64 || h <= 0 || h > 64 || bpr != (w + 7) / 8) return false;  // header 自洽
  if (n == 0 || n > 65536) return false;                                          // 字數合理
  uint32 per = bpr * h;
  if (per == 0 || n > 0xFFFFFFFFu / per) return false;                            // 乘法溢位
  if ((uint32)(f.size() - 15) < n * per) return false;                            // 檔案裝得下
  ```

  實測:餵一個被截斷成 1KB 的字型檔、和一個 w/h 被改成 200 的字型檔,
  加了檢查之後兩者都只是印 warning 並略過,遊戲照常跑完。

- 字形來源建議用**倚天中文系統的原生點陣字**(1990 年 DOS 中文的原貌),
  TTF 縮到 15–24px 筆劃比例會跑掉。倚天字模有版權,不要隨庫散布 —— 附轉檔工具、
  讓使用者自備即可。

---

## 5. 驗證方法

### [坑] 無頭截圖比對的兩個假錯位

1. **Xvfb 下視窗不在 (0,0)**,實測在 +10+15。截整個螢幕再縮放比對,
   不同倍率的相對位移不同,會得到「哪裡都差一點」的假錯位。
2. **螢幕開得跟視窗一樣大時,視窗右下會被裁掉**(截出 630×385 而不是 640×400)。

正解:Xvfb 螢幕開得比視窗大,並且截**視窗**而不是截螢幕。

> 這兩顆讓 RMSE 卡在 0.22 降不下來。判斷特徵:差異圖上是整片均勻雜訊、
> 而全黑區域反而沒差異 —— 那是取樣相位差,不是佈局錯位。

### [坑] 整張 RMSE 對佈局不敏感

RMSE 容易被畫面內容主導。要驗證「中文有沒有畫在對的位置」,
用**中文區 ROI 的亮像素佔比**更靈敏:錯位時會掉到正常值的三分之一。

### [坑] Retina 錯位在無頭環境永遠重現不出來

Xvfb 沒有 HiDPI,overlay 永遠是 640×400,恆等映射,永遠正確。
要重現得主動把 overlay 撐大:`--scale-factor=4` 會讓 overlay 變成 1280×800,
與 Retina 回報物理像素是同性質條件。

### 驗證訊號不一定要從原本那條路取

對白文字層的驗證卡了很久 —— 試過點檢視、點房間、點物品、開場多時間點取樣,
五種方法都沒能在無頭環境穩定觸發到一段對白。
最後是**錄推廣片時錄到的**(片中 NPC 那段完整對白)。
卡住的時候換個管道,別在同一條路上加特例。

### 其他實用細節

- `debug(0, ...)` 預設看不到,要加 `-d1`。
- headless 一律 `Xvfb :99 -screen 0 640x400x16`(**深度 x16**,x8 會炸 render driver)
  + `SDL_AUDIODRIVER=dummy`。
- 存檔熱鍵是 **Alt+數字**,讀檔才是 Ctrl+數字。搞反會變成把進度洗掉。
- 開場 cutscene 期間存檔被擋(`_mouseHideCount`),要等進到可操作場景。

---

## 6. patch 維護

### [坑★] 重生 patch 會漏掉新增的檔案

中文化新增的檔案(如 `cht_fusion.{h,cpp}`)在 ScummVM 的原始碼樹裡是 **untracked**,
慣用的 `git diff HEAD -- engines/agos/` **收不到它們**。

症狀很陰險:本機打包完全正常(用的是現成的 build 樹,檔案本來就在磁碟上),
只有「從 pristine 原始碼套 patch 再編」的 CI 會爆:

```
fatal error: 'agos/cht_fusion.h' file not found
```

而且 `git apply --check --reverse` **驗不出來** —— 對著已經有那些檔案的工作樹
反向驗證當然會過。反向驗證只證明「patch 描述的改動與現況相符」,不證明 patch 完整。

**正解**:

```bash
git add -N engines/agos/cht_fusion.cpp engines/agos/cht_fusion.h   # intent-to-add
git diff HEAD -- engines/agos/ > patches/agos-cht.patch
grep -c "new file mode" patches/agos-cht.patch                      # 必須等於新檔數

# 別等 CI:自己出一份 pristine 樹實測套用 + 編譯
git archive HEAD | tar -x -C /tmp/pristine
cd /tmp/pristine && git init -q . && git apply --check <patch>
```

---

## 7. 平台與打包

- **[坑] macOS CI 只能用 `macos-14`**;`macos-13`(Intel)runner 退役中,會永遠排隊。
  x86_64 那一弧走 `arch -x86_64`(Rosetta)各編一次再 `lipo -create`,
  單次雙 `-arch` 會讓 configure 的版本偵測失敗。
- **[坑] macOS 別用 brew 的 SDL2**:2026 起那是 sdl2-compat,runtime 會去 dlopen SDL3,
  玩家端出現「Failed loading SDL3」或黑畫面。自己從源碼編 pinned 的真 SDL2。
  防呆:dylib 要 >1MB、`otool -L` 不該看到 SDL3。
- **[坑] ScummVM 的 `configure` 不是 autoconf**,`CXXFLAGS=...` 不能當引數傳,
  要當環境變數前綴。
- **[坑] mingw 交叉編時共用原始碼樹會污染**:Linux build 留下的 ELF `.o`/`.a`
  被 mingw ld 靜默跳過(`nm` 讀 ELF 又看起來正常,像是「明明有定義」)。
  複製一份樹並清掉所有 `.o`/`.a` 再編。
- **[坑] 啟動器不要鎖死畫面倍率**。早期為了迴避疊層座標問題,
  在啟動腳本鎖 `--scale-factor=2`,結果玩家在 ScummVM 設定裡怎麼改都沒用
  (命令列參數優先於設定檔)。而 macOS 的 `.app` 沒有啟動腳本可鎖 ——
  **這正好解釋了為什麼只有 macOS 玩家撞到 Retina 那顆**。
  座標修好之後就該把鎖拿掉。

---

## 8. 一句話總結

AGOS 中文化的難點不在翻譯,在**疊層與座標**。
只要記住兩件事就能避開這份文件裡大半的坑:

1. **不要假設畫面尺寸**。overlay 的尺寸會因為 Retina、縮放、全螢幕、比例校正而改變,
   任何寫死的倍率遲早會咬人。座標寫在基準空間、用區間映射換算。
2. **「測起來正常」不等於正確**。越界讀不會立刻崩潰,無頭環境也重現不出 HiDPI。
   要用 ASan 這種確定性工具,並且主動製造極端條件(高倍率、非整數倍、比例校正)。
