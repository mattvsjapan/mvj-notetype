# PitchNum Font — Technical Notes

## What SMK8 Does

The Shin Meikai Kokugo Jiten (新明解国語辞典, 8th edition) displays pitch accent numbers
like `[0]`, `[1]`, `[2]` etc. as **numbers inside rounded rectangles**.

## How It Works

### XML Markup (Dictionary)

Each accent number is wrapped in custom elements:

```xml
<アクセント>
  <a href="$a">
    <accent0>⓪</accent0>
  </a>
</アクセント>
```

Tags: `<accent0>` through `<accent17>`, with Unicode circled numbers as fallback text content.

### CSS (Dictionary.app)

```css
アクセント { text-combine-horizontal: all; }

/* Replace fallback text with font glyph by CID */
accent0 { glyph: 11307; }
accent1 { glyph: 11309; }
accent2 { glyph: 11311; }
/* ... etc ... */
```

The `glyph:` property is **Apple Dictionary.app proprietary** — it tells the renderer
to use a specific glyph from the font by CID (Character ID), bypassing Unicode entirely.

### The Font: Hiragino Mincho ProN

- Standard macOS system font by Screen Graphics (SCREENグラフィックソリューションズ)
- Located at `/System/Library/Fonts/ヒラギノ明朝 ProN.ttc`
- CFF (Compact Font Format) outlines — vector paths stored as compressed PostScript bytecode
- Implements **Adobe-Japan1** character collection (Supplement 7, 23,060 CIDs)

### The Glyphs

Standard Adobe-Japan1 Supplement 4 glyphs (CIDs 9354–15443). Not custom.

The rounded-rectangle annotation block spans **CIDs 11307–11845** (539 glyphs), containing
numbers, kanji, and other symbols inside rounded boxes. Every Adobe-Japan1-4+ compliant
Japanese font has them (Hiragino, Kozuka, Morisawa, etc.).

They have **no Unicode mapping** but are accessible via the **`nalt` (Notation Alternates)**
OpenType feature. The rounded-rect variants are **alternate index 9** for plain digit characters.

### OpenType Access: `nalt` Feature

The `nalt` GSUB feature (AlternateSubst, Type 3) maps plain ASCII digits to annotation variants.
For each digit, alternate 9 is the rounded-rectangle form:

```
"0" (U+0030) -> nalt alternate [8] = cid11307  (rounded rect 0)
"1" (U+0031) -> nalt alternate [8] = cid11309  (rounded rect 1)
"2" (U+0032) -> nalt alternate [8] = cid11311  (rounded rect 2)
...
```

Full alternates list (using "1" as example):

| Index | Glyph    | Style                    |
|-------|----------|--------------------------|
| 0     | ①       | Circled                  |
| 1     | ⒈       | Period-suffix            |
| 2     | ⑴       | Parenthesized            |
| 3     | ❶       | Black circle (solid)     |
| 4     | (none)   | Parenthesized alt        |
| 5     | (none)   | Double-circle            |
| 6     | (none)   | Black square             |
| 7     | (none)   | Square                   |
| 8     | (none)   | **Rounded rectangle**    |
| 9     | (none)   | Black rounded rectangle  |

In CSS, `font-feature-settings: "nalt" 9` selects the rounded-rectangle variants.

### CID Mapping Table

| Accent | CID   | Fallback Unicode | Unicode Codepoint |
|--------|-------|------------------|-------------------|
| 0      | 11307 | ⓪               | U+24EA            |
| 1      | 11309 | ①               | U+2460            |
| 2      | 11311 | ②               | U+2461            |
| 3      | 11313 | ③               | U+2462            |
| 4      | 11315 | ④               | U+2463            |
| 5      | 11317 | ⑤               | U+2464            |
| 6      | 11319 | ⑥               | U+2465            |
| 7      | 11321 | ⑦               | U+2466            |
| 8      | 11323 | ⑧               | U+2467            |
| 9      | 11325 | ⑨               | U+2468            |
| 10     | 11327 | ⑩               | U+2469            |
| 11     | 11328 | ⑪               | U+246A            |
| 12     | 11329 | ⑫               | U+246B            |
| 13     | 11330 | ⑬               | U+246C            |
| 17     | 11334 | --               | --                |

CID pattern for 0–9: **CID = 11307 + (n * 2)** (odd-numbered CIDs are single-digit).
Even-numbered CIDs (11308, 11310...) are two-digit alternate forms (00, 01, 02...).

### Visual Difference

- **Unicode circled numbers** (⓪①②): digit inside a **circle**
- **Adobe-Japan1 CID glyphs**: digit inside a **rounded rectangle** (角丸囲み)

---

## Anki Implementation

### Current approach: `nalt 9` with PitchNum fallback font

On macOS/iOS, Hiragino Mincho ProN renders the glyphs natively via `nalt 9`.
On other platforms (Android, Windows), the PitchNum woff2 font provides the same glyphs.

```css
@font-face {
  font-family: 'PitchNum';
  src: url('_pitch_num.woff2') format('woff2');
  font-weight: 100 900;
}

.pitch-num {
  font-family: "Hiragino Mincho ProN", "PitchNum";
  font-feature-settings: "nalt" 9;
}
```

### Platform Notes

- **macOS / iOS**: Hiragino is a system font — works out of the box.
- **Android / Windows / Linux**: PitchNum woff2 provides the glyphs via `@font-face`.

---

## PitchNum Font: WKWebView Loading Issue

### Problem

Anki's WKWebView silently rejects small/subsetted fonts loaded via `@font-face`.
The font works in Safari and Chrome but not in Anki's WebView.

### Root cause

**WKWebView rejects fonts whose internal table structures have been modified by subsetting.**
It's not about glyph count, file size, missing tables, or fsType — it's that the fonttools
subsetter rebuilds CFF charsets, prunes GSUB/GPOS lookups, and modifies cmap entries in ways
that fail WKWebView's font validator.

### Solution

Instead of subsetting Hiragino down to just digits (which breaks the font), we **hollow it out**:
load the full 20K-glyph font, replace all non-essential glyph outlines with empty CFF charstrings,
but keep every table, glyph ID, cmap entry, and GSUB/GPOS lookup intact.
Result: 261 KB woff2 that passes WKWebView validation.

### Test results

| Test | Glyphs | Size | Works? |
|------|--------|------|--------|
| Full Hiragino (no subsetter) | 20,327 | 5.6 MB | YES |
| Full cmap through subsetter | 19,912 | 5.6 MB | YES |
| First half of cmap (subsetter) | 13,310 | 2.8 MB | NO |
| Latin + kana + CJK (subsetter) | 11,488 | 4.3 MB | NO |
| Latin + kana (subsetter) | 1,049 | 104 KB | NO |
| Digits only, all flags preserved (subsetter) | 425 | 42 KB | NO |
| Digits only, default subsetter | 63 | 5.8 KB | NO |
| **Hollowed (full structure, empty outlines)** | **20,327** | **261 KB** | **YES** |
| Original hand-built PitchNum | 12 | ~1.5 KB | NO |
| Rebuilt PitchNum (fsType=0, names, space) | 12 | ~1.5 KB | NO |
| Base64-inlined PitchNum | 12 | inline | NO |

### What the subsetter changes that breaks things

1. Rebuilds CFF charset (fewer glyph entries, renumbered IDs)
2. Prunes GSUB/GPOS lookups referencing removed glyphs
3. Removes cmap mappings for deleted codepoints
4. Changes maxp glyph count

The hollowed approach avoids all of this — identical structure to the original font.

### What did NOT matter

- `OS/2.fsType` (changed from 4→0, no effect; base64 also failed)
- Font-weight range in @font-face
- Position of @font-face in CSS
- Font rebuild with full name table and space glyph
- Restarting Anki
- Number of OpenType tables (subsetter preserved all tables, still failed)
- File size (4.3 MB subset failed while 261 KB hollowed version works)
