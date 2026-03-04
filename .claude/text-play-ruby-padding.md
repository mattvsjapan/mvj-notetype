# text-play ruby padding when furigana is hidden

## The problem

The `.text-play` highlight (background color on hover/playing) visually extends into the empty space above the base text where hidden furigana annotations sit.

On the front of the card, `<rt>` elements are hidden with `visibility: hidden`. This hides the text but **preserves its layout space**. The ruby annotation area remains as empty vertical space above the kanji. When the text-play highlight background activates (hover or playing state), it fills the entire element box — including that empty ruby annotation area — making it look like there's way too much top padding above the text.

## Why visibility: hidden is used (not display: none)

The front template is included on the back via `{{FrontSide}}`. On the back, CSS reveals the furigana with `visibility: visible` + a fade-in animation. Because `visibility: hidden` preserves layout space, the target word sits in the **exact same vertical position** on both front and back. If `display: none` were used instead, the word would jump down when flipping to the back as the furigana space suddenly appears.

## What was tried

### Attempt 1: Conditional padding selectors

Replaced the unconditional `.text-play:has(ruby)` padding selectors with three-pronged selectors that only match when ruby is actually visible:

1. `.back .text-play:has(ruby):not(.furigana-off)` — back side
2. `.text-play.furigana-front:has(ruby)` — front with furigana explicitly shown
3. `.text-play:has(rt[data-split])` — split readings always visible

**Result:** The extra padding correctly stopped applying on the front (debug confirmed `padding-top: 2px`). But the visual problem remained — the empty ruby annotation space is part of the element's **content box**, not its padding. The highlight background covers the content box regardless of padding values.

### Attempt 2: Move highlight to ::before pseudo-element with JS-measured inset

Moved the `background` and `box-shadow` from the element itself to a `::before` pseudo-element (`position: absolute; inset: 0; z-index: -1`). Then on the front, when furigana is hidden, inset the `::before`'s `top` by the measured ruby annotation height (set via `--ruby-h` CSS custom property from JS).

**Result:** Two failures:

1. **Jump on page load.** The `--ruby-h` measurement ran in a `setTimeout(fn, 200)` after the page rendered. The highlight initially appeared at full size (before JS ran), then jumped smaller once the variable was set. Visible flicker.

2. **Word position shift between front and back.** On the back side, the extra padding rules kick in (`padding-top: 17px; margin-top: -17px` for target-word with visible ruby). This changes the element's padding box size. Even though the negative margin compensates for surrounding layout, the `::before` (which uses `inset: 0` relative to the padding box) now covers a different area. The word appeared to jump up when flipping from front to back.

## Relevant CSS and DOM structure

### DOM hierarchy

**Front:**
```
(card container) > div.card-inner > div.front > div.front-content > h1.target-word.text-play
```

**Back:**
```
(card container) > div.back > div.card-inner > div.front > div.front-content > h1.target-word.text-play
                            > (back-specific content)
```

### Key CSS rules

```css
/* Front: rt hidden but space preserved */
.front-content .target-word rt { visibility: hidden; }
.front-content .sentence rt { visibility: hidden; }

/* Back: rt revealed with animation */
.back .front-content .target-word rt { visibility: visible; animation: rtFadeIn 0.25s ease both; }
.back .front-content .sentence rt { visibility: visible; animation: rtFadeIn 0.25s ease both; }

/* Base text-play */
.text-play { padding: 2px 6px; margin: -2px -6px; }

/* Highlight states (currently on the element itself) */
.text-play:hover { background: var(--accent-soft); box-shadow: inset 0 0 0 1px var(--accent-glow); }
.text-play.playing { background: var(--accent-soft-bright); box-shadow: inset 0 0 0 1px var(--accent-glow); }
```

### Ruby font sizes

- `.target-word rt` — `font-size: 0.33em` (of 52px base = ~17px)
- `.sentence rt` — `font-size: 0.5em`

### Furigana visibility states

| Context | Default (no class) | `.furigana-front` | `.furigana-off` | `rt[data-split]` |
|---------|-------------------|-------------------|-----------------|-------------------|
| Front card | hidden (`visibility: hidden`) | visible | `display: none` | visible |
| Back card | visible | visible | `display: none` | visible |

### Tategaki

In tategaki (vertical writing) mode, the ruby space is on the **right side** instead of the top. The tategaki section already uses `display: none` on front-side `rt` (with `display: revert` on back) because the ruby space issue was previously encountered there for layout reasons unrelated to text-play.

### Files

- `note-types/mvj/css.css` — all styling, text-play rules around lines 881–965
- `note-types/mvj/front.html` — front template, text-play linkage around lines 862–891
- `note-types/mvj/back.html` — back template, text-play linkage around lines 885–900
