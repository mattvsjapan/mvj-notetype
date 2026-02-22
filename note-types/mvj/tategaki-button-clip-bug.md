# Tategaki Audio Button Clipping Bug — AnkiMobile iOS

## Status: FIXED

**Fix:** `will-change: transform` on `.tategaki .audio-row-bottom` (one line in css.css).

This promotes the audio buttons to their own compositing layer, so they paint independently of the card-inner's broken paint bounds. No visual delay, no layout impact.

## The Problem

In tategaki (vertical writing) mode on AnkiMobile iOS, the right ~1/3 of the audio play buttons and their labels is visually clipped after showing the back of the card. The labels show "WOR" instead of "WORD" and "SENTE" instead of "SENTENCE". The play button circles are also cut off on the right side.

With the `tategakiExpand` animation (which ends at `clip-path: inset(0)`), the clip resolved after ~1 second. Without the animation, the clip was **permanent**.

When manually tapping the buttons during the clipped period, only the visible portion showed the orange active state.

## Root Cause

A **WebKit bug where paint bounds are miscalculated for `writing-mode: vertical-rl` containers**.

This maps directly to [WebKit Bug 70762 — "Incorrect repaint during layout in flipped writing modes"](https://bugs.webkit.org/show_bug.cgi?id=70762), filed October 2011 and **still open** as of 2025. The root cause: `RenderBox::computeRectForRepaint()` calls `flipForWritingMode()` during layout while the containing block's height is still 0. As a WebKit engineer explained in a 2024 comment: *"with flipped block direction an inflow child's final position is unknown until its containing block finished sizing."*

Multiple commits have fixed specific variants but never the general case:

- **Safari 18.4** fixed "vertical writing modes to set the correct bounding rect" (for SVG only, bug 135973175)
- **WebKit commit `5cf446e`**: `adjustRepaintRect()` didn't call `flipForWritingMode()` for form controls with visual overflow in vertical writing modes
- **WebKit commit `b738ab3`**: Box shadow invalidation incorrectly flipped edges in vertical-rl, causing wrong repaint rectangles
- **WebKit text-underline-position fix**: Described as a "stop-gap solution to cover incorrect repaints triggered by style changes until after we figure out the best way to compute repaint rects for such flipped content" — explicitly acknowledging the general problem remains unsolved

AnkiMobile uses WKWebView, which runs whatever WebKit version is bundled with the user's iOS. The Safari 18.4 fix only addresses SVG, so it does not help here.

### Bisection results

Through systematic elimination we confirmed:

1. **Not caused by visual properties** — removing `border-radius`, `box-shadow`, `::before`/`::after` pseudo-elements, `direction: rtl`, the `tategakiExpand` animation, and `overflow: visible` all together did NOT fix the clip.
2. **Not caused by overflow** — constraining card-inner to `width: 100%` so it didn't overflow its parent did NOT fix the clip.
3. **Caused by `writing-mode: vertical-rl` alone** — removing it (reverting to `horizontal-tb`) eliminated the clip immediately.

This means the bug is triggered by `writing-mode: vertical-rl` on any element, regardless of whether it overflows its parent.

## Layout Context

- **Viewport**: 390×753 (iPhone, portrait)
- **`html`**: `overflow: hidden` (set by AnkiMobile), `direction: rtl` (set by our CSS for tategaki back)
- **`body`**: `padding: 20px`, `box-sizing: border-box`, `overflow: auto` (set by AnkiMobile) → 350px content area
- **`div#qa`**: 350px wide (AnkiMobile's card container), `overflow: visible`
- **`.card-inner`**: 757px wide, `writing-mode: vertical-rl`, `overflow: visible` (on back), `border-radius: 16px`, `padding: 44px`, `position: relative`
- **Audio buttons** (`.audio-row-bottom`): rightmost element in the vertical-rl flex layout (`order: -4`), positioned at approximately L:273 R:325 in viewport coordinates
- **Visual clip boundary**: approximately x=306 — does **not** correspond to any known CSS box boundary
- **Def audio buttons** (`.def-audio-row`): inside `.word-column` further left in the flow — NOT affected by the clip

## Approaches Tested

### What fixed it

| Approach | Result | Tradeoff |
|---|---|---|
| **`will-change: transform` on `.audio-row-bottom`** | **Works instantly, no flash** | Permanently allocates a small GPU compositing layer (negligible on modern iPhones) |

### What partially worked

| Approach | Result | Tradeoff |
|---|---|---|
| `clip-path: inset(0)` on card-inner (static) | Fixes clip but ~0.5s visible flash | Delay before WebKit establishes correct paint bounds |
| `contain: paint` on card-inner | Fixes clip but ~0.5s visible flash | Same delay as clip-path; may have side effects with overflow |
| `tategakiExpand` animation ending at `clip-path: inset(0)` | Clip resolves after ~1s | Visual clip visible during animation |

### What didn't work

| Approach | Result |
|---|---|
| `overflow: visible !important` on html, body, #qa (individually and all together) | No effect |
| `border-radius: 0` on card-inner | No effect |
| `will-change: clip-path` on card-inner | No effect |
| Forced synchronous layout reflow via JS (`offsetWidth`) | No effect |
| Pre-establishing `clip-path: inset(0)` on the front side | Reduced flash but didn't eliminate it |
| `transform: translateZ(0)` on card-inner | **Made it worse** (permanently clipped) |
| Removing box-shadow, pseudo-elements, direction: rtl | No effect |
| Constraining card-inner width to prevent parent overflow | No effect |

## Why `will-change: transform` works

The clip is caused by WebKit miscalculating the paint bounds of the `writing-mode: vertical-rl` compositing layer. Elements painted within that layer get clipped to the wrong rectangle.

`will-change: transform` on the audio row promotes it to its **own** compositing layer. Since that layer uses `writing-mode: horizontal-tb` (set explicitly on `.tategaki .audio-row-bottom`), WebKit calculates its paint bounds correctly. The audio buttons are no longer subject to the parent's broken bounds.

`transform: translateZ(0)` on card-inner made things worse because it forced the *entire* vertical-rl element into a GPU layer, but WebKit still miscalculated that layer's bounds. The fix is to promote the *children* out of the broken layer, not to change the broken layer's compositing.
