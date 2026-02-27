# Old Pitch Accent Syntax (MvJ Addon)

This documents the pitch accent notation that the MvJ Japanese addon writes into Anki note fields. This is the format that needs to be converted to the new colon-based system used by the pitch-graphs templates.

## Field Format Overview

Pitch accent is embedded into furigana bracket notation using a semicolon separator:

```
word[reading;pitch]
```

The reading comes from MeCab/dictionary lookup, and the pitch comes from the NHK pronunciation dictionary or user-defined overrides.

## Target Word Field

### Basic patterns

| Pattern | Example | Description |
|---------|---------|-------------|
| `kanji[reading;pitch]` | `日本[にほん;2]` | Standard kanji word with pitch |
| `kanji[reading;p1,p2]` | `時[とき;1,2]` | Multiple pitch accents (comma-separated) |
| `kanji[reading]` | `日本[にほん]` | No pitch data available |
| `kana[pitch]` | `あう[0,1]` | All-kana word (no reading needed, just pitch) |
| `kana[pitch]` | `かわいい[3]` | All-kana word where word = reading (simplified) |
| `katakana[pitch]` | `アニメ[0]` | Katakana word (pitch only, no reading needed) |

### With okurigana

When a word has trailing kana (okurigana), the okurigana stays outside the brackets:

```
考[かんが;n]える
食[た;k]べる
行[い;0]く
```

### Compound words

Compound words (multi-morpheme) get collapsed into a single bracket pair:

```
考え方[かんがえかた;5,0]
```

If the compound has trailing okurigana (kana after the last kanji), it's placed outside:

```
取り替[とりか;3,0]え        (え is okurigana, outside the bracket)
```

### Multiple readings

When a word has multiple possible readings, they're comma-separated inside the brackets. Each reading can have its own pitch:

```
心中[しんじゅう;0,しんちゅう;1,0]
被[かぶ;2,こうむ;3]る
```

### Multiple brackets

When `format_output` breaks compound furigana into separate kanji groups (e.g., ` 一[いっ]石[せき]`), each bracket receives pitch sequentially. If only one pitch value exists, only the first bracket gets it:

```
一[いっ;2]石[せき]
```

Note: letter codes like `a`/`n` are sentence-field notation (see below), not word-field notation.

## Sentence Field

### Single words

Same as target word, but only the **first** pitch accent is used (no alternatives):

```
日本[にほん;2]
```

### Compound words in sentences

When a compound word appears in a sentence, the pitch is converted to a **letter code** and applied to every bracket:

```
考[かんが;n]え 方[かた;n]
```

Letter codes used for compounds:
- `h` — heiban (when pitch is `0`)
- `a` — atamadaka (when pitch is `1`)
- `n` — nakadaka/non-heiban (when pitch is 2+, catch-all for nouns)
- `k` — kifuku (when pitch contains `k`, for verbs/i-adjectives)

### Leading plain kana in compounds

If a compound starts with plain kana (no brackets), a pitch-only bracket is added:

```
お[n] 母[かあ;n]さん
```

### Inflected verbs/i-adjectives

When a verb or i-adjective appears inflected in a sentence, the pitch is reduced to simplified `h`/`k` notation based on the **base form** pitch. Only the first value is used (sentence mode takes `.split(',')[0]`):

- `h` — heiban (base form pitch is `0`)
- `k` — kifuku (base form pitch is non-`0`)

For compound base forms (e.g., `1-2`), only the second part (the verb portion) determines h/k.

When the base form has both heiban and kifuku readings, `_convert_to_simplified_pitch()` produces `h,k` or `k,h` (order preserved), but sentence mode only uses the first value. The full `h,k` notation can appear in the **word field** when an inflected form is entered directly (e.g., `食[た;h,k]べた`).

Examples:

```
食[た;k]べた          (食べる base form is kifuku)
走[はし;h]って        (走る base form is heiban)
```

### Spacing

Spaces are inserted before any token that has brackets, or after any token that has pitch accent notation. This means particles end up space-separated from the preceding pitched word:

```
日本[にほん;2] に 行[い;k]きたいです。
今日[きょう;1] は いい 天気[てんき;1]ですね。
```

When MeCab produces a merged token like `今日は`, the particle is stripped for pitch lookup and appended as a separate part (with a space before it). When MeCab tokenizes a particle separately (e.g., `に`), it remains a separate token and also gets a space before it if the previous token has pitch.

## Pitch Values

### Numeric values (from NHK dictionary)

| Value | Name | Meaning | Pattern |
|-------|------|---------|---------|
| `0` | Heiban | Flat — rises after first mora, stays high | L-H-H-H... |
| `1` | Atamadaka | Head-high — drops after first mora | H-L-L-L... |
| `2` | Nakadaka | Middle drop — drops after mora 2 | L-H-L-L... |
| `3` | Nakadaka | Middle drop — drops after mora 3 | L-H-H-L... |
| `N` | Nakadaka/Odaka | Drops after mora N | L-H-...-H-L... |
| `N` (= mora count) | Odaka | Tail-high — drops after the last mora | L-H-...-H(+L particle) |

### Compound pitch (hyphen-separated)

For compound words with nakaten (・) in the reading:

```
十人十色[じゅうにん・といろ;1-1]
```

The number of pitch values (separated by `-`) matches the number of reading segments (separated by `・`).

### Category letters

These are used in user-defined overrides and in sentence compound notation:

| Letter | Meaning | Equivalent |
|--------|---------|------------|
| `h` | Heiban | `0` |
| `a` | Atamadaka | `1` |
| `n` | Nakadaka | Any 2+ but not odaka (unspecified) |
| `o` | Odaka | Mora count of the reading |
| `k` | Kifuku | Stripped prefix; underlying pitch determined separately |

### Kifuku prefix

For verbs and i-adjectives with non-heiban pitch, the addon may prefix with `k`:

```
食[た;k1]べる        (kifuku with pitch 1)
```

The `k` is a marker indicating the verb/adjective has non-flat pitch. `parse_pitch_specification()` strips it recursively to get the underlying number.

### Special modifiers (from user overrides)

These are **not generated automatically** by the addon — they only appear if manually entered in `reading_overrides.csv`. They are handled at render time by the JavaScript template:

| Modifier | Example | Meaning |
|----------|---------|---------|
| `b` suffix | `0b`, `2b`, `pb` | "Black" — rendered in black/neutral color instead of category color |
| `~` | `~0`, `0~` | Force all-low pitch |
| `+` | `2+` | Extra particle mora appended |
| `p` prefix | `p`, `p0`, `p1`, `ph` | Particle marker |
| `*` on kana | `*き` in reading | Devoiced mora |

### Simplified notation (inflected forms)

In **sentence fields**, only `h` or `k` appears (the first value after splitting on `,`):

| Value | Meaning |
|-------|---------|
| `h` | Base form is heiban |
| `k` | Base form is kifuku (non-heiban) |

In the **word field** (when an inflected form is entered directly), the full notation may appear:

| Value | Meaning |
|-------|---------|
| `h,k` | Base form has both heiban and kifuku readings |
| `k,h` | Same as above, kifuku listed first |

## Mora Counting Rules

Used to determine odaka and pitch patterns:

- Standard kana = 1 mora (あ, か, さ, etc.)
- Small kana = 0 morae, combines with previous (ゃ, ゅ, ょ, etc.)
- ー (long vowel) = 1 mora
- ん/ン = 1 mora
- っ/ッ (geminate) = 1 mora

Examples:
- にほん = 3 morae
- がっこう = 4 morae
- きょう = 2 morae (ょ doesn't count)
- トーキョー = 4 morae

## Real Examples

### Target word field

```
日本[にほん;2]
時[とき;1,2]
あう[0,1]
考え方[かんがえかた;5,0]
十人十色[じゅうにん・といろ;1-1]
心中[しんじゅう;0,しんちゅう;1,0]
食[た]べる                          (no pitch data)
```

### Sentence field

```
日本[にほん;2] に 行[い;k]きたいです。
今日[きょう;1] は いい 天気[てんき;1]ですね。
考[かんが;n]え 方[かた;n] を 変[か;k]えた。
```

## Data Sources

- **NHK dictionary**: Primary source for pitch numbers (`NHK-2016.pickle`). Returns pitch as strings — plain integers (e.g., `"2"`) or compound pitches (e.g., `"1-1"` for nakaten words). Shinmeikai-8 (`Shinmeikai-8.pickle`) is used as a secondary/fallback source.
- **User overrides** (`reading_overrides.csv`): Can override any word's pitch. Supports conditional overrides based on MeCab reading, next word, and POS subcategory.
- **Simplified notation**: Generated at lookup time for inflected verbs/i-adjectives. Not stored in overrides.
