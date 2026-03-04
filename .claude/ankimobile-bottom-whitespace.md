# AnkiMobile Bottom Whitespace Bug

## Problem

AnkiMobile (iOS) always shows a persistent empty strip at the bottom of cards, between content and the bottom navigation bar. The strip takes on the page's background color but won't render background images.

## Root Cause

Explained by dae (Damien Elmes, Anki's creator):

- The WebView is set to **full screen height** so the top and bottom bars get translucency effects as the user scrolls (same approach Safari uses).
- The white strip is caused by **iOS WebView insets** — padding iOS adds so content can scroll up past the bottom bar when the page is shorter than the screen.
- iOS treats solid background colors and images differently in inset areas: a solid `background-color` fills the strip, but `background-image` may not.

> "The webview is the height of the entire screen, so that the top and bottom bars' translucency is affected as you scroll, like in Safari."

## Solution

The key insight: the inset strip only appears when element-level scrolling reaches the iOS WebView's inset area. By making `html` a fixed viewport with `overflow: hidden` and promoting `.card` (body) to be the sole scroll container, scrolling never escapes into the inset zone.

### CSS — inside `@media (hover: none)`

```css
html { height: 100dvh; overflow: hidden; }
.card { padding: 20px; min-height: auto; height: 100dvh; overflow-y: auto; }
```

- `html` is clamped to exactly the viewport and can't scroll — the inset area is never reached.
- `.card` (Anki's body element) becomes the scroll container. Its `overflow-y: auto` means only its *content* scrolls, fully contained within the viewport.

### JS — front.html lock script

```javascript
function lock() {
    var h = window.innerHeight;
    if (isBack) {
        document.body.style.height = h + 'px';
        ci.style.minHeight = (h - 40) + 'px';
    }
    if (fr) fr.style.paddingTop = Math.round((h - 120) * 0.52) + 'px';
}
```

- **Front side** skips pixel-locking entirely — CSS `100dvh` handles it. No `document.documentElement.style.overflow` needed since CSS sets `overflow: hidden` on `html` permanently (mobile only).
- **Back side** pixel-locks `body.height` and `ci.minHeight` to `window.innerHeight` so long content scrolls within `.card` without ever exposing the inset strip.

### Why it works

1. **Front (short content):** `html` is `overflow: hidden` at `100dvh`, `.card` is `100dvh` — nothing scrolls, no inset strip.
2. **Back (short content):** JS locks `body.height` to exact pixel height — no scrolling, no strip.
3. **Back (long content):** Content overflows `.card`'s fixed height, so `.card` scrolls internally via `overflow-y: auto`. The scroll happens inside the body element, never reaching the WebView's html/inset layer.
4. **Desktop:** All changes are inside `@media (hover: none)`, so no visual change.

### Previous attempts that failed

| Approach | Result |
|---|---|
| `min-height: 100vh` on `.card` | Partially helps; adding even 1px too much causes a scrollbar |
| `min-height: 100dvh` | Fixes scroll issues but gap above bottom bar remains |
| `calc(100vh - Xpx)` with hardcoded values | Fragile, device-specific |
| Moving background to `body`/`html` | Mixed results |
| Resetting all margins/padding to 0 | Doesn't eliminate the inset area |

## AnkiMobile CSS Custom Properties

AnkiMobile injects CSS custom properties as **inline styles** on `<html>`:

```html
<html style="--top-inset: 0px; --bottom-inset: 114px;">
```

These are set by native iOS code via a `setInsets()` function. The default stylesheet also defines:

```css
html {
    --top-inset: 74px;   /* iPad default */
    --bottom-inset: 100px;
    --io-header: 24px;   /* image occlusion header */
}
```

The inline style values override the defaults at runtime. Observed values:
- **iPhone**: `--bottom-inset: 114px`
- **iPad**: `--bottom-inset: 100px`

### Important caveats

- **Not dynamic**: `--bottom-inset` is set once on card load. It does **not** update when the user toggles the bottom bar on/off mid-review via gestures — it stays the same value either way.
- **Disabling in preferences works**: If the user turns off the bottom bar entirely in AnkiMobile preferences, the inset is removed.
- **Cannot be overridden**: The native `setInsets()` sets inline styles (highest specificity). Even JS changes to the variable don't affect the actual `WKWebView` content insets, which are iOS-level, not CSS-level.
- **`env(safe-area-inset-bottom)` is useless**: Returns `0px` because AnkiMobile doesn't use `viewport-fit=cover` in its viewport meta tag, and template authors can't change it.

### Using `--bottom-inset` in card CSS

You can use the variable to subtract the inset space from layout calculations:

```css
/* Example: shrink card height to account for the bottom bar inset */
.card { height: calc(100dvh - var(--bottom-inset, 0px)); }
```

The `var(--bottom-inset, 0px)` fallback ensures it resolves to `0px` on platforms that don't set the variable (desktop Anki, AnkiDroid, AnkiWeb).

AnkiMobile's own default CSS uses these variables for image occlusion layout:

```css
#image-occlusion-container {
    max-height: calc(100vh - var(--top-inset) - var(--bottom-inset) - var(--io-header));
}
```

### Platform detection classes

AnkiMobile also injects classes on `<html>` for platform-specific CSS:

```html
<html class="webkit safari mobile iphone ios js">  <!-- iPhone -->
<html class="webkit safari mobile ipad ios js">    <!-- iPad -->
```

The `mobile` class is shared with AnkiDroid. The `iphone`/`ipad` classes are AnkiMobile-only.

## App-Level Fix (Pending)

- dae (Damien Elmes) is also working on an app-level fix tied to **migrating the reviewing screen to Svelte and sandboxing the WebView** ([GitHub #3871](https://github.com/ankitects/anki/issues/3871)).
- Our CSS/JS workaround fully eliminates the strip in the meantime and should be safe to keep even after the app-level fix lands.

## Sources

- [Anki Forums: Empty area between image and bottom bar](https://forums.ankiweb.net/t/empty-area-between-image-and-bottom-bar-wastes-screen-real-estate-ankimobile/62258)
- [GitHub #3871: Migrate reviewing screen to Svelte](https://github.com/ankitects/anki/issues/3871)
