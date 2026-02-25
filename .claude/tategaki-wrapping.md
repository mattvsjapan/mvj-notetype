# Tategaki Word-Column Wrapping Fix

## The Problem

In tategaki mode, the `.word-column` contains four items stacked vertically:
target word, pitch graph, definition audio buttons, and image. When the card
height is too small to fit all four, they get clipped instead of causing the
card to grow wider.

## Root Cause

The original layout had `writing-mode: vertical-rl` set only on `.answer`,
while `.card-inner` remained in `horizontal-tb`. In horizontal-tb,
`.card-inner` uses `width: fit-content` to shrink-wrap to its content. But
CSS computes `fit-content` width **before** applying the fixed height
constraint — so at width-calculation time, there's infinite height available,
no wrapping happens, and the width is set to the single-column value. By the
time the fixed height triggers wrapping inside `.word-column`, the card's
width is already locked in.

This is a well-documented CSS limitation:

- **Flexbug #14**: `flex-direction: column; flex-wrap: wrap` containers do
  not report their intrinsic cross-size (width) including wrapped columns.
  The CSS Working Group acknowledges this in
  [csswg-drafts#6777](https://github.com/w3c/csswg-drafts/issues/6777).
  Firefox [Bug 995020](https://bugzilla.mozilla.org/show_bug.cgi?id=995020)
  has been open since 2014.

- The core issue is a **circular dependency**: width depends on how many
  columns wrap, wrapping depends on available height, and height depends on
  layout — but CSS computes width in a single pass before layout.

## Why Old-Tategaki Worked

The old tategaki card set `writing-mode: vertical-rl` at a high level
(`.outer_container`), not just on the content area. This changes everything:

- In `vertical-rl`, a block element's **width is its block-size**, which
  auto-sizes to content. No `width: fit-content` needed.
- The wrapping container (`.backside_in`) used the default
  `flex-direction: row`, which in `vertical-rl` means main axis = top→bottom
  (inline direction). `flex-wrap: wrap` wraps to new columns right→left
  (block direction).
- **Flexbug #14 only affects `flex-direction: column`**, not `row`. So the
  width propagates correctly through the parent chain.
- Items that needed their own column (like `.meaning`) used `height: 100%`
  to force a column break.

## The Fix

Move `writing-mode: vertical-rl` up from `.answer` to `.card-inner` in
tategaki mode. This makes the card behave like old-tategaki:

### `.card-inner` (tategaki)

```css
writing-mode: vertical-rl;
height: 668px;           /* = inline-size in vertical-rl */
/* no width / fit-content — block-size auto-sizes to content */
```

### `.answer`

```css
display: flex;
flex-wrap: wrap;
/* default flex-direction: row = T→B in vertical-rl */
height: 100%;
```

Items that should be standalone columns use `height: 100%` to fill the
inline-size and force a column break (sentence, divider, definition,
jp-def-section).

### `.word-column`

```css
display: flex;
flex-direction: row;     /* = T→B in inherited vertical-rl */
flex-wrap: wrap;         /* progressive overflow into new columns */
align-content: flex-end; /* pack columns toward the content side */
```

Each child resets `writing-mode: horizontal-tb` individually.

### Result

- **All 4 items fit**: single column, card stays narrow
- **3 fit**: 3 + 1 split, card grows slightly wider
- **2 fit**: 2 + 2 split, card grows wider
- **1 fits**: each item gets its own column, card at maximum width

Pure CSS. No JavaScript. The card width grows and shrinks automatically
based on available height.

## WebKit Paint Bounds Bug

WebKit miscalculates paint bounds for `writing-mode: vertical-rl`
containers, causing child elements to be visually clipped or to disappear
entirely — even though they exist in the DOM. The content may partially
render for a moment, then vanish.

This affects any element whose writing mode differs from its parent's
(e.g. a `horizontal-tb` child inside a `vertical-rl` parent). WebKit
computes the paint area based on the parent's writing mode and gets the
bounds wrong.

### Fix

Add `will-change: transform` to the affected element. This promotes it
to its own compositing layer, forcing WebKit to calculate its paint
bounds independently of the parent.

### Affected elements (so far)

| Element | Why it needs the fix |
|---------|---------------------|
| `.tategaki .audio-row-bottom` | Audio buttons clipped on right edge (css.css:1845) |
| `.tategaki .mid-audio-row` | Same clipping issue for mid-column audio (css.css:1616) |

### Symptoms

- Content partially renders then fully disappears
- Background color visible but no content
- Only happens on mobile WebKit (iOS Safari / AnkiMobile / AnkiDroid WebView)
- Desktop browsers unaffected

## Orthogonal Flow Sizing Collapse

### The rule

**Never set `writing-mode: horizontal-tb` on `.front` inside a
`vertical-rl` `.card-inner`.** This creates an orthogonal flow where
`.front`'s width depends on `.card-inner`'s width and vice versa. If
`.front` has no immediate intrinsic content (e.g. audio row is hidden,
`.front-content` is empty before JS runs), both collapse to zero width.

### Why the back is immune

On the back, `.front` is set to `display: contents` — it's removed from
the layout tree entirely. Content sits directly in `.answer`, which
inherits `vertical-rl` from `.card-inner`. Same writing mode throughout,
no orthogonal flow, no circular sizing.

### Why it worked on main

On the `main` branch, `.front` only contained `.audio-row` with real
audio elements from Mustache tags — always present, always giving `.front`
intrinsic width. The orthogonal flow resolved because the child had
content.

On `flexible-settings`, `.front` gained `.front-content` (empty until JS
populates it) and the audio row can be `display: none` (when
`--word-audio: off` and `--sentence-audio: off`). With no intrinsic
content, the orthogonal sizing collapses.

### The fix

Keep `.front` in inherited `vertical-rl` — same writing mode as
`.card-inner`. No orthogonal flow, width auto-sizes from content
naturally (same as how `.answer` works on the back).

```css
.tategaki .card-inner:not(:has(> .back)) .front {
    display: flex;
    /* flex-direction: row (default) = top→bottom in vertical-rl */
    align-items: flex-start;  /* = right edge (block-start in v-rl) */
    height: 100%;
}
```

`.audio-row` needs explicit `writing-mode: horizontal-tb` since it
previously inherited it from `.front`.

### First-frame flash

When `.front-content` starts empty and JS populates it, there's one
frame where `.card-inner` renders at its minimum size (just padding).
The back masks this with its `clip-path` → `tate-expand` reveal
animation on `.card-inner`. The front needs its own mask — a 16ms
opacity animation delay on `.card-inner`:

```css
.tategaki .card-inner:not(:has(> .back)) {
    animation: tateFrontReveal 0s 16ms both;
}
@keyframes tateFrontReveal {
    from { opacity: 0; }
    to   { opacity: 1; }
}
```

This hides the card for one frame, letting JS populate content before
the first visible paint.
