# Card Template Architecture Spec

This document defines the target architecture for all card templates (Japanese, Chinese, MVJ). It is the source of truth for how JS and CSS interact. Any AI working on these cards should read this document first.

---

## Migration Status

### Phase 1: Data attributes for visibility, fonts, and definition layout
Replace all inline `style.display`, `style.fontFamily`, `style.lineHeight` with data attributes. Add corresponding CSS rules. No audio ordering changes.

| Card | Status | Notes |
|------|--------|-------|
| Chinese | DONE | Simplest card, no tategaki. Completed first. |
| Japanese | DONE | Similar to Chinese but has pitch graph. Completed second. |
| MVJ | DONE | Most complex. Has tategaki. Completed last. |

### Phase 2: Audio item factory and ordering
Consolidate all audio item creation into `createAudioItem()`. Add `data-def-role` and `data-def-lang` attributes. Simplify bottom-row cloning to copy without reordering. Add CSS `order` rules.

| Card | Status | Notes |
|------|--------|-------|
| Chinese | DONE | Data attributes on dual-def items, simplified bottom-row cloning, CSS ordering. |
| Japanese | DONE | No def audio — only added data-attr copying to bottom-row cloning and CSS order rules. |
| MVJ | NOT STARTED | Most complex — 4 audio code paths, tategaki ordering, dual-def reversal. |

### Phase 3: Settings system
Add CSS-variable-driven settings for front/back positioning of elements. Implement `data-position` attributes and corresponding CSS rules.

| Card | Status | Notes |
|------|--------|-------|
| Chinese | NOT STARTED | |
| Japanese | NOT STARTED | |
| MVJ | NOT STARTED | Must also work with tategaki layout. |

### Work log
Record what was done in each session so the next context window has a worked example.

#### 2026-02-22 — Chinese card Phase 1

**Files modified:** `chinese/back.html`, `chinese/css.css`

**What changed in `back.html`:**
- Line 311: `targetEl.style.display = 'none'` → `targetEl.setAttribute('data-state', 'empty')`
- Lines 327-356: Replaced entire definition branching block. Added `var answerEl = document.querySelector('.answer')` and refactored all five cases:
  - **bi-only**: Sets `data-def-layout="bi-only"` on answerEl, `data-font="jp"` on defEl if biIsJp. Removed `jpDefSection.style.display = 'none'` (CSS handles it).
  - **mono-only**: Sets `data-def-layout="mono-only"` on answerEl, `data-font="zh"` on defEl. Removed `jpDefSection.style.display = 'none'` and inline font/lineHeight.
  - **dual-mono**: Sets `data-def-layout="dual-mono"` on answerEl, `data-font="zh"` on defEl, `data-font="jp"` on jpDefEl if biIsJp. Removed inline font/lineHeight.
  - **dual-bi**: Sets `data-def-layout="dual-bi"` on answerEl, `data-font="jp"` on defEl if biIsJp. Removed inline font/lineHeight.
  - **none**: Sets `data-def-layout="none"` on answerEl. Removed `defEl.style.display = 'none'` and `jpDefSection.style.display = 'none'`.

**What changed in `css.css`:**
- Added data-attribute CSS block after `.jp-def::before` and before bottom audio row section:
  - `[data-state="empty"] { display: none; }` — hides empty elements
  - `[data-font="jp"]` — Japanese serif font with line-height 1.65
  - `[data-font="zh"]` — Chinese serif font with line-height 1.65
  - `.answer[data-def-layout="none"]` — hides both `.def` and `.jp-def-section`
  - `.answer[data-def-layout="bi-only"]` and `mono-only` — hides `.jp-def-section`

**What JS still does (content-only, unchanged):**
- Sets `innerHTML` on defEl and jpDefEl
- Sets `jpDefEl.className = 'def'` in dual-mono case
- Sets toggle label text to 'Bilingual' in dual-mono case
- Sets `window.__monoUnlocked` flag

**Gotchas:** None encountered. The Chinese card has no tategaki and no pitch graph, making it a clean migration.

#### 2026-02-22 — Japanese card Phase 1

**Files modified:** `japanese/back.html`, `japanese/css.css`

**What changed in `back.html`:**
- Line 113: Removed redundant `frontDiv.style.display = 'contents'` — CSS already handles this via `.back .front { display: contents; }`. Kept `classList.remove('front')` which deactivates `.front .target-word rt { opacity: 0 }` and `.front .target-word span { color: ... }` rules.
- Lines 129, 132, 135: `graphEl.style.display = 'none'` → `graphEl.setAttribute('data-state', 'empty')` in all three pitch graph empty paths (no SVGs produced, no accent data, no word data).
- Line 154: `defEl.style.display = 'none'` → `defEl.setAttribute('data-state', 'empty')` for empty definition.

**What changed in `css.css`:**
- Added `[data-state="empty"] { display: none; }` rule before the AnkiDroid section.

**What JS still does (content-only, unchanged):**
- Sets `innerHTML` on graphEl, sentEl, defEl
- Adds `.reveal`, `.no-accent` classes to frontWord
- Mirrors audio buttons to bottom row

**Gotchas:** None. Simpler than Chinese — no font switching, no `data-def-layout`, no bilingual/monolingual toggle.

#### 2026-02-22 — MVJ card Phase 1

**Files modified:** `mvj/back.html`, `mvj/css.css`

**What changed in `back.html`:**
- Lines 830, 833, 836: `graphEl.style.display = 'none'` → `graphEl.setAttribute('data-state', 'empty')` in all three pitch graph empty paths (no SVGs produced, no accent data, no word data).
- Lines 861–887: Replaced entire definition branching block. Added `var answerEl = document.querySelector('.answer')` and refactored all five cases:
  - **bi-only**: Sets `data-def-layout="bi-only"` on answerEl. Removed `jpDefSection.style.display = 'none'` (CSS handles it).
  - **mono-only**: Sets `data-def-layout="mono-only"` on answerEl, `data-font="jp"` on defEl. Removed `jpDefSection.style.display = 'none'` and inline font/lineHeight.
  - **dual-mono**: Sets `data-def-layout="dual-mono"` on answerEl, `data-font="jp"` on defEl. Removed inline font/lineHeight.
  - **dual-bi**: Sets `data-def-layout="dual-bi"` on answerEl. No font override needed.
  - **none**: Sets `data-def-layout="none"` on answerEl. Removed `defEl.style.display = 'none'` and `jpDefSection.style.display = 'none'`.

**What changed in `css.css`:**
- Added data-attribute CSS block after `.jp-def::before` and before bottom audio row section:
  - `[data-state="empty"] { display: none; }` — hides empty elements
  - `[data-font="jp"]` — Japanese serif font with line-height 1.65
  - `.answer[data-def-layout="none"]` — hides both `.def` and `.jp-def-section`
  - `.answer[data-def-layout="bi-only"]` and `mono-only` — hides `.jp-def-section`

**What JS still does (content-only, unchanged):**
- Sets `innerHTML` on defEl and jpDefEl
- Sets `jpDefEl.className = 'def'` in dual-mono case
- Sets toggle label text to 'Bilingual' in dual-mono case
- Sets `window.__monoUnlocked` flag
- All audio creation, cloning, playback, and keyboard handling unchanged

**Gotchas:** None. No `[data-font="zh"]` needed — MVJ only has JP monolingual definitions, never Chinese.

#### 2026-02-22 — Chinese card Phase 2

**Files modified:** `chinese/back.html`, `chinese/css.css`

**What changed in `back.html`:**
- Tagged native dual path (`makeNativeDefItem`): Added `defRole` and `defLang` parameters. Function now sets `data-def-role` and `data-def-lang` on the item. Call sites changed from conditional insertion order to consistent order (Bi-Def first, Mono-Def second) with role/lang attributes determined by `window.__monoUnlocked`.
- Tagged `[audio:]` dual path (`makeDefItem`): Same pattern — added `defRole` and `defLang` parameters, sets both data attributes. Call sites changed to consistent insertion order with ternary-driven attributes and audio element assignment.
- Bottom row cloning: Removed `defItems`/`otherItems` separation and `defItems[1], defItems[0]` reversal. Now queries all `.audio-row .audio-item` directly. Clone creation copies all `data-*` attributes from the original item via attribute iteration.

**What changed in `css.css`:**
- Added CSS `order` rules for `.audio-row-bottom` before the bottom audio row section:
  - `[data-def-role="secondary"]` → order 0
  - `[data-def-role="primary"]` and `:not([data-def-role])` → order 1
  - `[data-audio="word"]` → order 2
  - `[data-audio="sentence"]` → order 3

**What JS still does (unchanged):**
- All playback logic (`playSingle`, `playAll`, `playGroup`, `__playLockedDefAudio`, `__autoPlayDefAudio`)
- Toggle listeners, keyboard handlers
- Untagged and single-def audio paths (no `data-def-role` needed)

**Gotchas:** None. No top-row ordering needed — DOM order is already correct for desktop.

#### 2026-02-22 — Japanese card Phase 2

**Files modified:** `japanese/back.html`, `japanese/css.css`

**What changed in `back.html`:**
- Bottom-row cloning (lines 165-171): Added `data-*` attribute copying loop after creating the clone div. Iterates `origItem.attributes` and copies any attribute whose name starts with `data-` to the clone. No other changes — Japanese has no definition audio, so no `data-def-role`/`data-def-lang` attributes to add to audio items.

**What changed in `css.css`:**
- Added CSS `order` rules for `.audio-row-bottom` before the bottom audio row section:
  - `[data-audio="def"][data-def-role="secondary"]` → order 0
  - `[data-audio="def"][data-def-role="primary"]` and `:not([data-def-role])` → order 1
  - `[data-audio="word"]` → order 2
  - `[data-audio="sentence"]` → order 3

**What JS still does (unchanged):**
- All audio extraction, button creation, playback logic, keyboard handlers
- No `data-audio` attributes exist on Japanese audio items, so CSS order rules don't match anything yet

**Gotchas:** None. Simplest Phase 2 migration — no definition audio means no tagging needed, just future-proofing the clone path and CSS.

---

## Core Principle

**JS decides what things are. CSS decides where they go.**

JS sets semantic data attributes on elements. CSS reads those attributes to control visibility, ordering, positioning, and styling. JS never sets `style.display`, `style.order`, `style.fontFamily`, or any other layout/presentation property directly. JS never relies on DOM insertion order for visual positioning.

---

## Data Attribute Catalog

### `data-audio` — Audio item type

Set on: `.audio-item` elements in both `.audio-row` and `.audio-row-bottom`

| Value | Meaning |
|-------|---------|
| `word` | Word pronunciation audio |
| `sentence` | Sentence audio |
| `def` | Definition audio (single, or when only one type exists) |

### `data-def-role` — Definition audio priority

Set on: `.audio-item[data-audio="def"]` elements, only when two definition audio items exist (bilingual + monolingual)

| Value | Meaning |
|-------|---------|
| `primary` | Audio for the currently visible definition |
| `secondary` | Audio for the toggled/hidden definition |

When only one definition audio exists, omit this attribute entirely.

### `data-def-lang` — Definition audio language type

Set on: `.audio-item[data-audio="def"]` elements

| Value | Meaning |
|-------|---------|
| `bi` | Bilingual definition audio |
| `mono` | Monolingual definition audio |

### `data-font` — Font override for content elements

Set on: `.def`, `.jp-def` — any element whose font depends on its content language

| Value | Meaning |
|-------|---------|
| `jp` | Japanese serif (`'Noto Serif JP', 'Hiragino Mincho ProN', 'Yu Mincho', serif`) |
| `zh` | Chinese serif (`'Noto Serif TC', 'MOE', serif`) |
| (absent) | Use default font from CSS class |

### `data-state` — Element visibility state

Set on: any element that JS may need to show/hide based on data availability

| Value | Meaning |
|-------|---------|
| `empty` | Element has no content — CSS hides it |
| (absent) | Element is visible (default) |

### `data-def-layout` — Definition section configuration

Set on: `.answer` (the main answer container)

| Value | Meaning |
|-------|---------|
| `bi-only` | Only bilingual definition exists |
| `mono-only` | Only monolingual definition exists |
| `dual-bi` | Both exist; bilingual is primary (visible), monolingual is toggled |
| `dual-mono` | Both exist; monolingual is primary (visible), bilingual is toggled |
| `none` | No definitions |

This replaces the current pattern of JS individually hiding `#jp-def-section` and `#def-bilingual` via `style.display = 'none'`.

---

## The JS/CSS Contract

### JS is responsible for:

1. **Populating content** — setting `innerHTML` / `textContent` on elements
2. **Setting data attributes** — all attributes listed above
3. **Creating audio items** — building `.audio-item` elements via the factory function (see below)
4. **Cloning to bottom row** — mirroring `.audio-row` items to `.audio-row-bottom` (clone all items without reordering; copy all `data-*` attributes)
5. **Registering event handlers** — tap handlers, keyboard shortcuts, toggle listeners
6. **Managing audio playback** — play, pause, stop, sequencing, Web Audio API
7. **Triggering animations** — adding `.ri` class after content is ready

### JS must NEVER:

1. Set `style.display` on any element — use `data-state="empty"` instead
2. Set `style.fontFamily` or `style.lineHeight` — use `data-font` instead
3. Set `style.order` on any element — ordering is always CSS
4. Rely on `appendChild` order for visual positioning — always set `data-*` attributes and let CSS `order` properties handle it
5. Reorder items during bottom-row cloning — clone in DOM order, CSS handles the rest

### CSS is responsible for:

1. **Layout and ordering** — all `order` properties, `display`, `flex-direction`, etc.
2. **Visibility** — hiding `[data-state="empty"]` elements, showing/hiding based on `data-def-layout`
3. **Font selection** — mapping `data-font` values to font stacks
4. **Responsive adaptation** — mobile vs desktop, tategaki vs horizontal
5. **Animation definitions** — keyframes, durations, delays

---

## CSS Ordering Scheme

All `.audio-item` ordering uses CSS `order`. Items without an explicit `order` default to `0`.

### Non-tategaki: `.audio-row` (top, desktop)

Items appear in natural order. No CSS `order` overrides needed — word and sentence come from the HTML template, def items are appended by JS. Since we no longer rely on insertion order, define explicit values:

```
[data-audio="word"]                          → order: 0
[data-audio="sentence"]                      → order: 1
[data-audio="def"][data-def-role="primary"]  → order: 2
[data-audio="def"]:not([data-def-role])      → order: 2  (single def)
[data-audio="def"][data-def-role="secondary"]→ order: 3
```

### Non-tategaki: `.audio-row-bottom` (bottom, mobile)

Same ordering scheme as top row. The cloning process copies `data-*` attributes, so the same CSS rules apply.

```
[data-audio="def"][data-def-role="secondary"]→ order: 0
[data-audio="def"][data-def-role="primary"]  → order: 1
[data-audio="def"]:not([data-def-role])      → order: 1  (single def)
[data-audio="word"]                          → order: 2
[data-audio="sentence"]                      → order: 3
```

### Tategaki: `.audio-row-bottom` (vertical column, always visible)

The audio column displays vertically. Word and sentence at top, definitions below:

```
[data-audio="word"]                          → order: 0
[data-audio="sentence"]                      → order: 1
[data-audio="def"][data-def-role="primary"]  → order: 2
[data-audio="def"]:not([data-def-role])      → order: 2  (single def)
[data-audio="def"][data-def-role="secondary"]→ order: 3
```

### Content elements in `.answer` (tategaki only)

In tategaki, `.answer` uses `writing-mode: vertical-rl` with flex column. Elements need explicit ordering:

```
.audio-row-bottom → order: -4  (rightmost — first in R→L flow)
.sentence         → order: -3
.def              → order: -2
.jp-def-section   → order: -1
.word-column      → order: 0   (default)
```

---

## CSS Visibility Rules

```css
/* Hide empty elements */
[data-state="empty"] {
    display: none;
}

/* Font overrides */
[data-font="jp"] {
    font-family: 'Noto Serif JP', 'Hiragino Mincho ProN', 'Yu Mincho', serif;
    line-height: 1.65;
}

[data-font="zh"] {
    font-family: 'Noto Serif TC', 'MOE', serif;
    line-height: 1.65;
}

/* Definition layout variants */
.answer[data-def-layout="none"] .def,
.answer[data-def-layout="none"] .jp-def-section {
    display: none;
}

.answer[data-def-layout="bi-only"] .jp-def-section,
.answer[data-def-layout="mono-only"] .jp-def-section {
    display: none;
}
```

---

## Audio Item Factory

All audio items should be created through a single pattern. This replaces the current 4+ separate code paths.

```js
/**
 * Create an audio-item element with semantic attributes.
 * CSS handles all positioning via the data attributes.
 *
 * @param {string} type       - 'word' | 'sentence' | 'def'
 * @param {string} label      - Display label ('Word', 'Sentence', 'Bi-Def', etc.)
 * @param {Array}  buttons    - Array of replay-button <a> elements
 * @param {Object} [opts]     - Optional attributes
 * @param {string} [opts.defRole] - 'primary' | 'secondary' (only for def items when two exist)
 * @param {string} [opts.defLang] - 'bi' | 'mono'
 * @returns {HTMLElement}      The .audio-item element (caller appends to container)
 */
function createAudioItem(type, label, buttons, opts) {
    var item = document.createElement('div');
    item.className = 'audio-item bi';
    item.setAttribute('data-audio', type);
    if (opts && opts.defRole) item.setAttribute('data-def-role', opts.defRole);
    if (opts && opts.defLang) item.setAttribute('data-def-lang', opts.defLang);
    for (var i = 0; i < buttons.length; i++) {
        item.appendChild(buttons[i]);
    }
    var lbl = document.createElement('span');
    lbl.className = 'audio-label';
    lbl.textContent = label;
    item.appendChild(lbl);
    return item;
}
```

### Bottom row cloning

The cloning function mirrors all items from `.audio-row` to `#audio-row-bottom` without reordering:

```js
function mirrorToBottomRow(bottomRow) {
    var topItems = document.querySelectorAll('.audio-row .audio-item');
    for (var i = 0; i < topItems.length; i++) {
        var orig = topItems[i];
        var clone = document.createElement('div');
        clone.className = 'audio-item';

        // Copy all data attributes
        var attrs = orig.attributes;
        for (var a = 0; a < attrs.length; a++) {
            if (attrs[a].name.startsWith('data-')) {
                clone.setAttribute(attrs[a].name, attrs[a].value);
            }
        }

        // Clone buttons (with delegation to originals)
        var origBtns = orig.querySelectorAll('.replay-button');
        for (var j = 0; j < origBtns.length; j++) {
            // ... create mirror button, delegate tap to original ...
        }

        // Clone label
        var origLabel = orig.querySelector('.audio-label');
        if (origLabel) {
            var lbl = document.createElement('span');
            lbl.className = 'audio-label';
            lbl.textContent = origLabel.textContent;
            clone.appendChild(lbl);
        }

        bottomRow.appendChild(clone);
    }
}
```

The key difference from the current code: **no reordering, no separating defs from non-defs, no array reversal.** CSS `order` handles everything.

---

## Settings System

User-configurable settings live as CSS custom properties in `:root`. JS reads them and stamps the appropriate data attributes. CSS rules respond to those attributes.

### How to add a new setting

1. **Define the CSS variable** in `:root`:
   ```css
   --sentence-position: back;  /* "front" | "back" | "hidden" */
   ```

2. **Read it in JS** and set a data attribute:
   ```js
   var pos = getComputedStyle(document.documentElement)
       .getPropertyValue('--sentence-position').trim();
   sentenceEl.setAttribute('data-position', pos || 'back');
   ```

3. **Write CSS rules** for each value:
   ```css
   .front [data-position="back"],
   .front [data-position="hidden"] { display: none; }
   .back [data-position="front"],
   .back [data-position="hidden"] { display: none; }
   ```

This pattern ensures:
- Users edit only CSS (`:root` variables) to change settings
- JS only translates variables into attributes (no layout logic)
- CSS handles all visual consequences
- New layout modes (tategaki, future modes) just add their own CSS rules for the same attributes
- An AI implementing a new setting touches exactly three places: the CSS variable, the JS reader, and the CSS rules

### Current settings

| Variable | Values | Card(s) | Description |
|----------|--------|---------|-------------|
| `--tategaki` | `on`, `off` | MVJ | Vertical writing mode |

### Planned settings (examples)

| Variable | Values | Description |
|----------|--------|-------------|
| `--sentence-position` | `front`, `back`, `hidden` | Where the sentence appears |
| `--definition-position` | `front`, `back`, `hidden` | Where the definition appears |
| `--image-position` | `front`, `back`, `hidden` | Where the image appears |
| `--pitch-graph` | `on`, `off` | Show/hide pitch graph |
| `--autoplay-def` | `on`, `off` | Auto-play definition audio on reveal |

---

## Cross-Card Shared Code

The three cards (Japanese, Chinese, MVJ) share identical audio utility functions defined in `front.html`:

- `window.__audioSVG` — SVG template for replay buttons
- `window.__animateBtn()` — Button tap/click animation
- `window.__onTap()` — Touch/click handler with ghost-tap prevention
- `window.__extractAudio()` — Parse `[audio:]` tags from container
- `window.__adoptNativeAudio()` — Convert native `[sound:]` elements to styled buttons
- `window.__stopAllAudio()` — Stop all playback
- `window.__safePlay()` — Play with error recovery
- `window.__startPlaying()` — Track playing state on button
- `window.__freshPlay()` — Create disposable Audio element
- `window.__webAudioPlay()` — Web Audio API playback
- `window.__playMobile()` — Route to Web Audio or fallback

These are currently copy-pasted across all three `front.html` files. This spec does not require unifying them (Anki templates can't import shared files), but changes to these utilities should be applied to all three cards.

---

## Anki-Specific Constraints

These constraints affect all architectural decisions:

1. **No ES modules** — Anki templates run in a WebView with no module support. All code is inline `<script>` blocks.
2. **No literal `<!--` in `<script>`** — Anki's Mustache engine treats HTML comments as template directives even inside script tags. Use string concatenation (`'<' + '!--'`) when building regexes that match comment syntax.
3. **No synchronous audio on AnkiDroid back template** — When `[sound:]` tags are present, calling `audio.play()` synchronously during rendering blanks the WebView. Always wrap in `setTimeout(fn, 0)`.
4. **`[sound:]` vs `[audio:]`** — `[sound:]` is Anki's native tag, processed by the client. `[audio:]` is a custom tag parsed by our JS. Both must be supported.
5. **`{{FrontSide}}`** — The back template includes the front template via `{{FrontSide}}`. Front-side scripts run again on the back. Guard front-only code with `if (document.querySelector('.back')) return;`.
6. **Anki reuses the WebView** — Global state from previous cards persists. Always clean up (`window.__stopAllAudio()`, remove orphaned `<audio>` elements, disconnect observers).

---

## Migration Checklist

When refactoring a card to match this spec:

- [ ] Replace all `el.style.display = 'none'` with `el.setAttribute('data-state', 'empty')`
- [ ] Replace all `el.style.fontFamily = ...` with `el.setAttribute('data-font', 'jp'|'zh')`
- [ ] Replace all `el.style.lineHeight = ...` (handled by `[data-font]` CSS rules)
- [ ] Set `data-def-layout` on `.answer` instead of individually hiding def elements
- [ ] Set `data-def-role` and `data-def-lang` on definition audio items
- [ ] Use `createAudioItem()` factory for all audio item creation
- [ ] Simplify bottom-row cloning to copy all items + `data-*` attributes without reordering
- [ ] Add CSS `order` rules for `.audio-row`, `.audio-row-bottom`, and tategaki variants
- [ ] Add CSS rules for `[data-state]`, `[data-font]`, `[data-def-layout]`
- [ ] Verify all combinations: 0/1/2 def audio × mono-unlocked/locked × tategaki/non-tategaki × `[audio:]`/`[sound:]`
