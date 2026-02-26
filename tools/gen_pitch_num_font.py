#!/usr/bin/env python3
"""
Generate _pitch_num.woff2 — a tiny web font where ASCII digits 0-9 are
the rounded-rectangle pitch-number glyphs extracted from Hiragino Mincho ProN's
nalt alternate index 8 (CSS "nalt" 9).

On macOS/iOS, the CSS uses Hiragino directly with font-feature-settings.
On other platforms (Android/Windows), this bundled font provides the fallback.

Usage:
    python3 tools/gen_pitch_num_font.py

Output:
    note-types/mvj/_pitch_num.woff2

Requires: fontTools, brotli (pip install fonttools brotli)

Licensing: Contains glyph outlines from Apple's Hiragino Mincho ProN.
           Fine for personal Anki use; for redistribution, swap source to
           Noto Sans CJK JP (OFL, also has nalt alternates).
"""

import os
import sys
from fontTools.ttLib import TTFont
from fontTools.fontBuilder import FontBuilder
from fontTools.pens.t2CharStringPen import T2CharStringPen
from fontTools.pens.recordingPen import RecordingPen
from fontTools.misc.psCharStrings import T2CharString

HIRAGINO_PATH = "/System/Library/Fonts/ヒラギノ明朝 ProN.ttc"
NALT_INDEX = 8  # 0-based; corresponds to CSS "nalt" 9
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "..", "note-types", "mvj")
OUTPUT_FILE = os.path.join(OUTPUT_DIR, "_pitch_num.woff2")


def main():
    if not os.path.exists(HIRAGINO_PATH):
        print(f"Error: Hiragino Mincho ProN not found at {HIRAGINO_PATH}", file=sys.stderr)
        sys.exit(1)

    # Open the W3 (regular) face
    src = TTFont(HIRAGINO_PATH, fontNumber=0)
    cmap = src.getBestCmap()
    gsub = src["GSUB"]

    # Find nalt lookup
    nalt_lookup_idx = None
    for rec in gsub.table.FeatureList.FeatureRecord:
        if rec.FeatureTag == "nalt":
            nalt_lookup_idx = rec.Feature.LookupListIndex[0]
            break
    if nalt_lookup_idx is None:
        print("Error: nalt feature not found in GSUB", file=sys.stderr)
        sys.exit(1)

    alt_sub = gsub.table.LookupList.Lookup[nalt_lookup_idx].SubTable[0]

    # Map digit codepoints to their nalt alternate glyph names
    glyph_map = {}  # digit -> (base_glyph_name, alt_glyph_name)
    for digit in range(10):
        cp = 0x30 + digit
        base_glyph = cmap.get(cp)
        if base_glyph is None or base_glyph not in alt_sub.alternates:
            print(f"Error: no nalt alternate for digit {digit}", file=sys.stderr)
            sys.exit(1)
        alts = alt_sub.alternates[base_glyph]
        if len(alts) <= NALT_INDEX:
            print(f"Error: digit {digit} has only {len(alts)} alternates", file=sys.stderr)
            sys.exit(1)
        glyph_map[digit] = (base_glyph, alts[NALT_INDEX])

    print("Glyph mapping:")
    for d, (base, alt) in sorted(glyph_map.items()):
        print(f"  '{d}': {base} -> {alt}")

    # Extract metrics from source
    upm = src["head"].unitsPerEm
    src_os2 = src["OS/2"]
    src_hhea = src["hhea"]
    glyph_set = src.getGlyphSet()

    # Glyph names for new font
    glyph_order = [".notdef"] + [f"digit{d}" for d in range(10)]

    # Build new font
    fb = FontBuilder(upm, isTTF=False)
    fb.setupGlyphOrder(glyph_order)

    # cmap: map ASCII digits to our glyph names
    fb.setupCharacterMap({0x30 + d: f"digit{d}" for d in range(10)})

    # Record glyph outlines and collect metrics
    hmtx = {".notdef": (500, 0)}
    recordings = {}

    for digit in range(10):
        alt_name = glyph_map[digit][1]
        rec = RecordingPen()
        glyph_set[alt_name].draw(rec)
        recordings[digit] = rec
        hmtx[f"digit{digit}"] = (src["hmtx"][alt_name][0], src["hmtx"][alt_name][1])

    fb.setupHorizontalMetrics(hmtx)

    fb.setupHorizontalHeader(ascent=src_hhea.ascent, descent=src_hhea.descent)

    fb.setupNameTable({"familyName": "PitchNum", "styleName": "Regular"})

    fb.setupOS2(
        sTypoAscender=src_os2.sTypoAscender,
        sTypoDescender=src_os2.sTypoDescender,
        sTypoLineGap=src_os2.sTypoLineGap,
        usWinAscent=src_os2.usWinAscent,
        usWinDescent=src_os2.usWinDescent,
        sxHeight=src_os2.sxHeight,
        sCapHeight=src_os2.sCapHeight,
    )

    fb.setupPost()

    # Build CFF charstrings
    charstrings = {}

    # .notdef — empty glyph
    cs = T2CharString()
    cs.program = [500, "hmoveto", "endchar"]
    charstrings[".notdef"] = cs

    for digit in range(10):
        name = f"digit{digit}"
        width = hmtx[name][0]
        pen = T2CharStringPen(width=width, glyphSet=None)
        recordings[digit].replay(pen)
        charstrings[name] = pen.getCharString()

    fb.setupCFF(
        psName="PitchNum-Regular",
        fontInfo={"version": "1.0"},
        charStringsDict=charstrings,
        privateDict={},
    )

    # Save as woff2
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    fb.font.flavor = "woff2"
    fb.font.save(OUTPUT_FILE)

    size = os.path.getsize(OUTPUT_FILE)
    print(f"\nGenerated {OUTPUT_FILE} ({size:,} bytes)")


if __name__ == "__main__":
    main()
