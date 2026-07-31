#!/usr/bin/env python3
# 從倚天中文系統(ETEN 3.53)原生點陣字烘 DCJK 字型,供 AGOS CJK patch 使用。
#
# 為什麼不用 TTF:1990 年的 DOS 中文長什麼樣,倚天就長什麼樣。TTF 縮到 15–24px
# 筆劃比例不對、複雜字糊成一團;倚天是為該尺寸手工調過的點陣字。
#
# 來源(裸格式,每列 (W+7)//8 bytes、MSB-first、由上而下):
#   stdfont.15  16×15 漢字 13094 字,30 B/字
#   SPCFONT.15  16×15 全形標點 408 字,30 B/字   ← 漏帶會讓所有標點掉 fallback
#   stdfont.24  24×24 漢字 13094 字,72 B/字     (STD.24M 經 etunpack 解壓)
#   SPCFONT.24  24×24 全形標點 408 字,72 B/字
#
# 倚天的索引是「Big5 分區」不是線性,而 DCJK 是線性 (lead-0x81)*157+trailOffset,
# 兩者碼空間不同,必須逐字轉換(見下 eten_slot)。兩邊的 stride 剛好相同
# (16×15→2B/列、24×24→3B/列),故字模本身可直接複製,不需重排位元。
#
# 用法:
#   python3 build_eten_font.py --size 15 --std <stdfont.15> --spc <SPCFONT.15> \
#       --out run_game/elvira1_zh16.dcjk [--fallback-ttf <ttf>]
import argparse, struct, sys

BIG5_LEADS = range(0x81, 0xFF)
NUM_GLYPHS = (0xFE - 0x81 + 1) * 157      # 19782

# --- DCJK 線性索引 ---------------------------------------------------------
def dcjk_index(lead, trail):
    if 0x40 <= trail <= 0x7E:   to = trail - 0x40
    elif 0xA1 <= trail <= 0xFE: to = 63 + (trail - 0xA1)
    else: return -1
    return (lead - 0x81) * 157 + to

# --- 倚天 Big5 分區索引 ----------------------------------------------------
def raw(hi, lo):
    return (hi - 0xA1) * 157 + ((lo - 0x40) if lo < 0x7F else (lo - 0x62))

LAST_SPC    = raw(0xA3, 0xBF)     # 符號區尾 = 407
BASE_A440   = raw(0xA4, 0x40)     # 漢字常用區起點
LAST_COMMON = raw(0xC6, 0x7E)     # 常用字尾
BASE_C940   = raw(0xC9, 0x40)     # 次常用起點
N_COMMON    = 5401

def eten_slot(hi, lo):
    """回傳 ('spc'|'std', idx);倚天沒有的碼位回 None。"""
    r = raw(hi, lo)
    if r < 0:              return None
    if r <= LAST_SPC:      return ('spc', r)
    if r < BASE_A440:      return None                      # A3C0–A3FE 控制碼區
    if r <= LAST_COMMON:   return ('std', r - BASE_A440)
    if r < BASE_C940:      return None                      # C6A1–C8FE 造字區
    return ('std', N_COMMON + (r - BASE_C940))

def embolden(glyph, w, h, bpr):
    """筆劃水平膨脹 1px。倚天 15 點只有明體一種、偏細, 疊在深色面板上對比不足;
    加粗後厚實好讀, 且複雜字仍保有原生 15 點手工排過的結構(優於把 24 點縮小)。"""
    out = bytearray(glyph)
    for row in range(h):
        base = row * bpr
        for col in range(w - 1, 0, -1):
            if glyph[base + ((col - 1) >> 3)] & (0x80 >> ((col - 1) & 7)):
                out[base + (col >> 3)] |= (0x80 >> (col & 7))
    return bytes(out)

def ascii_art(glyph, w, h, bpr):
    out = []
    for row in range(h):
        line = ''
        for col in range(w):
            b = glyph[row * bpr + (col >> 3)]
            line += '#' if (b & (0x80 >> (col & 7))) else '.'
        out.append(line)
    return '\n'.join(out)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--size', type=int, required=True, help='15(16x15) 或 24(24x24)')
    ap.add_argument('--std', required=True)
    ap.add_argument('--spc', required=True)
    ap.add_argument('--out', required=True)
    ap.add_argument('--fallback-ttf', help='倚天缺字時用這個 TTF 補同尺寸')
    ap.add_argument('--bold', action='store_true', help='程式加粗(水平膨脹 1px);15 點倚天只有偏細明體時建議開')
    ap.add_argument('--selftest', action='store_true', help='dump 驗收字')
    a = ap.parse_args()

    if a.size == 15:   W, H = 16, 15
    elif a.size == 24: W, H = 24, 24
    else: sys.exit('--size 只支援 15 或 24(倚天原生尺寸;別把 16x15 放大成 24)')
    bpr = (W + 7) // 8
    stride = bpr * H

    std = open(a.std, 'rb').read()
    spc = open(a.spc, 'rb').read()
    n_std, n_spc = len(std) // stride, len(spc) // stride
    print(f'來源: std {n_std} 字 / spc {n_spc} 字 (stride {stride}B)')

    # 驗收 oracle(kb eten-bitmap-font): std idx=0 必須是「一」
    first = std[0:stride]
    ink_rows = [r for r in range(H) if any(first[r * bpr + c] for c in range(bpr))]
    if len(ink_rows) > 3:
        sys.exit(f'!! std idx=0 不像「一」(墨水佔 {len(ink_rows)} 列) — 索引或檔案不對')
    print(f'  ✓ oracle: std idx=0 是單橫線(墨水 {len(ink_rows)} 列)= 「一」')

    glyphs = bytearray(NUM_GLYPHS * stride)
    n_eten = n_fb = n_miss = 0

    face = None
    if a.fallback_ttf:
        import freetype
        face = freetype.Face(a.fallback_ttf)
        face.set_pixel_sizes(W, H)

    for lead in BIG5_LEADS:
        for trail in list(range(0x40, 0x7F)) + list(range(0xA1, 0xFF)):
            di = dcjk_index(lead, trail)
            if di < 0: continue
            slot = eten_slot(lead, trail)
            src = None
            if slot:
                which, idx = slot
                buf, n = (spc, n_spc) if which == 'spc' else (std, n_std)
                if 0 <= idx < n:
                    src = buf[idx * stride:(idx + 1) * stride]
            if src is not None and any(src):
                glyphs[di * stride:(di + 1) * stride] = embolden(src, W, H, bpr) if a.bold else src
                n_eten += 1
                continue
            # 倚天沒有 → 真缺字才 fallback(數量是品質指標,一大批就是索引錯了)
            if face is None:
                n_miss += 1
                continue
            try:
                ch = bytes([lead, trail]).decode('big5')
            except Exception:
                n_miss += 1
                continue
            face.load_char(ch, 0x4 | 0x10000)   # FT_LOAD_RENDER | FT_LOAD_TARGET_MONO
            bm = face.glyph.bitmap
            gw, gh, pitch = bm.width, bm.rows, bm.pitch
            if gw == 0 or gh == 0:
                n_miss += 1
                continue
            ox, oy = max(0, (W - gw) // 2), max(0, (H - gh) // 2)
            got = False
            for row in range(gh):
                yy = oy + row
                if yy >= H: break
                for col in range(gw):
                    xx = ox + col
                    if xx >= W: break
                    if bm.buffer[row * pitch + (col >> 3)] & (0x80 >> (col & 7)):
                        glyphs[di * stride + yy * bpr + (xx >> 3)] |= (0x80 >> (xx & 7))
                        got = True
            if got: n_fb += 1
            else:   n_miss += 1

    with open(a.out, 'wb') as f:
        f.write(b'DCJK')
        f.write(bytes([1, W, H, bpr, 0, 0, 0]))
        f.write(struct.pack('<I', NUM_GLYPHS))
        f.write(glyphs)
    print(f'寫入 {a.out}: {W}x{H}, 倚天 {n_eten} 字 / TTF 補 {n_fb} 字 / 空 {n_miss} 槽, '
          f'{15 + len(glyphs)} bytes')

    if a.selftest:
        for label, (hi, lo) in [('一', (0xA4, 0x40)), ('中', (0xA4, 0xA4)),
                                ('猴', (0xB5, 0x55)), ('，', (0xA1, 0x41)),
                                ('開', (0xB6, 0x7D))]:
            di = dcjk_index(hi, lo)
            g = glyphs[di * stride:(di + 1) * stride]
            print(f'--- {label} (0x{hi:02X}{lo:02X}) ---')
            print(ascii_art(g, W, H, bpr))

if __name__ == '__main__':
    main()
