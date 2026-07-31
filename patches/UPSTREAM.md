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

### `stretch200To240Nearest` 越界(未修,有完整分析)

**狀態**:已定位、可重現、**尚未修復**。玩家不受影響(建議啟動器預設關閉比例校正)。

ASan 報告:

```
ERROR: AddressSanitizer: heap-buffer-overflow
WRITE of size 1280
    #0 memcpy
    #1 stretch200To240Nearest(...)            graphics/scaler/aspect.cpp:208
    #2 stretch200To240(...)
    #3 SurfaceSdlGraphicsManager::internUpdateScreen()
0x... is located 736 bytes BEFORE 614400-byte region
allocated by SurfaceSdlGraphicsManager::SDL_SetVideoMode()
```

注意越界方向是 **underflow**(寫在緩衝區之前),不是溢出。
614400 bytes = 640 × 480 × 2,是 SDL 的畫面緩衝區。

**觸發條件**(對照實驗,同一個 binary 只切換一個開關):

| 條件 | 結果 |
|---|---|
| 中文疊層開啟 + aspect ratio correction | 報越界 |
| 中文疊層關閉(移走譯表即可) | 乾淨 |
| vanilla ScummVM(完全未套 patch) | 乾淨 |

**判讀**:程式碼是上游的(這個 repo 沒有碰 `backends/` 或 `graphics/scaler/`),
但觸發條件是中文化造成的 —— 一般遊戲只在叫出 GUI 選單時**短暫**顯示 overlay,
而中文化是**全程開著** overlay,才會每幀走進那條比例校正路徑。

**還沒修的理由**:`internUpdateScreen` 裡有兩處 `stretch200To240` 呼叫,
遊戲畫面那條會帶入非零的 `srcY / origSrcY`(來自 dirty rect 系統),
而 `startSrcPtr = buf + (srcY - origSrcY) * pitch` 在兩者關係不如預期時會指到緩衝區之前。
要正確修必須先弄懂 SurfaceSDL 的 dirty rect 與 aspect 座標系統怎麼配合,
在那之前硬改邊界只會把症狀藏起來。

**重現方法**:

```bash
# 用 ASan 版 binary,開啟比例校正,並讓中文疊層處於啟用狀態
ASAN_OPTIONS="detect_leaks=0:halt_on_error=1:print_stacktrace=1" \
  ./scummvm -p <game> --auto-detect --aspect-ratio --scale-factor=2
```
