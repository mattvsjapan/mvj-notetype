# Text-play pill position refactor

## The problem

The text-play pill (the `::after` highlight behind clickable text) needs its top edge positioned differently depending on whether ruby/furigana annotations are visible, hidden, or absent. In horizontal mode, when furigana is hidden on the front side (`visibility: hidden` preserves layout space), the pill must pull its top edge inward so it doesn't extend into the empty annotation area. When furigana is visible on the back side, the pill must extend outward to encompass the annotations.

Previously, this was handled by ~20 context-specific `::after` rules with hardcoded `top` values — one for each combination of element type (`.target-word`, `.sentence`, `.def`, `.jp-def`, `.word-pitch-group`), container (`.front-content`, `.back .front-content`, `.answer`), and device (`@supports` for iOS). Every new container or furigana state required a new batch of rules for every element type.

This caused two concrete bugs:

1. **Word/sentence on back only**: When configured to appear only on the back (inside `.answer` rather than `.front-content`), there were no ruby-specific `::after` rules. The pill fell back to its default inset, ignoring the furigana entirely. This made the spacing look wrong compared to the same elements on the front.

2. **Split furigana with furigana off**: The `日本語[言語|にほんご]` syntax shows selective readings even when the furigana setting is "off". The `rt[data-split]` elements override `display: none` and remain visible. But all pill positioning rules used `:not(.furigana-off)`, so the pill treated these elements as having no ruby at all — it didn't extend to cover the visible split readings.

## How the refactor fixes it

The pill positioning is now a two-layer CSS custom property system in `css.css`:

**Layer 1 — Per-element tuning values** (lines 937-942): Each element type declares `--pill-ruby-hidden` (how far to pull the pill inward when furigana is invisible) and `--pill-ruby-visible` (how far to extend when furigana is showing). These are the only values that need tuning per element type or per device (iOS overrides at lines 2159-2170 just reassign these same variables).

**Layer 2 — State resolution** (lines 944-974): Four rules for non-tategaki and two for tategaki resolve the furigana visibility state into `--pill-top` (or `--pill-right` for tategaki). The rules use CSS specificity to cascade correctly:

| Specificity | Rule | Sets `--pill-top` to |
|---|---|---|
| (0,3,2) | `.text-play:has(ruby):not(.furigana-off)` | `--pill-ruby-visible` |
| (0,3,2) | `.text-play.furigana-off:has(rt[data-split])` | `--pill-ruby-visible` |
| (0,4,2) | `.front-content .text-play:has(ruby):not(.furigana-front):not(.furigana-off)` | `--pill-ruby-hidden` |
| (0,5,2) | `.back .front-content .text-play:has(ruby):not(.furigana-front):not(.furigana-off)` | `--pill-ruby-visible` |

The `::after` rule itself (line 899) just reads `var(--pill-top, -2px)` — it never needs to change.

**Why the bugs are fixed:**

- `.answer .target-word` with ruby matches the general "ruby visible" rule (first row) and gets `--pill-ruby-visible`. No `.answer`-specific rule needed — the state resolution is container-agnostic.
- Split furigana with `.furigana-off` matches the dedicated split rule (second row) and gets `--pill-ruby-visible` for the visible readings.
- Adding future containers or furigana states requires at most one new state resolution rule, not one per element type per device.

## What to adjust if pill spacing looks wrong

To adjust how far the pill extends above visible furigana for a specific element, change its `--pill-ruby-visible` value (lines 938-942 for standard, lines 2160-2164 for iOS). To adjust how far the pill pulls inward past hidden furigana on the front, change `--pill-ruby-hidden`. No other rules need to change.
