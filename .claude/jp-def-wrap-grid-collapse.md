# JP Definition Wrap: Grid Track Collapse Bug

## Problem

In non-tategaki cards with a dual definition layout (both bilingual and monolingual), the toggle button ("Monolingual" / "Bilingual") had ~14px of extra space below it when retracted. The `clearLastMargin` function correctly identified `.jp-def-section` as the last visible element and zeroed its `marginBottom`, but the gap persisted because the source of the extra space was *inside* the section, not on its margin.

## Root Cause

The `.jp-def-wrap` uses a `0fr` grid trick to animate open/closed:

```css
.jp-def-wrap {
    display: grid;
    grid-template-rows: 0fr;  /* collapsed */
}
.jp-def-input:checked ~ .jp-def-wrap {
    grid-template-rows: 1fr;  /* expanded */
}
.jp-def-wrap > * {
    overflow: hidden;
    min-height: 0;
    margin: 0;
}
```

The child element inside the wrap has `overflow: hidden; min-height: 0;` so its *content* collapses to zero height in a `0fr` track. But **padding is not content** — it's part of the element's box. When the child had padding, the border-box remained non-zero, inflating the grid track.

The padding came from two sources, both applied by class changes made in JS:

1. **`.def:not([data-font]) { padding: 6px; }`** — In `dual-mono` mode, the JS renames the `.jp-def` child to class `def` (`jpDefEl.className = 'def'`). Since the bilingual content has no `data-font` attribute, this rule matched, adding 6px padding on all sides (12px vertical total).

2. **`.text-play { padding: 2px 6px; }`** — The text-play feature adds this class for tap-to-play-audio, contributing another 2px top + 2px bottom.

Combined: **12px from `.def` padding + 4px from `.text-play` padding = up to 14px** of phantom height in what should be a fully collapsed container.

## Why Initial Fixes Failed

- **`overflow: hidden` on `.jp-def-wrap`**: Didn't help. The grid track *itself* resolved to ~12px (not 0px) because the child's padding inflated the track's minimum size. Clipping overflow on the container doesn't change track sizing.

- **`clearLastMargin` clearing `paddingBottom`**: Would only affect `.jp-def-section`'s own padding (which was already 0). The problem padding was on a *grandchild* element inside the section.

## The Fix

Zero only the vertical padding on the wrap's child when the toggle is unchecked:

```css
.jp-def-wrap > * {
    overflow: hidden;
    min-height: 0;
    margin: 0;
    transition: padding 400ms cubic-bezier(0.25, 0.1, 0.25, 1);
}

.jp-def-input:not(:checked) ~ .jp-def-wrap > * {
    padding-top: 0;
    padding-bottom: 0;
}
```

Key decisions:

- **Only vertical padding is zeroed** (`padding-top`/`padding-bottom`), preserving horizontal padding. Without this, the text shifts left abruptly when the toggle closes.

- **A `transition` on padding** matches the grid's 400ms collapse animation. Without it, the vertical padding snaps to 0 instantly while the grid animates, causing an unnatural upward jut at the start of the collapse.

- **`:not(:checked)` scoping** means the padding override only applies when collapsed. When expanded, the normal `.def:not([data-font])` and `.text-play` padding rules apply freely.

## Debugging Approach

Dump debugging was essential. The initial analysis (reading CSS rules and guessing) produced three incorrect fixes. The actual root cause only became clear by injecting a debug overlay after `clearLastMargin` that reported `getBoundingClientRect()` and `getComputedStyle()` for every element in the chain — revealing that `.jp-def-wrap` had `h=12.0` and `grid-template-rows: 11.9978px` instead of the expected 0.

## Takeaway

In a `0fr`/`1fr` grid collapse pattern, `overflow: hidden; min-height: 0;` on the child only collapses the *content box*. Any padding on the child inflates its border box, which in turn inflates the grid track. If the child can acquire padding from external CSS rules (especially via JS class changes), the collapse breaks silently.
