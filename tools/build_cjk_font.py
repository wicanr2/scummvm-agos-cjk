#!/usr/bin/env python3
# 從 TTF 烘 Big5 點陣字型 atlas (DCJK 格式), 供 AGOS CJK patch 使用。
# 用法: python3 build_cjk_font.py --size 24 --font <ttf> --out simon_zh24.dcjk
#
# DCJK 格式 (little-endian 數值):
#   0  4  magic "DCJK"
#   4  1  version=1
#   5  1  width
#   6  1  height
#   7  1  bytesPerRow = (width+7)//8
#   8  1  encoding=0 (Big5 linear index)
#   9  2  reserved
#   11 4  numGlyphs (LE) = 19782 (Big5 lead 0x81..0xFE × 157)
#   15 .. glyphs[numGlyphs * bytesPerRow * height], 1bpp MSB-first per row
import argparse, struct, sys
import freetype

BIG5_LEADS = range(0x81, 0xFF)      # 0x81..0xFE
NUM_GLYPHS = (0xFE - 0x81 + 1) * 157  # 126*157 = 19782

def big5_linear_index(lead, trail):
    if trail is None: return -1
    if 0x40 <= trail <= 0x7E: to = trail - 0x40
    elif 0xA1 <= trail <= 0xFE: to = 63 + (trail - 0xA1)
    else: return -1
    return (lead - 0x81) * 157 + to

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--size', type=int, default=24)
    # 高度可與寬度不同: 面板列距 16px, 字模高 16 就零間隙、上下列會黏在一起
    # (倚天原生是 16x15 才留得下 1px)。烘 TTF 當替代字型時要一併對齊這個尺寸。
    ap.add_argument('--height', type=int, default=0, help='字模高度(預設同 --size)')
    ap.add_argument('--font', required=True)
    ap.add_argument('--out', required=True)
    a = ap.parse_args()
    W = a.size
    H = a.height if a.height else a.size
    bpr = (W + 7) // 8
    face = freetype.Face(a.font)
    face.set_pixel_sizes(W, H)

    glyphs = bytearray(NUM_GLYPHS * bpr * H)  # 全 0 預設
    filled = 0
    for lead in BIG5_LEADS:
        for trail in list(range(0x40, 0x7F)) + list(range(0xA1, 0xFF)):
            idx = big5_linear_index(lead, trail)
            if idx < 0: continue
            try:
                ch = bytes([lead, trail]).decode('big5')
            except Exception:
                continue
            face.load_char(ch, freetype.FT_LOAD_RENDER | freetype.FT_LOAD_TARGET_MONO)
            bm = face.glyph.bitmap
            gw, gh, pitch = bm.width, bm.rows, bm.pitch
            # 置中
            ox = max(0, (W - gw) // 2)
            oy = max(0, (H - gh) // 2)
            # baseline 對齊: 用 bitmap_top 粗略垂直置中
            base = H * 4 // 5
            oy = max(0, base - face.glyph.bitmap_top)
            buf = bm.buffer
            any_px = False
            for row in range(gh):
                yy = oy + row
                if yy >= H: break
                for col in range(gw):
                    xx = ox + col
                    if xx >= W: break
                    byte = buf[row * pitch + (col >> 3)]
                    if byte & (0x80 >> (col & 7)):
                        gi = idx * bpr * H + yy * bpr + (xx >> 3)
                        glyphs[gi] |= (0x80 >> (xx & 7))
                        any_px = True
            if any_px: filled += 1

    with open(a.out, 'wb') as f:
        f.write(b'DCJK')
        f.write(bytes([1, W, H, bpr, 0, 0, 0]))
        f.write(struct.pack('<I', NUM_GLYPHS))
        f.write(glyphs)
    print(f"寫入 {a.out}: {W}x{H}, {NUM_GLYPHS} glyph 槽, 實際填 {filled} 字, 大小 {15 + len(glyphs)} bytes")

if __name__ == '__main__':
    main()
