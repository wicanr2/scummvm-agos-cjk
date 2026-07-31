/* Elvira 1 - Mistress of the Dark（古堡禁地）繁體中文化 — 非上游模組。
 * 資料: elvira1_zh24.dcjk (Big5 24x24 點陣), elvira1_zh16.dcjk (16x16),
 *       elvira1_zh.tab (id→Big5 譯表)。
 * 引擎共用掛勾: getStringPtrByID(string.cpp) 依 stringId 換 Big5 完整譯文。
 */
#ifndef AGOS_CHT_FUSION_H
#define AGOS_CHT_FUSION_H

#include "common/scummsys.h"
#include "common/hashmap.h"
#include "common/str.h"

namespace AGOS {

// Big5 線性索引 (與 build_cjk_font.py 對齊): (lead-0x81)*157 + trailOffset
inline bool chtIsBig5Lead(byte c) { return c >= 0x81 && c <= 0xFE; }

inline int chtBig5Index(byte lead, byte trail) {
	if (lead < 0x81 || lead > 0xFE)
		return -1;
	int to;
	if (trail >= 0x40 && trail <= 0x7E)
		to = trail - 0x40;
	else if (trail >= 0xA1 && trail <= 0xFE)
		to = 63 + (trail - 0xA1);
	else
		return -1;
	return (lead - 0x81) * 157 + to;
}

struct ChtFusion {
	// 字型 (24x24, 字幕/視窗文字用)
	byte *font = nullptr;      // DCJK glyph 區起點 (跳過 15-byte header)
	int fontW = 0, fontH = 0, fontBpr = 0;
	uint32 numGlyphs = 0;
	// 小字型 (16x16, 底部指令面板小格用)
	byte *font16 = nullptr;
	int fontW16 = 0, fontH16 = 0, fontBpr16 = 0;
	uint32 numGlyphs16 = 0;
	// 加粗字型 (倚天 16x15 程式加粗, 動詞面板用)
	// 倚天 15 點只有偏細的明體一種; 面板字少、疊在深色底上, 加粗才有對比。
	// 對白反過來要細版 —— 密集長文加粗會讓「爵/籠/罩/鑰」這類複雜字黏成塊。
	byte *fontBold = nullptr;
	int fontWBold = 0, fontHBold = 0, fontBprBold = 0;
	uint32 numGlyphsBold = 0;
	// 譯表: floppy stringId -> Big5 字串
	Common::HashMap<uint32, Common::String> table;
	// 語音: floppy stringId -> CD speechId (Elvira 1 floppy 無語音, 保留欄位)
	Common::HashMap<uint32, uint16> voice;

	bool fontLoaded() const { return font != nullptr; }
	bool hasTable() const { return !table.empty(); }

	// 取得某 Big5 字的 glyph bitmap (fontBpr*fontH bytes), 找不到回 nullptr
	const byte *glyph(byte lead, byte trail) const {
		if (!font) return nullptr;
		int idx = chtBig5Index(lead, trail);
		if (idx < 0 || (uint32)idx >= numGlyphs) return nullptr;
		return font + (uint32)idx * fontBpr * fontH;
	}

	// 16x16 小字模版本 (指令面板用)
	const byte *glyph16(byte lead, byte trail) const {
		if (!font16) return nullptr;
		int idx = chtBig5Index(lead, trail);
		if (idx < 0 || (uint32)idx >= numGlyphs16) return nullptr;
		return font16 + (uint32)idx * fontBpr16 * fontH16;
	}

	// 加粗字模版本 (動詞面板)
	const byte *glyphBold(byte lead, byte trail) const {
		if (!fontBold) return nullptr;
		int idx = chtBig5Index(lead, trail);
		if (idx < 0 || (uint32)idx >= numGlyphsBold) return nullptr;
		return fontBold + (uint32)idx * fontBprBold * fontHBold;
	}

};

bool chtLoadFont(ChtFusion &fus, const char *filename);
bool chtLoadFont16(ChtFusion &fus, const char *filename);
bool chtLoadFontBold(ChtFusion &fus, const char *filename);
bool chtLoadTable(ChtFusion &fus, const char *filename);
bool chtLoadVoiceMap(ChtFusion &fus, const char *filename);

} // namespace AGOS

#endif
