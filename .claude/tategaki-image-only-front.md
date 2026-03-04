# Tategaki Image-Only Front Layout

When the front of the card shows only an image and audio (no word, no sentence), the tategaki layout needs special handling to stack the image above the audio buttons instead of placing them side-by-side in separate columns.

## The Problem

In normal tategaki mode, `.front` is a `vertical-rl` flex container. `.front-content` takes `height: 100%`, filling the entire column. This forces `.audio-row` to wrap into a separate column to the left. The result: image on the right, audio on the left — two separate columns.

The desired layout: image at the top, audio buttons stacked vertically and centered in the remaining space below.

## What Had to Change

### 1. CSS: Switch `.front` to horizontal-tb for image-only case

The core selector that detects "image-only front":

```css
.tategaki .card-inner:not(:has(> .back))
  .front:has(.image-wrap[data-side="front"])
       :not(:has(.target-word[data-side="front"]))
       :not(:has(.sentence[data-side="front"]))
```

The `.front` container itself gets switched out of vertical-rl:

```css
{
    writing-mode: horizontal-tb;
    flex-direction: column;
    align-items: center;
    gap: 16px;
}
```

This makes `.front` a simple top-to-bottom column with centered children, instead of the usual vertical-rl wrapped flex layout.

### 2. CSS: `.front-content` also needs the flex column properties

This was the key gotcha for the **back side**. On the back, `.front` has `display: contents` (it's flattened into `.back`'s layout). So every flex property set on `.front` does nothing — the element has no box. `.front-content` is the actual container on the back.

The fix: duplicate the flex container properties on `.front-content` itself:

```css
.front-content {
    writing-mode: horizontal-tb;
    flex-direction: column;
    align-items: center;
    gap: 16px;
    height: auto;
    align-self: auto;
}
```

- `height: auto` — on the front, `.front` is the full-height container and `.front-content` should only be as tall as the image. `.audio-row` (a sibling) gets `flex: 1` to fill the rest.
- `align-self: auto` — overrides `align-self: stretch` from the normal tategaki `.front-content` rule, so it follows the parent's `align-items: center`.

### 3. CSS: Back-specific height override (specificity battle)

On the back, `.front-content` IS the full-height container (since `.front` is `display: contents`). It needs `height: 100%`, not `auto`. But the shared rule's `height: auto` has very high specificity (~0,11,0 from all the `:has()` and `:not()` pseudo-classes).

A low-specificity `.tategaki .back .front-content:has(.audio-row-bottom)` rule (0,4,0) can't override it. The fix: mirror the full long selector with `.back` prepended to get higher specificity:

```css
.tategaki .back .card-inner:not(:has(> .back))
  .front:has(.image-wrap[data-side="front"])
       :not(:has(.target-word[data-side="front"]))
       :not(:has(.sentence[data-side="front"]))
  .front-content {
    height: 100%;
}
```

### 4. CSS: Image margin — different per side

`.tategaki .front-content .image-wrap` normally has `margin-left: 16px` to separate it from the audio column to its left. In the image-only layout:

- **Front**: `margin-left: 0` — no divider, audio is below not beside.
- **Back**: `margin-left: 16px` — the divider is to the left, needs spacing.

Same specificity approach: the shared rule sets `margin-left: 0`, the `.back`-prefixed rule restores `margin-left: 16px`.

### 5. CSS: Audio row/audio-row-bottom styling

Both `.audio-row` (front side) and `.audio-row-bottom` (back side) need the same treatment:

```css
{
    flex: 1;          /* fill remaining space below image */
    margin: 0;
    padding: 0;       /* override mobile padding-top that pushes buttons down */
    height: auto;
    justify-content: center;  /* center buttons vertically in the space */
    order: 1;         /* override audio-row-bottom's order: -3 which put it above image */
}
```

And their `.audio-item` children need `flex: 0 0 auto` to prevent them from growing to fill equal parts of the audio row (the base `.audio-item` has `flex: 1 1 0` which caused one button to appear top-aligned and the other centered).

### 6. JS (back.html): Audio routing — treat image-only as "no front content"

The back template's audio routing logic uses `hasFrontContent` to decide where audio buttons go:
- `!hasFrontContent` → audio stays in front section (`bottomRow`)
- `hasFrontContent` → audio goes to definition section (`midAudioRow`)

With an image on front, `hasFrontContent` is true, so audio was incorrectly routed to the definition section. The fix adds a `hasImageOnlyFront` check:

```js
var hasImageOnlyFront = hasFrontContent
    && !!document.querySelector('.front-content .image-wrap[data-side="front"]')
    && !document.querySelector('.front-content .target-word[data-side="front"]')
    && !document.querySelector('.front-content .sentence[data-side="front"]');
```

Then both routing decisions use `(!hasFrontContent || hasImageOnlyFront)`:
- `data-zone="front"` on `bottomRow` — keeps it in the front section visually
- `isFront` per-item check — routes each audio item to `bottomRow` not `midAudioRow`

### 7. JS (back.html): Move audio-row-bottom into front-content

Even after routing audio to `bottomRow`, the image and audio are in different containers: `.front-content` is inside the `{{FrontSide}}` block, while `.audio-row-bottom` is inside `.answer`. They can't stack because they're not siblings in the same flex context.

The fix: physically move `bottomRow` into `.front-content` after cloning:

```js
if (isTategaki && hasImageOnlyFront && bottomRow && bottomRow.children.length) {
    var fc = document.querySelector('.front-content');
    if (fc) fc.appendChild(bottomRow);
}
```

Now `.front-content` contains both the image and the audio buttons, and the CSS flex column layout stacks them correctly.

## Debugging Approach

When the layout wasn't working on the back, a `<pre>` overlay dumping computed styles was essential. Key things to check:

- `.front display` — reveals `contents` on back (all `.front` flex rules are useless)
- `.front-content flex-direction` — was `row` (from `.tategaki .back .front-content`) instead of `column`
- `.front-content height` — was `auto` (content-sized) instead of full card height
- `.audio-row-bottom order` — was `-3` (from tategaki base), pushing it above the image
- `.audio-item flex` — was `1 1 0` (from base), making items grow instead of staying natural size

## Architecture Summary

The image-only tategaki front is essentially an escape hatch from vertical-rl: both `.front` and `.front-content` switch to `horizontal-tb` with `flex-direction: column`. On the front side, `.front` is the container; on the back side, `.front-content` is the container (because `.front` is `display: contents`). This requires duplicating flex container properties on both elements, and back-specific overrides for height and image margin due to the different structural role `.front-content` plays on each side.
