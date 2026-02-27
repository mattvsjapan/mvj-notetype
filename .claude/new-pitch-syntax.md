# New Pitch Accent Syntax (pitch-graphs)

This documents the colon-based pitch accent notation used by the pitch-graphs JavaScript templates. This is the **target format** that old MvJ semicolon-based notation needs to be converted to.

## Source Files

| File | Purpose |
|------|---------|
| `parse.js` | Tokenization, normalization, accent parsing, mora splitting, fragment merging |
| `section.js` | `Section` class, role/pitch resolution, high/low level calculation |
| `config.js` | Rendering configuration constants |
| `kana.js` | Hiragana/katakana conversion, pronunciation normalization |
| `graph.js` | SVG pitch graph rendering |
| `sentence.js` | Colored sentence HTML with ruby annotations |

## Field Format Overview

Pitch accent is placed **after** the word (outside the brackets) using a colon separator:

```
word[reading]:accent
```

The colon acts as both a separator and a marker that this token is an accented content word (as opposed to a particle, which has no colon). The reading stays inside brackets as pure furigana; accent metadata lives entirely after the colon.

## Section Structure

Each whitespace-separated token is a "section". The parser splits on `splitSection()` (`parse.js:78`):

```
word:accent   →  { word: "word", sep: ":", accent: "accent" }
particle      →  { word: "particle", sep: null, accent: "" }
```

The regex is `^([^:]+)(:)?(.*)$` — everything before the first colon is the word, the colon itself is `sep`, and everything after is the accent string.

- **Has colon** (`sep: ":"`) → content word (role determined from accent)
- **No colon** (`sep: null`) → particle (rendered without accent color, pitch inherited from context)

## Accent Format

The accent string after `:` is parsed by `splitAccent()` (`parse.js:84`) using the regex:

```
^(p)?([a-zA-Z])?(~)?(\d)?(~)?$
```

This matches the grammar:

```
accent = [p] [role] [~] [pitch] [~]
```

All parts are optional. Each component:

| Component | Values | Description |
|-----------|--------|-------------|
| `p` | `p` | Particle prefix — marks this as a particle that still carries accent info |
| `role` | `h`, `a`, `n`, `o`, `k`, `b`, `w`, `s`, `e`, `p` (or uppercase for Keihan) | Category letter (see Roles below) |
| `~` | `~` | All-low modifier — can appear before and/or after the pitch digit; either position forces all morae to low pitch (pitch becomes `-1`) |
| `pitch` | `0`–`9` | Numeric pitch (mora where drop occurs; 0 = heiban) |

The return value is `{ is_particle, role, allLow, pitch }`:

- `is_particle`: `'p'` or `null` — set when the `p` prefix is present
- `role`: the role letter, or falls back to `'p'` if only the `p` prefix was given (via `m[2] || m[1]`)
- `allLow`: `true` if either `~` position matched
- `pitch`: the digit as a string, or `null`

**Fallback**: If the accent string doesn't match either regex (Tokyo or Keihan), `splitAccent()` returns `{ role: null, pitch: null }` with no `allLow`, `is_particle`, or `keihan` properties.

### Keihan (Kyoto-Osaka) accent

A separate format for Keihan dialect, matched by a second regex:

```
^([a-zA-Z]{1,2}):([hlHL]+)$
```

```
accent = role:levels
```

Where `role` is 1–2 letters (case-insensitive — both uppercase and lowercase are accepted by the regex) and `levels` is a string of `h`/`l`/`H`/`L` characters specifying the pitch level of each mora (uppercase is lowercased by `determineLevelsKeihan()`).

Returns `{ role, levels, keihan: true }`.

If the `levels` string is shorter than the number of morae, `determineLevelsKeihan()` (`section.js:16`) extends it by repeating the last character until it matches the mora count.

Example: `H:hlh` — Keihan heiban with explicit high-low-high pattern.

## Roles

### Tokyo (standard) roles

Defined in `RoleFromValue` (`section.js:1`):

| Letter | Role name | Color class | Description |
|--------|-----------|-------------|-------------|
| `h` | heiban | `heiban` | Flat — pitch 0 (rises after first mora, stays high) |
| `a` | atamadaka | `atamadaka` | Head-high — pitch 1 (drops after first mora) |
| `n` | nakadaka | `nakadaka` | Middle drop — pitch 2+ (drops after mora N) |
| `o` | odaka | `odaka` | Tail-high — pitch = mora count (drops after last mora) |
| `k` | kifuku | `kifuku` | Rise-fall — used for verbs/i-adjectives with non-flat pitch |
| `b` | black | `black` | Neutral — rendered without accent color |
| `w` | white | `white` | White — special rendering |
| `s` | setsubigo | `setsubigo` | Suffix — treated like heiban for pitch calculation (pitch 0) |
| `e` | empty | `empty` | Empty — no circle on graph, used for separators |
| `p` | particle | `particle` | Particle — inherits pitch from preceding word |

### Keihan roles (uppercase)

| Letter | Role name | Description |
|--------|-----------|-------------|
| `H` | keihan_heiban | Keihan flat |
| `A` | keihan_atamadaka | Keihan head-high |
| `N` | keihan_nakadaka | Keihan middle drop |
| `L` | keihan_low_heiban | Keihan low flat |
| `M` | keihan_low_nakadaka | Keihan low middle drop |
| `O` | keihan_low_odaka | Keihan low tail-high |
| `K` | keihan_kifuku | Keihan rise-fall |

Keihan role resolution (`determineRoleKeihan()`, `section.js:11`) tries `RoleFromValue[val.toUpperCase()]` first, then `RoleFromValue[val.toLowerCase()]`, defaulting to `'keihan_heiban'`.

## Role Resolution

Role is determined by `determineRoleTokyo()` (`section.js:33`) using this priority:

1. **Zero morae or empty-particle word** (`|`, `,`, `、`) → `'empty'`
2. **No colon** (`sep == null`) → `'particle'`
3. **Colon but no role and no pitch** (e.g., `word:`) → `'particle'`
4. **Pitch number only** (no role letter) → inferred by `guessRoleFromPitchNum()`:

| Pitch | Inferred role |
|-------|---------------|
| `0` | heiban |
| `1` | atamadaka |
| N = mora count | odaka |
| N < mora count | nakadaka |
| N > mora count | heiban (fallback) |
| `null` | heiban (fallback) |

5. **Role letter given** → looked up in `RoleFromValue` (lowercased), defaulting to `'heiban'` if not found

## Pitch Resolution

After role is determined, `determinePitchTokyo()` (`section.js:41`) resolves the numeric pitch value used for level calculation:

| Condition | Pitch value |
|-----------|-------------|
| `allLow` is true (`~` modifier) | `-1` (all low) |
| Explicit pitch digit in accent (requires colon) | that digit (parsed to int) |
| Role is `heiban` or `setsubigo` | `0` |
| Role is `atamadaka` | `1` |
| Role is `nakadaka` or `kifuku` | `2` |
| Role is `odaka` | mora count |
| Role is `particle` | `null` (resolved later by `buildHighLow`) |
| Role is `empty` | `-1` |
| Fallback | `0` |

This means when only a role letter is given without a pitch number, the pitch is inferred from the role. For example, `:n` without a number defaults to pitch 2; `:o` defaults to the mora count.

## The `p` Prefix (Particle with Accent)

The `p` prefix in the accent string marks a token as a particle that still carries accent information. For example, `は:ph` means "this is the particle は, but give it heiban accent coloring."

When `is_particle` is set on a section:
- The `isParticle` getter returns `true`
- The CSS `classname` includes both `'particle'` and the actual role (e.g., `"particle heiban"`)
- Particle pronunciation correction applies (は→ワ, へ→エ — see Particle Pronunciation below)

## Special Prefixes on Morae

These prefixes appear **inside** the word/reading portion (before kana characters), not in the accent:

| Prefix | Constant | Description |
|--------|----------|-------------|
| `*` | `DEVOICED_PREFIX` | Devoiced mora — rendered with a dashed circle (single-char mora) or rounded rectangle (multi-char mora) around the kana |
| `\` | `LITERAL_PREFIX` | Literal — bypasses pronunciation normalization (long vowel merging like おう→オー from `EQUIVALENT_SOUNDS`) but is still converted to katakana via `toKatakana()`. Also prevents particle pronunciation correction (は→ワ, へ→エ) since the mora is marked `literal` |
| `^` | `HIGH_PREFIX` | High override — forces this mora to high pitch regardless of the accent pattern |

Up to 3 prefixes can be combined on a single mora (matched by `[\*\\\^]{1,3}` in the mora regex).

### Prefix movement into readings

`furiganaToReading()` (`parse.js:45`) moves `*` and `^` prefixes from before kanji brackets into the reading using:

```
/([\*\^]+)([^\[\]\*\^]*)\[/g  →  '$2[$1'
```

Note: `\` is **not** included in this regex, so `\` before a kanji bracket does not get moved into the reading.

```
*食[た]べる:k     →  reading becomes *た + べる
^高[たか]い:k     →  reading becomes ^たか + い
```

### Mora object shape

`splitToMoras()` (`parse.js:63`) returns an array of mora objects:

```js
{ text: 'カ', devoiced: false, literal: false, high: false }
```

## Multiple Pitch Accents

When a word has multiple possible pitch patterns, they are comma-separated **after the colon**:

```
時[とき]:1,2
```

`splitMultiplePitchNotations()` (`parse.js:132`) computes the Cartesian product of all alternatives across all tokens in a sequence. If multiple words have comma-separated accents, every combination is generated.

The parser renders the first combination as the default colored sentence, with all variations as separate graphs.

## Sentence Structure

### Whitespace-separated tokens

Tokens are split by `splitToSections()` (`parse.js:37`) on whitespace (spaces, tabs, ideographic spaces `\u3000`). Each token is either:
- A **content word** with `:accent` (has a colon)
- A **particle** without colon (inherits pitch from surrounding context)
- A **separator** (`|`, `,`, `、`, `「`, `」`, `;`, `-`)

```
日本[にほん]:2 に 行[い]く:k
```

Here `日本[にほん]:2` is accented, `に` is a particle (no colon), and `行[い]く:k` is accented.

### Fragment merging

Unaccented tokens before an accented token get merged into it. This handles compound words where kanji segments are written separately.

`mergeFragments()` (`parse.js:104`) collects pending tokens (no colon) into a buffer. When a colon-bearing token appears, it strips the accent portion from that token's text, joins all pending tokens + the text with spaces, and reattaches the accent:

```
考[かんが] え 方[かた]:n   →  merged to "考[かんが] え 方[かた]:n" as one section
```

Separators flush the pending buffer without merging (pending tokens are emitted individually, then the separator).

Tokens left in the pending buffer at the end are emitted individually (as particles).

### Sentence breaks

Input is split into sentences by `splitToSentences()` (`parse.js:33`) on `.` and `\n`:

```js
expr.split(/[.\n]+/).map(s => s.trim()).filter(Boolean)
```

Japanese/full-width punctuation `。`, `!`, `?`, `！`, `？` is handled during normalization: each character is kept in place and a `.` is appended after it (` X .`), which then triggers the sentence split. The original punctuation character remains as a visible token in its sentence.

### Ghost particle `-`

A trailing `-` represents a ghost particle mora (e.g., for odaka words where the particle is implied but not written). It appears on the graph as a circle without text, and is hidden in the colored sentence (it's in `SENT_HIDDEN`).

```
橋[はし]:2 -
```

The `-` adds one more mora to show the pitch drop after an odaka word.

`detachGhostParticle()` (`parse.js:41`) ensures trailing dashes are space-separated from the preceding word: `(-+)[\s\n.]*$` → ` $1`.

### Tape connector `;`

A semicolon between tokens creates a dashed line connecting them on the graph, showing pitch continuity across a boundary:

```
word1:h ; word2:a
```

The `;` token becomes a `Section` with `isTape === true`. In the graph, `shouldConnect()` returns `true` when the previous section is a tape, and the connecting line is drawn with `stroke-dasharray` (dashed).

### Separators

Defined as `SEPARATORS` (`parse.js:102`):

```js
const SEPARATORS = [';', '|', ',', '、', '-', '「', '」'];
```

Additional groupings control behavior:

```js
const SENT_HIDDEN = ['|', '-'];       // Hidden in colored sentence
const PITCH_BREAKS = ['|', '-', ',', '、'];  // Reset pitch tracking (lastLow)
```

| Character | Visible in sentence | Resets pitch | Graph behavior |
|-----------|-------------------|-------------|----------------|
| `;` | No (skipped) | No | Dashed connector line to next word |
| `\|` | No (`SENT_HIDDEN`) | Yes (`PITCH_BREAKS`) | Empty section, no circles |
| `,` | Yes | Yes (`PITCH_BREAKS`) | Empty section, no circles |
| `、` | Yes | Yes (`PITCH_BREAKS`) | Empty section, no circles |
| `-` | No (`SENT_HIDDEN`) | No (role is `'particle'`, not `'empty'`, so `PITCH_BREAKS` has no effect — behaves as a normal particle inheriting pitch from context) | Ghost particle circle (no text) |
| `「` | Yes | No (preserves `lastLow`) | Empty section, no circles |
| `」` | Yes | No (preserves `lastLow`) | Empty section, no circles |

**Key distinction**: `「」` are in `SEPARATORS` but **not** in `PITCH_BREAKS`. They become empty sections (zero morae → role `'empty'`), and `calcLastWordEndedLow()` preserves the previous `lastLow` state for empty sections not in `PITCH_BREAKS`. So quotation marks do **not** reset pitch tracking.

### Empty particle detection

`isEmptyParticle()` (`section.js:9`) tests `/^[|,、]$/` — these three characters get `'empty'` role directly in `determineRoleTokyo()`. Other separator characters (`「`, `」`, `;`) get `'empty'` role through the zero-morae check instead. Note: `-` is different — `filterKana()` keeps `-` (it's in the allowed character set `\-`), so it has 1 mora and gets `'particle'` role via the `sep == null` branch, not `'empty'`.

## Pitch Calculation (High/Low)

### buildHighLow()

`buildHighLow()` (`section.js:162`) walks left to right through sections, starting with `lastLow = true`. For each section:

- **Keihan sections**: levels are already set from the `levels` string; `lastLow` is updated based on the final level character
- **Tokyo sections**: levels are computed by `buildLevelsTokyo()`, then `^` (high) overrides are applied, then `lastLow` is updated

### buildLevelsTokyo()

(`section.js:143`) Assigns `H`/`L` to each mora based on pitch value and `lastLow`:

| Pitch value | First mora | Remaining morae |
|-------------|-----------|-----------------|
| `null` (unset) | Resolved to `-1` if `lastLow`, `-2` if not, then reprocessed |
| `-1` (all-low) | L | L |
| `-2` (all-high) | H | H |
| `1` (atamadaka) | H | All L |
| `0` (heiban) | L if `lastLow`, else H | All H |
| `N` (nakadaka/odaka) | L if `lastLow`, else H | H for morae 1..N-1, L for morae N+ |

The `null` pitch case handles particles: they inherit all-low or all-high from surrounding context.

### High override

After levels are computed, any mora with `high: true` (from the `^` prefix) has its level forced to `H`:

```js
if (section.moraes[i].high) section.levels[i] = H;
```

### Small tsu (っ/ッ) special case

In graph rendering (`graph.js:109`), small tsu at position 1 (second mora) after a low first mora stays low regardless of what `buildLevelsTokyo` calculated:

```js
if (mora.text === 'っ' || mora.text === 'ッ') {
  moraLevel = (j === 1 && section.levels[j - 1] === L) ? section.levels[j - 1] : section.levels[j];
}
```

### calcLastWordEndedLow()

(`section.js:155`) Determines `lastLow` for the next section:

| Condition | `lastLow` |
|-----------|-----------|
| Role is `'empty'` and word not in `PITCH_BREAKS` | Preserved (unchanged) |
| Pitch is `1` (atamadaka) | `true` |
| Pitch is `0` (heiban) or `-2` (all-high) | `false` |
| Otherwise | `true` if mora count >= pitch value |

## Furigana

Standard bracket notation, same as the old system but without pitch inside:

```
漢字[かんじ]
```

### Split furigana (front|back)

Brackets can contain pipe-separated readings for front/back card sides:

```
漢字[かん|かんじ]
```

Front side uses the text before `|`, back side uses after `|`.

- **Pitch parsing** (`normalizeForParsing`): strips to back part `[$2]`
- **Reading extraction** (`furiganaToReading`): also strips to back part `[$2]`
- **Sentence display** (`textToRuby` in `sentence.js`): uses the front part for the `<rt>` ruby text (with `data-split` attribute), or hides the ruby entirely if front is empty (`[|back]`)

### Digit-only brackets

Brackets containing only digits (e.g., `[3]`) are protected during normalization so they aren't treated as furigana. They're replaced with Unicode characters `⁅⁆` during processing and restored later in `textToRuby()`, where they render as `<span class="pitch-num">3</span>`.

## Pre-processing (normalizeForParsing)

`normalizeForParsing()` (`parse.js:18`) transforms raw field text before parsing, in this exact order:

| Step | Operation | Code |
|------|-----------|------|
| 1 | `<br>` tags → ` . ` (sentence break) | `/<br\s*\/?>/gi` → `' . '` |
| 2 | Strip all HTML tags | `/<[^<>]+>/gi` → `''` |
| 3 | Escape special brackets: `\ ` → `&nbsp;`, `\[`/`\]` → `⁅⁆`, space before `[reading]` → `&nbsp;⁅reading⁆`, `⁆ ` → `⁆&nbsp;` | `escapeBrackets()` |
| 4 | Protect digit-only brackets from furigana regex | `\[(\d+)\]` → `⁅digits⁆` |
| 5 | Strip split furigana to back reading | `\[front\|back\]` → `[back]` |
| 6 | `/` or `／` → ` ; ` (slash → tape connector) | `\s*[/／]\s*` → `' ; '` |
| 7 | Japanese punctuation: each `。!?！？` char is kept and a `.` appended | `([。!?！？])` → `' X .'` |
| 8 | Separators `「」\|、､` spaced out | `([「」\|、､])` → `' X '` |
| 9 | Non-final `,` spaced out | `([^ ]), ` → `' X , '` |

**Note on step 7**: The original punctuation character is preserved as a visible token in the sentence. The appended `.` triggers the sentence split in `splitToSentences()`. For example, `。` becomes ` 。 .` — the `。` stays visible, and the `.` acts as the boundary.

**Note on step 8**: `､` (half-width Japanese comma) is included alongside `、` (full-width).

## Kana Handling

### Mora splitting

Morae are split by `kanaToMoraes()` (`parse.js:59`) using:

```js
/(?:[\*\\\^]{1,3})?.[ァィゥェォャュョぁぃぅぇぉゃゅょ]?/g
```

- Optional prefix markers (`*`, `\`, `^`, up to 3) attach to the following mora
- Any single character (`.`) is the main kana
- Optional small kana (`ァィゥェォャュョぁぃぅぇぉゃゅょ`) combines with the preceding character into one mora

Before mora splitting, `filterKana()` (`parse.js:55`) strips everything except hiragana, katakana, the prefix markers `*`, `\`, `^`, and the ghost particle character `-`.

### Reading conversion (adjustKana)

`adjustKana()` (`section.js:54`) applies kana conversion based on the `convert_reading` config:

- **`'katakana'`** (default):
  1. Extract and protect `\`-prefixed characters (literal markers)
  2. Strip `*` devoicing markers, tracking their positions
  3. Apply pronunciation normalization via `literalPronunciation()` (converts to katakana + normalizes long vowels like おう→オー, えい→エー, etc. — see `EQUIVALENT_SOUNDS` in `kana.js`)
  4. Restore devoicing markers at their original positions
  5. Restore literal characters as katakana (bypassing normalization)
- **`'hiragana'`** — convert all katakana to hiragana (no pronunciation normalization)
- **(default/unset)** — keep as-is

### Particle pronunciation

Single-mora particles get pronunciation correction in the `moraes` getter (`section.js:114`). This only applies when:
- The section's role is `'particle'` OR `isParticle` is true (from `p` prefix)
- The section has exactly 1 mora
- The mora is not marked as `literal` (no `\` prefix)

The correction checks the **post-conversion** text (katakana by default):

| Before | After | Note |
|--------|-------|------|
| ハ | ワ | Particle は pronounced as "wa" |
| ヘ | エ | Particle へ pronounced as "e" |

**Important**: This operates on the already-converted kana. With the default `convert_reading: 'katakana'`, は has already been converted to ハ before this check runs. If `convert_reading` were set to `'hiragana'` or left as-is, the check for `ハ`/`ヘ` would not match hiragana `は`/`へ`, and the correction would not fire.

## Section Class

`Section` (`section.js:87`) wraps a raw token string and provides computed properties:

| Property | Description |
|----------|-------------|
| `raw` | Original token string |
| `word` | Word text with prefix markers (`*`, `\`, `^`) stripped |
| `moraes` | Array of mora objects (with particle pronunciation applied) |
| `role` | Resolved role name string |
| `classname` | CSS class(es) — role name, or `"particle <role>"` if `isParticle` |
| `pitch` | Resolved numeric pitch value (get/set) |
| `levels` | Array of `'h'`/`'l'` per mora (get/set) |
| `isKeihan` | Whether this section uses Keihan accent |
| `isTape` | Whether this section is a `;` tape connector |
| `isParticle` | Whether the `p` prefix was used in the accent |

## Graph Rendering

`makeGraph()` (`graph.js:80`) converts a sequence of `Section` objects into an SVG pitch graph:

1. `filterEmptyMoraes()` removes sections with no morae (unless they're pitch breaks or tapes)
2. Iterates through sections, skipping `'empty'` roles and tape connectors
3. For each section's morae: places circles at high/low Y positions, draws path lines between them
4. Connector lines link adjacent sections (dashed if previous was tape)
5. Ghost particle morae (`-`) get circles but no text
6. Devoiced morae get an additional dashed circle (single-char) or rounded rectangle (multi-char)
7. If `config.no_text` is `true`, kana text below circles is omitted and SVG height is reduced

## Sentence Rendering

`makeColoredSentence()` (`sentence.js:30`) produces colored HTML:

1. Skips sections in `SENT_HIDDEN` (`|` and `-`), dash-only words, and tape sections
2. Each visible section becomes `<span class="<classname>">...</span>`
3. `wordToRuby()` strips devoicing/literal prefixes and converts bracketed readings to `<ruby>` annotations

`textToRuby()` (`sentence.js:1`) handles:
- Split furigana `[front|back]` → uses front part as `<rt data-split>`, or hides ruby if front is empty
- Readings containing kana or letters → `<ruby>` with `<rt>`
- Digit-only brackets → `<span class="pitch-num">`
- Non-reading brackets (restored from `⁅⁆`) → passed through

## Config

All config values (from `config.js`):

```js
const config = {
  no_text: false,               // Graph without kana text below
  size_unit: 25,                // Base unit for graph dimensions
  font_size: 24,                // Kana text font size (px)
  text_dx: -12,                 // Kana text horizontal offset
  x_step: 50,                   // Horizontal distance between morae
  circle_radius: 5.25,          // Pitch circle radius
  devoiced_circle_width: 1.5,   // Devoiced marker stroke width
  devoiced_circle_radius: 17,   // Devoiced marker radius
  devoiced_stroke_disarray: "2 3", // Devoiced marker dash pattern
  devoiced_rectangle_padding: 5,   // Devoiced rectangle padding (multi-char)
  stroke_width: 2.5,            // Line stroke width
  graph_height: 40,             // Vertical distance between high and low
  graph_visible_height: 100,    // Rendered SVG height (px)
  graph_horizontal_padding: 6,  // Left/right padding
  graph_font: 'Hiragino Mincho ProN, Yu Mincho, Noto Serif CJK JP, serif',
  convert_reading: 'katakana',  // Reading display mode
  stroke_dasharray: '4',        // Tape connector dash pattern
};
```

## Real Examples

### Target word field

```
日本[にほん]:2                    // nakadaka, drop after mora 2
時[とき]:1,2                     // two possible accents
あう:0,1                         // all-kana, two accents
食[た]べる:k                     // kifuku verb (defaults to pitch 2)
アニメ:0                         // katakana heiban
考[かんが]え 方[かた]:n           // compound nakadaka (merged fragments)
```

### Sentence field

```
日本[にほん]:2 に 行[い]く:k たいです。
今日[きょう]:1 は いい 天気[てんき]:1 ですね。
考[かんが]え 方[かた]:n を 変[か]える:k
お 母[かあ]さん:n は 元気[げんき]:1 です
```

### With special features

```
*す*き:a                          // devoiced す and き
橋[はし]:2 -                      // ghost particle showing pitch drop
食[た]べる:k ; 物[もの]:h         // tape connecting verb to noun
\き:a                             // literal き (bypasses pronunciation normalization, still converted to katakana)
大阪[おおさか]:H:hlhh             // Keihan accent with explicit levels
^高[たか]い:0~                    // high override on first mora, all-low
は:ph                             // particle with explicit heiban accent
```

### Comparison: old → new

| Old (semicolon-inside) | New (colon-outside) |
|------------------------|---------------------|
| `日本[にほん;2]` | `日本[にほん]:2` |
| `時[とき;1,2]` | `時[とき]:1,2` |
| `あう[0,1]` | `あう:0,1` |
| `食[た;k]べる` | `食[た]べる:k` |
| `アニメ[0]` | `アニメ:0` |
| `考え方[かんがえかた;5,0]` | `考[かんが]え方[かた]:5,0` |
| `日本[にほん;2] に 行[い;k]く` | `日本[にほん]:2 に 行[い]く:k` |
| `考[かんが;n]え 方[かた;n]` | `考[かんが]え 方[かた]:n` |
