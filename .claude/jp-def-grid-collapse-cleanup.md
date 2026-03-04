# JP Definition Grid Collapse: Cleanup Task

## Background

The `.jp-def-wrap` uses a `0fr`/`1fr` grid trick to animate the monolingual definition open/closed:

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

This worked perfectly until two things independently added padding to the grid child, inflating the `0fr` track (padding is not content — `overflow: hidden; min-height: 0` only collapses content to zero, not padding):

1. **`.text-play { padding: 2px 6px; }`** — added 4px vertical. **FIXED by the `::after` refactor** (commit `470d63b`). Text-play no longer adds padding.

2. **`.def:not([data-font]) { padding: 6px; }`** — added 12px vertical. **Still present.** Introduced in commit `e84da53` ("Port Chinese card layout changes to MVJ") as part of a batch. The user confirms this padding is not needed.

A hack was added in commit `950d09e` to work around both: animate vertical padding to 0 when collapsed, with a `transition: padding 400ms` to match the grid animation. This works but forces layout reflow every animation frame (expensive on mobile), and was never implemented for tategaki.

## What to do

### 1. Change `.def:not([data-font]) { padding: 6px; }` to use margin (css.css ~line 1333)

The user wants the 6px breathing room around def text — the intent was to keep text from touching the edge. But padding on a grid child inflates the `0fr` track. **Margin does not** — it sits outside the border box and gets swallowed when the content collapses to zero.

Change:
```css
/* Before */
.def:not([data-font]) { padding: 6px; }

/* After */
.def:not([data-font]) { margin: 6px; }
```

However, `.jp-def-wrap > *` sets `margin: 0` which would override this inside the grid. That's fine — the definition doesn't need breathing room when it's inside the collapsible wrap (the wrap's own `margin-top: 2px` handles the gap from the toggle button). The `margin: 6px` would only take effect on `.def` elements that are NOT inside the wrap (direct definitions in the answer section).

If the user DOES want the 6px inside the wrap when expanded, use a more targeted override:
```css
.jp-def-input:checked ~ .jp-def-wrap > .def:not([data-font]) { margin: 6px; }
```
This only applies when expanded, so it won't affect the `0fr` collapsed state (margin on a zero-height child is collapsed away by the grid).

**Check both templates:**
- `note-types/mvj/css.css`
- `note-types/chinese/css.css` (may have the same rule — it was ported FROM Chinese)

### 2. Remove the padding-zeroing hack (css.css ~lines 1434, 1438-1441)

These rules exist solely to work around the padding inflation. With the padding gone, they're unnecessary:

```css
/* Remove the transition on .jp-def-wrap > * */
.jp-def-wrap > * {
    overflow: hidden;
    min-height: 0;
    margin: 0;
    transition: padding 400ms cubic-bezier(0.25, 0.1, 0.25, 1);  /* ← remove this line */
}

/* Delete this entire block */
.jp-def-input:not(:checked) ~ .jp-def-wrap > * {
    padding-top: 0;
    padding-bottom: 0;
}
```

### 3. Keep `margin-top: 2px` on `.jp-def-wrap` (line ~1426)

This is the intentional 2px gap between the toggle button and the definition content. Do not remove it.

### 4. Verify `.jp-def` has no padding

Before the problems started, `.jp-def` had `padding-top: 0` explicitly. Check that no other rule adds padding to `.jp-def` or to elements inside `.jp-def-wrap > *`. The grid child must have zero vertical padding for the `0fr` collapse to fully work.

Relevant elements that can end up as the grid child:
- `.jp-def` (the default monolingual definition)
- `.def` (JS renames `.jp-def` to `.def` in `dual-mono` mode)

### 5. Test

- Toggle the monolingual definition open and closed — should animate smoothly
- When collapsed, there should be NO gap below the toggle button (other than the 2px margin-top)
- Test in both non-tategaki and tategaki modes
- Test in all definition modes: `monolingual`, `bilingual`, `all` (dual), `unlocked`
- Check that definition text content still looks properly spaced when expanded (if the 6px padding is missed, margin or line-height on `.def`/`.jp-def` can compensate)

### 6. Remove the debug dump from front.html

There's a `// ── DEBUG DUMP: front-content overflow diagnostics ──` script block in `front.html` that should be removed if still present.

## Why this is safe now

The `::after` refactor (commit `470d63b`) eliminated text-play padding entirely. With `.def:not([data-font]) { padding: 6px; }` also removed, NO padding sources remain on the grid child. The `0fr` track collapses fully to zero without any workarounds. The padding transition hack becomes dead code.

## Files to modify

- `note-types/mvj/css.css` — remove `.def:not([data-font])` padding, remove padding hack
- `note-types/chinese/css.css` — check for same `.def` padding rule
- `note-types/mvj/front.html` — remove debug dump if present
