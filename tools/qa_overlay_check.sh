#!/usr/bin/env bash
# ============================================================================
# QA 判定: 把 qa_<tag>.png 統一縮回 640x400 基準空間, 對「已知正確的 x2 基準」比對,
# 並量測動詞面板中文 ROI 的黑底/亮字比例。全程 docker(imagemagick), 不污染 host。
#
# 判定依據(overlay 座標正確時, 不論倍率, 縮回 640x400 後佈局應幾乎一致):
#   RMSE vs qa_x2.png  < 0.10  → PASS
#   右欄中文區(x554..640, y16..246)/ 左欄(x6..90, y22..90)應是黑底白字:
#     mean 亮度 < 0.35 且亮像素(>60%)佔比 2%..25%
#
# 用法: scripts/qa_overlay_check.sh <tag> [tag2 ...]
# ============================================================================
set -u
cd "$(dirname "$0")/.." || exit 1
ROOT="$PWD"

TAGS="$*"
[ -n "$TAGS" ] || { echo "用法: $0 <tag> [tag2 ...]"; exit 1; }

docker run --rm -v "$ROOT:/w" agos-build bash -c '
cd /w/screenshots
base=qa_x2.png
[ -f "$base" ] || { echo "缺基準 qa_x2.png"; exit 1; }
convert "$base" -filter point -resize 640x400\! /tmp/base.png
printf "%-8s %-9s %-22s %-22s %s\n" TAG RMSEvsX2 "右欄(mean/亮佔比)" "左欄(mean/亮佔比)" 判定
for t in '"$TAGS"'; do
  f=qa_$t.png
  [ -f "$f" ] || { printf "%-8s %s\n" "$t" "(無截圖)"; continue; }
  convert "$f" -filter point -resize 640x400\! /tmp/c.png
  rmse=$(convert /tmp/c.png /tmp/base.png -metric RMSE -compare -format "%[distortion]" info: 2>/dev/null)
  # 右欄動詞面板中文區
  rm_mean=$(convert /tmp/c.png -crop 86x230+554+16 +repage -colorspace Gray -format "%[fx:mean]" info:)
  rm_lit=$(convert /tmp/c.png -crop 86x230+554+16 +repage -colorspace Gray -threshold 60% -format "%[fx:mean]" info:)
  lf_mean=$(convert /tmp/c.png -crop 84x68+6+22 +repage -colorspace Gray -format "%[fx:mean]" info:)
  lf_lit=$(convert /tmp/c.png -crop 84x68+6+22 +repage -colorspace Gray -threshold 60% -format "%[fx:mean]" info:)
  verdict=$(awk -v r="$rmse" -v rm="$rm_mean" -v rl="$rm_lit" -v lm="$lf_mean" -v ll="$lf_lit" '"'"'
    BEGIN{
      ok=1; why="";
      if (r >= 0.10) { ok=0; why=why "佈局偏移 "; }
      if (rm >= 0.35 || rl < 0.02 || rl > 0.25) { ok=0; why=why "右欄異常 "; }
      if (lm >= 0.35 || ll < 0.02 || ll > 0.25) { ok=0; why=why "左欄異常 "; }
      print (ok ? "PASS" : "FAIL " why);
    }'"'"')
  printf "%-8s %-9.4f %-22s %-22s %s\n" "$t" "$rmse" "$(printf %.3f/%.3f $rm_mean $rm_lit)" "$(printf %.3f/%.3f $lf_mean $lf_lit)" "$verdict"
done
'
