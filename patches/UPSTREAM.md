# 上游版本對應

## 基準版本

| 項目 | 值 |
|---|---|
| ScummVM tag | `v2.9.1` |
| 取得方式 | `git clone --depth 1 --branch v2.9.1 https://github.com/scummvm/scummvm.git` |
| 涵蓋的 subengine | AGOS(目前實作對位到 `GType_ELVIRA1`)|

## 套用與驗證

```bash
git clone --depth 1 --branch v2.9.1 https://github.com/scummvm/scummvm.git sv
cd sv && git apply --whitespace=nowarn ../patches/agos-cjk.patch
./configure --disable-all-engines --enable-engine=agos --enable-release
make -j$(nproc)
```

## 換版本時要做的事

1. 取新版原始碼,`git apply --check` 看哪些 hunk 對不上。
2. 重對之後**一定要從乾淨的原始碼樹實測套用 + 完整編譯**,不要只在自己的工作樹驗證 ——
   `git apply --check --reverse` 對著已經改過的工作樹當然會過,那證明不了 patch 完整
   (見 `docs/AGOS_PITFALLS.md` §6)。
3. 重生 patch 前先 `git add -N` 把新增的檔案納入,否則 `git diff` 收不到它們。
4. 跑 `tools/qa_overlay_scale.sh` 的各倍率回歸,以及 `tools/asan_sweep.sh`。

## 已知與上游有關的問題

### `stretch200To240Nearest` 越界(**已修**)

**狀態**:已定位、已修復、ASan 驗證通過。修正包含在 `agos-cjk.patch` 內
(`backends/graphics/surfacesdl/surfacesdl-graphics.cpp`)。

#### 症狀

開啟 aspect ratio correction 並讓 overlay 持續顯示時,ASan 報:

```
ERROR: AddressSanitizer: heap-buffer-overflow
WRITE of size 1280
    #1 stretch200To240Nearest(...)            graphics/scaler/aspect.cpp
    #3 SurfaceSdlGraphicsManager::internUpdateScreen()
```

#### 根因

`internUpdateScreen()` 裡兩處 aspect 校正的條件都是 `!_overlayInGUI`:

```cpp
if (_videoMode.aspectRatioCorrection && !_overlayInGUI)
    dst_y = real2Aspect(dst_y);
...
if (_videoMode.aspectRatioCorrection && orig_dst_y < height && !_overlayInGUI)
    r->h = stretch200To240(...);
```

這裡有一個沒被寫下來的隱含假設:**「overlay 顯示中」等於「ScummVM 自己的 GUI 開著」**。
對 ScummVM 本身成立,因為它只在開選單時顯示 overlay。

但 overlay 也可以被引擎用 `showOverlay(false)` 開啟並**持續顯示** ——
`false` 的語意是「這不是 GUI 用途」,於是 `_overlayInGUI` 保持 false,
backend 就以為沒有 overlay,照常對畫面做 200→240 校正。
而此時 hwScreen 上的內容已經是 overlay 尺寸(480 列,已含校正),再校正一次:

```
real2Aspect(479) = 479 + 480/5 = 575     ← 目標列
緩衝區只有 480 列(640 × 480 × 2 = 614400 bytes)
```

診斷用的實際參數(在 `stretch200To240Nearest` 開頭加 log 印出來的):

```
STRETCH: w=640 h=400 ... maxDstY=479   ← 正常:400 拉成 480,剛好填滿
STRETCH: w=640 h=480 ... maxDstY=575   ← 越界:傳進來的高度已經是校正後的值
```

#### 修法

把那兩處的判斷從 `_overlayInGUI` 換成 `_overlayVisible`(兩者都是
`WindowedGraphicsManager` 的成員):

```cpp
if (_videoMode.aspectRatioCorrection && !_overlayVisible)
```

**對 ScummVM 原本的行為零影響** —— 它自己開 GUI 時 `_overlayInGUI` 與 `_overlayVisible`
同時為 true,兩個條件等價;只有「overlay 可見但非 GUI」這種用法才有差別,
而那正是出問題的情況。

#### 驗證

| 條件 | ASan |
|---|---|
| 修正前(疊層開啟 + aspect 校正) | 1 顆越界 |
| **修正後(同條件)** | **0** |
| 疊層關閉 / vanilla ScummVM | 0(本來就不會走到) |

另外確認 aspect 模式(640×480)下畫面顯示正常、比例正確 —— 這條改的是顯示邏輯,
不能只驗「沒有崩潰」。

**重現方法**(給想自己確認的人):

```bash
ASAN_OPTIONS="detect_leaks=0:halt_on_error=1:print_stacktrace=1" \
  ./scummvm -p <game> --auto-detect --aspect-ratio --scale-factor=2
# 需要引擎端有「持續顯示 overlay」的行為(本 patch 的中文疊層即是)
```
