#!/usr/bin/env bash
# AGOS 疊層韌性: ASan 全流程掃描。
# 刻意製造極端條件, 因為越界讀在一般條件下不會炸(見 docs/AGOS_PITFALLS.md §3.2):
#   - 各種倍率, 含非整數倍映射(x3 = 1.5x、opengl 視窗 = 任意比)
#   - OpenGL 後端 overlay 是 4 bytes/px(SurfaceSDL 是 2), 兩條分支都要走到
#   - 密集互動: 地圖開關、無敵、模態選單、存讀檔、場景切換
# ASan 沒開 recover, 一個 process 只報第一顆 → 每個情境獨立跑一輪。
set -u
BIN=/home/anr2/.claude/jobs/b9c2d587/tmp/newasan2
PROJ=/home/anr2/scummvm/elvira_cht/workplace
TAG="$1"; DISP="$2"; shift 2

docker run --rm -v "$PROJ:/work" -v "$BIN:/bin_asan" -w /work/run_game agos-build bash -c '
export SDL_AUDIODRIVER=dummy XDG_RUNTIME_DIR=/tmp/x; mkdir -p /tmp/x
export ASAN_OPTIONS="detect_leaks=0:halt_on_error=1:print_stacktrace=1"
Xvfb :'"$DISP"' -screen 0 1600x1100x16 &>/dev/null & sleep 2
export DISPLAY=:'"$DISP"'
timeout 130 /bin_asan/scummvm -p /work/run_game --auto-detect '"$*"' \
    -e null > /work/screenshots/sweep_'"$TAG"'.log 2>&1 &
SV=$!
sleep 16
# 進遊戲
xdotool mousemove 400 300 click 1 2>/dev/null; sleep 4
for i in $(seq 1 45); do
  kill -0 $SV 2>/dev/null || break
  # 面板各處 + 遊戲區(場景切換)
  xdotool mousemove $((60 + RANDOM % 900)) $((60 + RANDOM % 500)) click 1 2>/dev/null
  case $((i % 9)) in
    0) xdotool key Tab ;;            # 地圖開
    1) xdotool key Tab ;;            # 地圖關
    3) xdotool key F7 ;;             # 無敵切換
    5) xdotool key alt+1 ;;          # 存檔(模態選單 + 文字層)
    7) xdotool key Escape ;;
  esac
  sleep 0.6
done
sleep 2
kill -0 $SV 2>/dev/null && echo "SURVIVED" || echo "CRASHED-OR-ASAN-ABORT"
pkill scummvm 2>/dev/null
chown 1000:1000 /work/screenshots/sweep_'"$TAG"'.log
' 2>&1 | grep -E "SURVIVED|CRASHED"

L="$PROJ/screenshots/sweep_${TAG}.log"
echo "--- CHTOVL(確認實際 overlay 尺寸/bpp)---"
grep "CHTOVL" "$L" | head -3
echo "--- ASan ---"
if grep -q "ERROR: AddressSanitizer" "$L"; then
	grep -m1 -A6 "ERROR: AddressSanitizer" "$L" | sed 's/(BuildId:.*//'
else
	echo "  乾淨"
fi
