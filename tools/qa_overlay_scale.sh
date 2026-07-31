#!/usr/bin/env bash
# ============================================================================
# QA loop: overlay 疊層在各種 scale factor / 視窗尺寸下的座標正確性
#
# 背景(玩家 issue1): macOS retina 高 DPI 下 ScummVM overlay 回報的是「物理像素」
# (例 1280x800), 但 chtOverlayCompose 的中文座標全寫死「overlay = 遊戲座標 x2」
# (即固定 640x400) → 中文擠到左上 1/4; 且升採取樣用整數倍 sx=ow/gw, 非整數倍時
# 讀出遊戲 surface 列邊界 → 畫面右緣出現重複面板。
#
# headless(Xvfb)沒有 retina, 但 --scale-factor / 視窗尺寸同樣讓 overlay != 640x400,
# 是等價的代理條件(不是真 retina, 報告時要照實說)。
#
# 用法:
#   scripts/qa_overlay_scale.sh <tag> <scale> <W> <H> [gfx-mode]
#   例: scripts/qa_overlay_scale.sh x2 2 640 400
#       scripts/qa_overlay_scale.sh x4 4 1280 800
#       scripts/qa_overlay_scale.sh ogl 3 1100 700 opengl
#   環境變數 QA_ASPECT=1 → 開 aspect ratio correction(640x400 → 640x480,
#   垂直非整數倍, ScummVM 對 DOS 遊戲預設開啟)
#
# 產出: screenshots/qa_<tag>.png (原始截圖) + screenshots/qa_<tag>.log
# ============================================================================
set -u
cd "$(dirname "$0")/.." || exit 1
ROOT="$PWD"

TAG="${1:?tag}"; SCALE="${2:?scale}"; W="${3:?width}"; H="${4:?height}"; GFX="${5:-surfacesdl}"
ASPECT_FLAG="--no-aspect-ratio"
[ "${QA_ASPECT:-0}" = "1" ] && ASPECT_FLAG="--aspect-ratio"
DISP=":9${SCALE}"
BIN="/work/build/scummvm-src/scummvm"

mkdir -p screenshots

docker run --rm -v "$ROOT:/work" -w /work/run_game agos-build bash -c "
export SDL_AUDIODRIVER=dummy XDG_RUNTIME_DIR=/tmp/x
mkdir -p /tmp/x
# Xvfb 螢幕要比遊戲視窗大: 視窗被放在 +10+15, 螢幕剛好等於視窗尺寸時右下會被裁掉
# (實測截出 630x385 而非 640x400), 各倍率裁掉的比例不同 → 比對時變成假的佈局差異。
Xvfb $DISP -screen 0 \$(( $W + 60 ))x\$(( $H + 60 ))x16 &>/dev/null &
sleep 2
export DISPLAY=$DISP
timeout 32 $BIN -p /work/run_game --auto-detect $ASPECT_FLAG \
    --gfx-mode=$GFX --scale-factor=$SCALE -e null -d1 \
    >/work/screenshots/qa_${TAG}.log 2>&1 &
sleep 13
xdotool mousemove \$(( $W / 2 )) \$(( $H / 2 )) click 1
sleep 7
# 截「視窗本身」而非整個 root screen: Xvfb 下 ScummVM 視窗位在 +10+15(非 0,0),
# 截 root 會讓各倍率的畫面內容帶著不同的相對位移, 縮回 640x400 比對時變成假的「佈局偏移」。
WID=\$(xdotool search --name 'Elvira' 2>/dev/null | tail -1)
if [ -n \"\$WID\" ]; then import -window \$WID /work/screenshots/qa_${TAG}.png
else import -window root /work/screenshots/qa_${TAG}.png; fi
pkill scummvm
sleep 1
chown 1000:1000 /work/screenshots/qa_${TAG}.png /work/screenshots/qa_${TAG}.log
" >/dev/null 2>&1

[ -f "screenshots/qa_${TAG}.png" ] || { echo "FAIL($TAG): 沒有產出截圖"; exit 1; }

# ScummVM 偶爾在 GUI 階段(引擎啟動前)噴 SDL_BlitSurface failed 然後停在錯誤對話框,
# 截出來是全黑 → 這是環境競態不是程式問題(同一組參數重跑就正常)。偵測到就自動重試一次,
# 否則會誤報成佈局 FAIL。
if grep -q "SDL_BlitSurface failed" "screenshots/qa_${TAG}.log" 2>/dev/null; then
	echo "  (SDL 啟動競態, 重試一次)"
	exec "$0" "$TAG" "$SCALE" "$W" "$H" "$GFX"
fi
echo "OK: screenshots/qa_${TAG}.png ($(du -h "screenshots/qa_${TAG}.png" | cut -f1))"
grep -E "^CHTOVL" "screenshots/qa_${TAG}.log" | head -3
