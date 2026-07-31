/* Elvira 1（古堡禁地）繁中融合 — 載入器 (非上游) */
#include "agos/cht_fusion.h"
#include "common/file.h"
#include "common/debug.h"

namespace AGOS {

// 非上游: DCJK 字型載入的共用實作 + header 驗證。
//
// 為什麼要驗 header:dataSize = numGlyphs × bpr × h。如果字型檔損毀、被截斷、
// 或玩家放錯檔,這個乘積可能溢位或算出比實際需要小的值 → malloc 出來的 buffer
// 小於 glyph 索引的上限(numGlyphs),而 glyphXX() 是拿 numGlyphs 驗界的,
// 驗界就形同虛設 → 越界讀。所以這裡要求 header 自洽、不溢位、而且檔案真的裝得下,
// 三者其一不成立就當作載入失敗(引擎會落回英文,總比讀壞記憶體好)。
static bool chtLoadDcjk(const char *filename, byte **outData,
                        int *outW, int *outH, int *outBpr, uint32 *outN) {
	Common::File f;
	if (!f.open(filename))
		return false;
	byte hdr[15];
	if (f.read(hdr, 15) != 15 || memcmp(hdr, "DCJK", 4) != 0)
		return false;

	int w = hdr[5], h = hdr[6], bpr = hdr[7];
	uint32 n = READ_LE_UINT32(hdr + 11);

	// 尺寸要在合理範圍, 且 bpr 必須真的等於 ceil(w/8) —— 對不起來就是檔案有問題
	if (w <= 0 || w > 64 || h <= 0 || h > 64 || bpr != (w + 7) / 8) {
		warning("CHT: %s header 不合理 (%dx%d bpr=%d), 略過", filename, w, h, bpr);
		return false;
	}
	// Big5 線性索引最多 (0xFE-0x81+1)*157 = 19782, 給一點餘裕但不接受離譜值
	if (n == 0 || n > 65536) {
		warning("CHT: %s glyph 數異常 (%u), 略過", filename, n);
		return false;
	}
	uint32 per = (uint32)bpr * (uint32)h;
	if (per == 0 || n > 0xFFFFFFFFu / per) {          // 乘法溢位防護
		warning("CHT: %s 尺寸乘積溢位, 略過", filename);
		return false;
	}
	uint32 dataSize = n * per;
	int32 avail = f.size() - 15;
	if (avail < 0 || (uint32)avail < dataSize) {      // 檔案要真的裝得下宣告的字數
		warning("CHT: %s 檔案被截斷 (需要 %u, 只有 %d), 略過", filename, dataSize, avail);
		return false;
	}

	byte *data = (byte *)malloc(dataSize);
	if (!data)
		return false;
	if (f.read(data, dataSize) != dataSize) {
		free(data);
		return false;
	}
	*outData = data; *outW = w; *outH = h; *outBpr = bpr; *outN = n;
	return true;
}

// 載入 DCJK 字型檔到 fus.font (24x24, 大字/標題/地圖)
bool chtLoadFont(ChtFusion &fus, const char *filename) {
	byte *data = nullptr;
	int w = 0, h = 0, bpr = 0;
	uint32 n = 0;
	if (!chtLoadDcjk(filename, &data, &w, &h, &bpr, &n))
		return false;
	free(fus.font);                    // 重複載入時不要漏掉舊的
	fus.font = data;
	fus.fontW = w; fus.fontH = h; fus.fontBpr = bpr; fus.numGlyphs = n;
	debug(0, "CHT: font %s loaded (%dx%d, %u glyphs)", filename, w, h, n);
	return true;
}

// 載入 DCJK 字型檔到 fus.font16 (視窗文字 + 對白層; 倚天 16x15 細版)
bool chtLoadFont16(ChtFusion &fus, const char *filename) {
	byte *data = nullptr;
	int w = 0, h = 0, bpr = 0;
	uint32 n = 0;
	if (!chtLoadDcjk(filename, &data, &w, &h, &bpr, &n))
		return false;
	free(fus.font16);
	fus.font16 = data;
	fus.fontW16 = w; fus.fontH16 = h; fus.fontBpr16 = bpr; fus.numGlyphs16 = n;
	debug(0, "CHT: panel font %s loaded (%dx%d, %u glyphs)", filename, w, h, n);
	return true;
}

// 載入 DCJK 字型檔到 fus.fontBold (動詞面板; 倚天 16x15 程式加粗版)
bool chtLoadFontBold(ChtFusion &fus, const char *filename) {
	byte *data = nullptr;
	int w = 0, h = 0, bpr = 0;
	uint32 n = 0;
	if (!chtLoadDcjk(filename, &data, &w, &h, &bpr, &n))
		return false;
	free(fus.fontBold);
	fus.fontBold = data;
	fus.fontWBold = w; fus.fontHBold = h; fus.fontBprBold = bpr; fus.numGlyphsBold = n;
	debug(0, "CHT: panel bold font %s loaded (%dx%d, %u glyphs)", filename, w, h, n);
	return true;
}

// 載入譯表 elvira1_zh.tab (STAB: magic, count, [id:4][len:2][big5..])
bool chtLoadTable(ChtFusion &fus, const char *filename) {
	Common::File f;
	if (!f.open(filename))
		return false;
	byte magic[4];
	if (f.read(magic, 4) != 4 || memcmp(magic, "STAB", 4) != 0)
		return false;
	uint32 count = f.readUint32LE();
	for (uint32 i = 0; i < count; i++) {
		uint32 id = f.readUint32LE();
		uint16 len = f.readUint16LE();
		Common::String s;
		for (uint16 k = 0; k < len; k++)
			s += (char)f.readByte();
		fus.table[id] = s;
	}
	debug(0, "CHT: translation table %s loaded (%u entries)", filename, count);
	return true;
}

// 載入語音對映 (Elvira 1 floppy 無語音, 保留) (VMAP: magic, count, [id:4][speech:2])
bool chtLoadVoiceMap(ChtFusion &fus, const char *filename) {
	Common::File f;
	if (!f.open(filename))
		return false;
	byte magic[4];
	if (f.read(magic, 4) != 4 || memcmp(magic, "VMAP", 4) != 0)
		return false;
	uint32 count = f.readUint32LE();
	for (uint32 i = 0; i < count; i++) {
		uint32 id = f.readUint32LE();
		uint16 sp = f.readUint16LE();
		fus.voice[id] = sp;
	}
	debug(0, "CHT: voice map %s loaded (%u entries)", filename, count);
	return true;
}

} // namespace AGOS
