# iOS Ruby Annotation Gap Workaround

## The Problem

iOS WebKit's ruby layout engine (`RubyFormattingContext.cpp`) automatically adds ~10-12px of extra space around `<rt>` annotations. This inflates line boxes — lines with furigana become taller (horizontal) or wider (tategaki) than lines without. There is no CSS property to control or disable this gap.

## Our Solution

Three-layer workaround in the `@supports (-webkit-touch-callout: none)` block in `css.css`:

### 1. Collapse the gap: `margin-block: -0.5em` on `rt`

Applied to `.sentence rt`, `.def rt`, `.jp-def rt`. In horizontal mode, `margin-block` collapses vertical space; in tategaki (`writing-mode: vertical-rl`), it collapses horizontal space — both targeting the annotation gap axis. This makes lines with and without furigana the same size.

### 2. Reposition furigana: `transform: translate(...)`

The margin collapse pulls furigana visually into the base characters. Transform nudges it back to the correct position without affecting layout flow.

### 3. iPhone vs iPad split: `@media (min-width: 768px)`

AnkiMobile uses different text scaling on each device:
- **iPhone**: `-webkit-text-size-adjust` (rendering-level inflation)
- **iPad**: root `font-size` / `rem`-based scaling (clean CSS cascade)

These produce slightly different internal font metrics, so the annotation gap differs between devices. The base `@supports` values are tuned for iPhone; the `@media (min-width: 768px)` overrides are tuned for iPad.

## Key Values (as of commit 531b70e)

### Non-tategaki

| Property | iPhone | iPad |
|---|---|---|
| `margin-block` | `-0.5em` | `-0.5em` |
| `transform` | `translateY(0.1em)` | `translateY(-0.35em)` |
| Container `padding-top` | `0.2em` | `0.2em` |

### Tategaki

| Property | iPhone | iPad |
|---|---|---|
| `margin-block` | `-0.5em` | `-0.5em` |
| Sentence `transform` | `translate(-0.15em, 0.07em)` | `translate(0.35em, 0.07em)` |
| Def/jp-def `transform` | `translate(-0.1em, 0.07em)` | `translate(0.4em, 0.07em)` |
| Container `padding-right` | `0.25em` | `0.25em` |

### Font sizes (mobile, both devices)

- Sentence rt: `0.45em` (tategaki iOS gets its own override due to source-order conflict with `@media (hover: none)` rule at ~line 2445)
- Def/jp-def rt: `0.5em`

## Source Order Gotcha

The tategaki `.sentence rt` rule in `@media (hover: none)` (around line 2445) comes **after** the main `@supports` block. Same specificity, later source order — so it overrides the iOS transform. Fix: a second `@supports (-webkit-touch-callout: none)` block placed after that mobile rule to re-assert the iOS values.

## Why Not Something Better?

- **No CSS `annotation-gap` property exists.** The gap is computed in WebKit's C++ layout code.
- **`ruby-position`** only controls over/under, not gap size.
- **`ruby-align`** and **`ruby-overhang`** don't affect the gap either.
- **Abandoning native `<ruby>`** for absolute positioning would be more fragile and complex.
- **Can't modify** WebKit's layout engine or AnkiMobile's text scaling.

This is the least-bad option given the constraints.

## Desktop / AnkiDroid

Not affected. The entire workaround lives inside `@supports (-webkit-touch-callout: none)`, which only matches iOS WebKit.
