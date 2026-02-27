# Anki Addon: Old-to-New Pitch Syntax Converter

## Design Document

This document specifies how to build an Anki addon that batch-converts note fields from the old MvJ semicolon-inside-brackets pitch syntax to the new colon-outside-brackets pitch-graphs syntax. It is self-contained — all conversion rules are included here.

---

## 1. Overview

### Old syntax (semicolon inside brackets)
Pitch data lives **inside** furigana brackets after a semicolon:
```
日本[にほん;2]          — kanji word
あう[0,1]               — kana-only word (pitch-only bracket)
食[た;k2]べる           — verb with okurigana
```

### New syntax (colon outside brackets)
Pitch data lives **after** the word, outside brackets, after a colon:
```
日本[にほん]:2           — kanji word
あう:0,1                 — kana-only word
食[た]べる:k2            — verb with okurigana
```

### What the addon does
1. Scans all notes of the 🇯🇵 MvJ note type
2. Converts the **Word** and **Sentence** fields from old → new syntax
3. Provides a dry-run preview before committing
4. Logs any notes that couldn't be cleanly converted for manual review

---

## 2. Conversion Rules — Word Field

The Word field contains a single word (possibly compound) with pitch accent data.

### 2.1 Simple kanji word: `kanji[reading;pitch]`

Move pitch from inside brackets to after a colon.

| Old | New |
|-----|-----|
| `日本[にほん;2]` | `日本[にほん]:2` |
| `時[とき;1,2]` | `時[とき]:1,2` |

**Rule**: Find bracket content containing `;`. Split on the *first* `;` → left part is reading, right part is pitch. Reconstruct as `kanji[reading]:pitch`.

### 2.2 Kana-only word: `kana[pitch]`

When the word is all kana (hiragana or katakana), the bracket contains only pitch data (no reading, no semicolon). Remove the brackets and put pitch after a colon.

| Old | New |
|-----|-----|
| `あう[0,1]` | `あう:0,1` |
| `かわいい[3]` | `かわいい:3` |
| `アニメ[0]` | `アニメ:0` |

**Detection**: Bracket content matches `/^[0-9,hkaonb~+p*\-]+$/` (digits, commas, hyphens, and pitch modifier characters — no kana). The word before the bracket is all kana.

**Rule**: Strip brackets, append `:pitch`.

### 2.3 Kanji word with okurigana: `kanji[reading;pitch]okurigana`

Okurigana (trailing kana) sits outside the brackets in both old and new syntax. The pitch just needs to move from inside the bracket to after the entire word+okurigana.

| Old | New |
|-----|-----|
| `食[た;k2]べる` | `食[た]べる:k2` |
| `走[はし;h]る` | `走[はし]る:h` |
| `行[い;h,k]く` | `行[い]く:h,k` |
| `考[かんが;k2]える` | `考[かんが]える:k2` |

**Rule**: Extract pitch from inside brackets. Remove the `;pitch` from the bracket content. Append `:pitch` after the trailing okurigana (end of the full token).

### 2.4 No pitch data: `kanji[reading]`

Brackets containing only a kana reading (no semicolon, no pitch characters) have no pitch to convert.

| Old | New |
|-----|-----|
| `食[た]べる` | `食[た]べる` (no change) |

**Rule**: Leave unchanged.

### 2.5 Multiple readings: `kanji[reading1;pitch1,reading2;pitch2,...]`

The old syntax supports multiple alternative readings with per-reading pitches inside one bracket pair. The comma after a pitch value followed by kana starts a new reading.

| Old | New |
|-----|-----|
| `心中[しんじゅう;0,しんちゅう;1,0]` | `心中[しんじゅう]:0` (**flag for review**) |
| `被[かぶ;2,こうむ;3]る` | `被[かぶ]る:2` (**flag for review**) |

The new syntax has no equivalent for per-reading pitch alternatives in a single token. The comma-separated notation in new syntax means multiple pitches for the **same** reading (e.g., `時[とき]:1,2` means とき can be pitch 1 or 2).

**Rule**: Use the **first** reading and its pitch(es). Flag the note for manual review so the user can decide how to handle the alternate reading. Include the original text in the log.

**Parsing multiple readings**: Split bracket content on `;` to get segments. The first segment is always reading1. For subsequent segments, split on `,` and classify each part: if it starts with kana → it begins a new reading; if it starts with a digit or pitch letter → it's another pitch value for the current reading.

Example parse of `しんじゅう;0,しんちゅう;1,0`:
1. Split on `;` → `["しんじゅう", "0,しんちゅう", "1,0"]`
2. Segment 0: reading1 = `しんじゅう`
3. Segment 1: split on `,` → `["0", "しんちゅう"]` → pitch1=`0`, reading2 starts at `しんちゅう`
4. Segment 2: split on `,` → `["1", "0"]` → all digits → pitch2=`1,0`
5. Result: reading1=しんじゅう pitch=0, reading2=しんちゅう pitch=1,0

### 2.6 Collapsed compound words: `compound[combinedReading;pitch]`

This is the hardest conversion. The old addon collapses multi-kanji compounds into a single bracket pair. The new syntax needs per-kanji furigana brackets with the pitch on the last segment.

| Old | New |
|-----|-----|
| `考え方[かんがえかた;5,0]` | `考[かんが]え 方[かた]:5,0` |
| `一石[いっせき;2]` | `一石[いっせき]:2` (consecutive kanji — see §5) |
| `取り替[とりか;3,0]え` | `取[と]り 替[か]え:3,0` |

**Rule**: Use the furigana distribution algorithm (§5) to split the combined reading back into per-kanji segments. Place `:pitch` after the last segment (including any trailing okurigana).

### 2.7 Nakaten compound pitch: `word[reading・with・dots;N-N]`

Nakaten (`・`) in the reading separates segments, and hyphens in the pitch correspond 1:1 with those segments.

| Old | New |
|-----|-----|
| `十人十色[じゅうにん・といろ;1-1]` | `十人十色[じゅうにんといろ]:1` (**flag for review**) |

The new syntax has no equivalent for compound pitch with hyphens. The hyphenated pitch `1-1` means "first segment is pitch 1, second segment is pitch 1."

**Rule**: Use the nakaten positions to split both reading and pitch into corresponding segments. The `・` delimiters in the reading and `-` delimiters in the pitch align 1:1, giving us natural split points. Apply the furigana distribution algorithm to each reading segment independently against the word text to produce separate accented sections (e.g., `十人[じゅうにん]:1 十色[といろ]:1`). If the word is all-kanji and the segments can't be distributed, fall back to keeping the combined bracket with the **last** pitch value. Flag for manual review in all cases.

### 2.8 Pitch value mapping

Pitch values transfer directly — both systems use the same notation:

| Value | Meaning | Conversion |
|-------|---------|-----------|
| `0` | Heiban | No change |
| `1` | Atamadaka | No change |
| `2`, `3`, ... `N` | Nakadaka/Odaka | No change |
| `h` | Heiban (verbs) | No change |
| `k` | Kifuku (verbs, sentence) | No change |
| `kN` (e.g., `k2`) | Kifuku with pitch N | No change |
| `h,k` or `k,h` | Both readings | No change (new system treats as alternatives) |

### 2.9 Special modifier mapping

These only appear in user-override data, not auto-generated. They're rare but must be handled:

| Old | New | Notes |
|-----|-----|-------|
| `0b`, `2b` | `:b0`, `:b2` | `b` was a suffix/prefix modifier → becomes `b` role letter with pitch digit |
| `b2` | `:b2` | Same — role `b`, pitch `2` |
| `~0`, `0~` | `:0~` or `:~0` | All-low modifier, both positions work in new syntax |
| `2+` | `:2` + trailing ` -` | `+` meant extra particle mora → becomes ghost particle `-` |
| `p`, `p0` | `:p`, `:ph` | Particle marker → `p` prefix in new accent |
| `p1` | `:pa` | Particle with atamadaka |
| `ph` | `:ph` | Particle with heiban |
| `pb` | `:pb` | Particle with black/neutral coloring |
| `*き` in reading | `*き` in reading | Devoiced mora — no change needed, same prefix in both systems |

---

## 3. Conversion Rules — Sentence Field

The Sentence field contains a full sentence with multiple tokens, each potentially carrying pitch.

### 3.1 Simple pitched words in sentences

Same as word field §2.1–§2.3: move pitch from inside brackets to after colon.

```
日本[にほん;2] → 日本[にほん]:2
食[た;k]べた   → 食[た]べた:k
```

### 3.2 Compound words in sentences (letter-coded brackets)

In old sentence syntax, compound words have **every** bracket tagged with a letter code (`h`/`a`/`n`/`k`). In new syntax, only the **last** segment gets the accent (via colon), and preceding unaccented segments are merged by the parser's fragment merging.

| Old | New |
|-----|-----|
| `考[かんが;n]え 方[かた;n]` | `考[かんが]え 方[かた]:n` |
| `お[n] 母[かあ;n]さん` | `お 母[かあ]さん:n` |

**Rule**: Identify runs of consecutive tokens where **all** brackets carry the **same** pitch letter code. Strip the pitch from all brackets except the last one in the run, and place the code after a colon on the last token.

**Detection of compound runs**: Walk tokens left to right. A token belongs to the current compound group if:
- Its bracket contains `;` followed by a single letter (`h`, `a`, `n`, `k`) matching the group's letter
- OR it's a pitch-only bracket (e.g., `[n]`, `[h]`) on a bare kana token with the same letter
The run ends when a token has a different pitch letter, a numeric pitch, no pitch, or is a particle/punctuation.

**Known limitation — false positives with `h`/`k`**: The letters `h` and `k` are used both for sentence compounds and for inflected verbs/adjectives (§3.3). Two adjacent verbs that happen to share the same letter (e.g., `食[た;k]べ 終[お;k]わった`) would be falsely grouped as a compound, producing `食[た]べ 終[お]わった:k` instead of the correct `食[た]べ:k 終[お]わった:k`. In practice this is rare (adjacent verbs usually have a particle between them), but the implementation should add a heuristic: only group `h`/`k` tokens when their structure looks like a compound (e.g., no token in the group has okurigana after its bracket, or the group contains a mix of kanji-bracket and kana-only tokens). The letters `a` and `n` are safe to group unconditionally since they're only used for compounds in sentence notation.

### 3.3 Inflected verbs/adjectives in sentences

Old sentence syntax uses simplified `h`/`k` notation (the original pitch number is lost).

| Old | New |
|-----|-----|
| `食[た;k]べた` | `食[た]べた:k` |
| `走[はし;h]って` | `走[はし]って:h` |

**Rule**: Same as §2.3 — extract pitch letter, remove from bracket, append after colon. Note: old `k` maps to new `k` which defaults to pitch 2 in the new renderer. This is acceptable since the original pitch number was already lost in the old system's simplification.

### 3.4 Particles between accented words

Old syntax: particles are bare text (no brackets, no pitch).
New syntax: particles between two accented words need an explicit `:p` (or just `:`) to prevent fragment merging from swallowing them into the next accented word. Trailing particles (after the last accented word) are fine without colons.

| Old | New |
|-----|-----|
| `日本[にほん;2] に 行[い;k]く` | `日本[にほん]:2 に:p 行[い]く:k` |
| `天気[てんき;1] ですね。` | `天気[てんき]:1 ですね。` (trailing — no colon needed) |

**Rule**: After converting all pitched tokens, scan for bare tokens (no brackets, no colon) that sit **between** two colon-bearing tokens. Add `:p` to each such bare token.

**Important nuances**:
- Only add `:p` to tokens **between** two accented words. Trailing particles (after the last accented word in the sentence) should stay bare — they naturally become particle sections in the new parser.
- Plain kana that runs together in old syntax (e.g., `たいです`) should remain as one token. Don't split or add colons to fused auxiliary chains.
- Punctuation (`。`, `！`, `？`, `、`) should not get `:p`.

### 3.5 Sentence spacing

Old syntax has specific spacing rules where plain-kana tokens sometimes run together. The new syntax is more uniform (whitespace-separated). The converter should preserve existing spacing as-is — the new parser handles it correctly through fragment merging.

---

## 4. Token Parsing

### 4.1 Tokenizing a field value

Split the field text into tokens by whitespace (spaces). Each token is one of:

1. **Bracketed token**: contains `[...]` — may have kanji before, reading/pitch inside, okurigana after
2. **Bare token**: no brackets — plain kana, particle, or punctuation

### 4.2 Classifying bracket content

Given a bracket's inner content (between `[` and `]`):

```python
def classify_bracket(content: str) -> str:
    """Returns 'reading_and_pitch', 'pitch_only', 'reading_only', or 'already_new'."""
    if ':' in content:
        return 'already_new'  # shouldn't happen in old data
    if ';' in content:
        return 'reading_and_pitch'
    if re.match(r'^[0-9,hkaonb~+p*\-]+$', content):
        return 'pitch_only'
    return 'reading_only'
```

### 4.3 Detecting already-converted tokens

A token is already in new syntax if it contains `:` **outside** brackets. Skip these tokens. This allows the converter to be run multiple times safely (idempotent).

Detection: After removing all `[...]` segments from the token, check if the remainder contains `:`.

### 4.4 Full token regex

A single regex can decompose an old-syntax token:

```python
OLD_TOKEN_RE = re.compile(
    r'^'
    r'(?P<pre>[^\[\]]*?)'        # text before bracket (kanji, kana, or empty)
    r'(?:\[(?P<bracket>[^\]]+)\])?' # bracket content (optional)
    r'(?P<post>[^\[\]:]*)'       # text after bracket (okurigana)
    r'$'
)
```

But compound words (with okurigana between kanji groups) may have multiple bracket pairs in a single token — this only happens in old sentence syntax. For word field tokens, there's always exactly one bracket pair. Sentence tokens can have multiple.

For sentence tokens with multiple brackets, process them as a group (see §3.2).

---

## 5. Furigana Distribution Algorithm (Compound Word Splitting)

When the old word field has a collapsed compound like `考え方[かんがえかた;5,0]`, we need to split the reading across kanji segments to produce `考[かんが]え 方[かた]:5,0`.

### 5.1 Algorithm

```
distribute_furigana(word: str, reading: str) → list of segments

Input:
  word = "考え方"
  reading = "かんがえかた"

Output:
  [("kanji", "考", "かんが"), ("kana", "え"), ("kanji", "方", "かた")]
```

Steps:
1. Walk through the word character by character
2. Group consecutive kanji into kanji-runs, consecutive kana into kana-runs
3. Kana-runs in the word are okurigana — they must appear literally in the reading at the corresponding position. Use them as anchor points.
4. Everything in the reading between kana anchors maps to the adjacent kanji-run.

```python
import unicodedata

def is_kanji(ch):
    return unicodedata.category(ch) == 'Lo' and (
        '\u4e00' <= ch <= '\u9fff' or   # CJK Unified
        '\u3400' <= ch <= '\u4dbf' or   # CJK Extension A
        ch == '々'                       # kanji repeat mark
    )

def is_kana(ch):
    return ('\u3040' <= ch <= '\u309f' or  # hiragana
            '\u30a0' <= ch <= '\u30ff')     # katakana

def distribute_furigana(word, reading):
    # Split word into alternating kanji/kana segments
    segments = []
    i = 0
    while i < len(word):
        if is_kanji(word[i]):
            run = ''
            while i < len(word) and is_kanji(word[i]):
                run += word[i]
                i += 1
            segments.append(('kanji', run))
        else:
            run = ''
            while i < len(word) and not is_kanji(word[i]):
                run += word[i]
                i += 1
            segments.append(('kana', run))

    # Match segments against reading
    result = []
    r_pos = 0
    for idx, (seg_type, seg_text) in enumerate(segments):
        if seg_type == 'kana':
            # This kana should appear in the reading — advance past it
            kana_len = len(seg_text)
            # Verify match (katakana/hiragana normalization may be needed)
            r_pos += kana_len
            result.append(('kana', seg_text))
        else:
            # Kanji segment — consume reading up to the next kana anchor
            # Find the next kana segment in the word (if any)
            next_kana = None
            for future_type, future_text in segments[idx + 1:]:
                if future_type == 'kana':
                    next_kana = future_text
                    break

            if next_kana is not None:
                # Find where next_kana appears in remaining reading
                anchor_pos = reading.find(next_kana, r_pos)
                if anchor_pos == -1:
                    # Fallback: can't split, return None
                    return None
                kanji_reading = reading[r_pos:anchor_pos]
                r_pos = anchor_pos
            else:
                # Last segment — consume all remaining reading
                kanji_reading = reading[r_pos:]
                r_pos = len(reading)

            result.append(('kanji', seg_text, kanji_reading))

    return result
```

### 5.2 Reconstructing new syntax from segments

```python
def segments_to_new_syntax(segments, pitch, okurigana=''):
    """Convert distributed segments to new colon notation.

    `okurigana` is any trailing kana that was outside the original bracket
    (e.g., the え in 取り替[とりか;3,0]え). It is appended after the last
    segment and before :pitch.
    """
    parts = []
    for seg in segments:
        if seg[0] == 'kana':
            parts.append(seg[1])
        else:  # kanji
            kanji, reading = seg[1], seg[2]
            parts.append(f'{kanji}[{reading}]')
    return ' '.join(parts) + okurigana + f':{pitch}'
```

Result: `考[かんが] え 方[かた]:5,0`

Note: the spaces between all parts (including kana segments like `え`) are fine — the new parser's fragment merging collects all unaccented tokens before the colon-bearing token and merges them into a single section. `考[かんが] え 方[かた]:5,0` parses identically to `考[かんが]え 方[かた]:5,0`.

### 5.3 Consecutive kanji (no kana anchors)

When a compound is all kanji (e.g., `一石[いっせき;2]`), there are no kana anchors to split on. The algorithm cannot determine where to split the reading between kanji characters.

**Fallback**: Keep the combined bracket as-is and just move the pitch:
```
一石[いっせき;2] → 一石[いっせき]:2
```

This is visually acceptable (furigana spans the whole kanji group) and semantically correct for the pitch graph. Flag the note only if the compound has more than 2 kanji characters, as those may benefit from manual splitting.

### 5.4 Ambiguous kana anchors

If a kana character appears multiple times in the reading, the `find()` call may match the wrong position. Example: `送り届け` (おくりとどけ) — the `り` in the word could match at position 2 (correct) or potentially elsewhere.

In practice this is rare because:
- `find(kana, r_pos)` searches forward from the current position, which is almost always correct
- Japanese okurigana follows predictable patterns

If the split produces a kanji segment with an empty reading (0 characters), that's a signal the match was wrong. In that case, fall back to keeping the combined bracket and flagging for review.

---

## 6. Sentence-Specific Processing

### 6.1 Processing pipeline for sentence fields

```
1. Split sentence text on whitespace → tokens
2. For each token, classify it (bracketed with pitch, bracketed without pitch, bare)
3. Identify compound groups (consecutive tokens sharing the same pitch letter)
4. Convert each token/group:
   a. Compound group → strip pitch from all but last, add :letter to last
   b. Single pitched token → move pitch from bracket to colon
   c. Bare token → leave as-is for now
5. Add :p to bare tokens between two accented tokens
6. Rejoin with spaces
```

### 6.2 Compound group detection

```python
def get_pitch_letter(token):
    """Extract pitch letter from an old-syntax token, or None."""
    # Check for bracket with ;letter
    m = re.search(r'\[([^\]]*);([hankHANK])\]', token)
    if m:
        return m.group(2).lower()
    # Check for pitch-only bracket with single letter
    m = re.search(r'\[([hank])\]', token)
    if m:
        return m.group(1)
    return None

def group_compound_tokens(tokens):
    """Group consecutive tokens sharing the same pitch letter."""
    groups = []
    current_group = []
    current_letter = None

    for token in tokens:
        letter = get_pitch_letter(token)
        if letter is not None and letter == current_letter:
            current_group.append(token)
        else:
            if current_group:
                groups.append(('compound' if len(current_group) > 1 else 'single',
                              current_letter, current_group))
            if letter is not None:
                current_group = [token]
                current_letter = letter
            else:
                groups.append(('bare', None, [token]))
                current_group = []
                current_letter = None

    if current_group:
        groups.append(('compound' if len(current_group) > 1 else 'single',
                      current_letter, current_group))

    return groups
```

### 6.3 Adding `:p` to interstitial particles

After all pitched tokens have been converted (they now have `:`), scan for bare tokens between two colon-bearing tokens:

```python
def add_particle_colons(tokens):
    """Add :p to bare tokens sitting between two accented tokens."""
    result = list(tokens)

    for i in range(len(result)):
        if ':' in result[i]:
            continue  # already accented
        if _is_punctuation(result[i]):
            continue  # don't add :p to punctuation

        # Look for accented token before and after
        has_before = any(':' in result[j] for j in range(i - 1, -1, -1)
                        if not _is_punctuation(result[j]))
        has_after = any(':' in result[j] for j in range(i + 1, len(result))
                       if not _is_punctuation(result[j]))

        if has_before and has_after:
            result[i] = result[i] + ':p'

    return result

def _is_punctuation(token):
    return token.strip() in ('。', '、', '！', '？', '!', '?', '…', '「', '」')
```

**Important**: The "has_before" and "has_after" checks must stop at sentence punctuation boundaries (`。`, `！`, `？`). A particle after `。` is not between two accented words — it's at the start of a new clause. The implementation should split the token list on sentence-ending punctuation first, then process each clause independently before reassembling.

---

## 7. Edge Cases & Lossy Conversions

These cases lose information or have no clean equivalent. Flag all of them for manual review.

| Case | What's lost | Handling |
|------|-------------|----------|
| Multiple readings (`心中[しんじゅう;0,しんちゅう;1,0]`) | Alternate readings and their pitches | Use first reading only |
| Nakaten compound pitch (`1-1`) | Per-segment pitch values | Use last pitch value; attempt to split into separate sections |
| Sentence `n` (catch-all for 2+) | Odaka words are lumped into `n` | Keep as `n` — new system's `n` defaults to pitch 2, may not match original |
| Sentence `k` (simplified) | Original pitch number lost | Keep as `k` — new system defaults to pitch 2 |
| `+` modifier (extra particle) | Explicit extra mora | Convert to ghost particle ` -` after the word |
| Consecutive kanji compounds | Can't split reading per-kanji | Keep combined bracket, move pitch to colon |

---

## 8. Addon Architecture

### 8.1 File structure

Add a new module to the existing addon:

```
addon/
  __init__.py          (existing — add menu entry for converter)
  settings_dialog.py   (existing)
  notetype.py          (existing)
  converter.py         (NEW — all conversion logic)
  converter_ui.py      (NEW — dialog for running the converter)
```

### 8.2 Integration with existing addon

The existing addon already has a pattern for batch operations (see `_convert_sound_to_audio` in `settings_dialog.py`). The pitch converter should follow the same pattern:

1. Add a button to the settings dialog: **"Convert old pitch syntax → new"**
2. Clicking it opens a dedicated `ConverterDialog` with options and preview
3. The actual conversion runs in `mw.taskman.run_in_background` with progress updates

### 8.3 `converter.py` — Core conversion module

```python
# Public API

def convert_word_field(text: str) -> tuple[str, list[str]]:
    """Convert a Word field value from old to new syntax.

    Returns (converted_text, warnings).
    Warnings list is non-empty if any lossy conversions occurred.
    """

def convert_sentence_field(text: str) -> tuple[str, list[str]]:
    """Convert a Sentence field value from old to new syntax.

    Returns (converted_text, warnings).
    """

def is_old_syntax(text: str) -> bool:
    """Check if text contains old-style pitch notation."""

def is_already_new_syntax(text: str) -> bool:
    """Check if text already uses new-style colon notation."""
```

Key internal functions:
```python
def _parse_bracket_content(content: str) -> dict:
    """Parse bracket content into {readings: [{reading, pitches}], type}."""

def _distribute_furigana(word: str, reading: str) -> list | None:
    """Split combined reading across kanji. Returns None if ambiguous."""

def _convert_word_token(token: str) -> tuple[str, list[str]]:
    """Convert a single word-field token."""

def _convert_sentence_tokens(tokens: list[str]) -> tuple[list[str], list[str]]:
    """Convert sentence tokens, handling compounds and particles."""

def _detect_compound_groups(tokens: list[str]) -> list:
    """Identify compound word groups by shared pitch letter."""

def _add_particle_colons(tokens: list[str]) -> list[str]:
    """Add :p to bare particles between accented words."""
```

### 8.4 `converter_ui.py` — Converter dialog

A `QDialog` with:

1. **Scope selector**: Radio buttons for "All notes" / "Selected notes" / "Current deck"
2. **Field checkboxes**: Which fields to convert (Word, Sentence — checked by default). Each tagged as word-type or sentence-type conversion.
3. **Dry run button**: Scans notes and shows a preview table:
   - Note ID, field name, original text, converted text, warnings
   - Rows with warnings highlighted in yellow
   - Rows with no changes grayed out
4. **Convert button**: Applies changes with undo support
5. **Stats summary**: "N notes scanned, M converted, K flagged for review"

### 8.5 Undo support

Use Anki's custom undo:
```python
pos = mw.col.add_custom_undo_entry(
    f"Convert pitch syntax in {count} notes"
)
mw.col.update_notes(modified_notes)
mw.col.merge_undo_entries(pos)
```

### 8.6 Safety

- **Idempotent**: Running the converter twice produces the same result. Already-converted tokens (detected by `:` outside brackets) are skipped.
- **Non-destructive fields**: Only modify Word and Sentence fields. Never touch Definition, Audio, or other fields.
- **Preview before commit**: Dry-run is prominently featured; the Convert button is disabled until a dry run has been done.
- **HTML preservation**: The converter must preserve any HTML tags in the field (e.g., `<br>`, `<b>`, `<div>`). Parse pitch tokens only from the text content, not from HTML attribute values. Strategy: extract text segments between HTML tags, convert each independently, reassemble.

---

## 9. Detailed Regex Reference

### 9.1 Detect old-syntax bracket (has semicolon + pitch)

```python
# Matches: 日本[にほん;2], 食[た;k2], 心中[しんじゅう;0,しんちゅう;1,0]
OLD_PITCHED_BRACKET = re.compile(r'\[[^\]]*;[^\]]*\]')
```

### 9.2 Detect pitch-only bracket (kana word)

```python
# Matches: [0], [0,1], [3], [h], [k2], [h,k]
PITCH_ONLY_BRACKET = re.compile(r'\[([0-9hkaonb~+p*,\-]+)\]')
```

Note: Must verify the **word** before the bracket is all kana (no kanji). Otherwise `何[3]` (kanji with a digit bracket) might be misclassified — but in practice this doesn't occur because kanji words always have kana readings in brackets.

### 9.3 Detect new-syntax (colon outside brackets)

```python
# Has colon that's not inside brackets
NEW_SYNTAX = re.compile(r'(?:\][^\[]*|^[^\[]*):')
```

### 9.4 Full word-field token pattern

```python
# Captures: (before_bracket)(bracket_content)(after_bracket_okurigana)
WORD_TOKEN = re.compile(
    r'^(?P<head>[^\[\]]*?)'          # kanji/kana before bracket
    r'\[(?P<content>[^\]]+)\]'       # bracket content
    r'(?P<tail>[^\[\]:]*)$'          # okurigana after bracket
)
```

### 9.5 Sentence bracket with pitch letter

```python
# Matches brackets with ;letter at the end: [かんが;n], [n], [かた;n]
SENTENCE_PITCH_LETTER = re.compile(
    r'\[(?:([^\];]*);)?([hank])\]'
    # group 1: optional reading, group 2: pitch letter
)
```

---

## 10. Testing Strategy

### 10.1 Unit tests for `converter.py`

Test each conversion rule with explicit input → output pairs:

```python
# §2.1 Simple kanji word
assert convert_word("日本[にほん;2]") == "日本[にほん]:2"
assert convert_word("時[とき;1,2]") == "時[とき]:1,2"

# §2.2 Kana-only word
assert convert_word("あう[0,1]") == "あう:0,1"
assert convert_word("アニメ[0]") == "アニメ:0"

# §2.3 Okurigana
assert convert_word("食[た;k2]べる") == "食[た]べる:k2"
assert convert_word("走[はし;h]る") == "走[はし]る:h"

# §2.4 No pitch data
assert convert_word("食[た]べる") == "食[た]べる"

# §2.6 Compound splitting
assert convert_word("考え方[かんがえかた;5,0]") == "考[かんが]え 方[かた]:5,0"
assert convert_word("取り替[とりか;3,0]え") == "取[と]り 替[か]え:3,0"

# §2.6 Consecutive kanji (no split possible)
assert convert_word("一石[いっせき;2]") == "一石[いっせき]:2"

# §3.2 Sentence compounds
assert convert_sentence("考[かんが;n]え 方[かた;n]") == "考[かんが]え 方[かた]:n"

# §3.4 Particles
assert convert_sentence("日本[にほん;2] に 行[い;k]く") == \
    "日本[にほん]:2 に:p 行[い]く:k"

# Trailing particles don't get :p
assert convert_sentence("天気[てんき;1] ですね") == "天気[てんき]:1 ですね"

# Idempotent
assert convert_word("日本[にほん]:2") == "日本[にほん]:2"
```

### 10.2 Integration test with real Anki notes

Use the `mw.col.find_notes()` API to find notes, convert them in dry-run mode, and verify the output against expected values. This tests the full pipeline including HTML handling.

### 10.3 Manual test cases to include

Collect real examples from your collection that cover:
- Simple words, kana words, verbs, compounds
- Sentences with various particle patterns
- Words with special modifiers (`b`, `~`, `+`, `p`, `*`)
- Multiple-reading words
- Nakaten compounds
- Already-converted words (idempotency)
- Mixed old/new syntax in the same field (partial conversion)

---

## 11. Summary of Conversion at a Glance

### Word field: single-token conversion
```
kanji[reading;pitch]okurigana    →  kanji[reading]okurigana:pitch
kana[pitch]                      →  kana:pitch
compound[reading;pitch]okurigana →  split_furigana(compound, reading) + okurigana:pitch
no_pitch[reading]                →  no change
```

### Sentence field: multi-token conversion
```
1. Convert each pitched token (move pitch from bracket to colon)
2. Collapse compound groups (same letter on all brackets → letter on last only)
3. Add :p to bare particles between accented words
```
