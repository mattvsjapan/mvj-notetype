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
| MVJ | DONE | Most complex — 4 audio code paths, tategaki ordering, dual-def reversal. |

### Phase 3: Settings system
Add CSS-variable-driven settings for content on/off toggles and front/back positioning. Users edit CSS variables in `:root` to customize their cards. Front shows plain white text + furigana; back shows full pitch accent coloring. Split into two sessions: Session 1 (on/off flags) and Session 2 (front positioning + audio placement).

| Card | Status | Notes |
|------|--------|-------|
| Chinese | NOT STARTED | |
| Japanese | NOT STARTED | |
| MVJ | NOT STARTED | Session 1: on/off flags. Session 2: front positioning. Must work with tategaki. |

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

#### 2026-02-22 — MVJ card Phase 2

**Files modified:** `mvj/back.html`, `mvj/css.css`

**What changed in `back.html`:**
- Tagged native dual path (`makeNativeDefItem`): Added `defRole` and `defLang` parameters. Function now sets `data-def-role` and `data-def-lang` on the item. Call sites changed from conditional insertion order to consistent order (Bi-Def first, Mono-Def second) with role/lang attributes determined by `window.__monoUnlocked`.
- Tagged `[audio:]` dual path (`makeDefItem`): Same pattern — added `defRole` and `defLang` parameters, sets both data attributes. Call sites changed to consistent insertion order with ternary-driven attributes and audio element assignment.
- Bottom-row cloning: Removed `defItems`/`otherItems` separation and `defItems[1], defItems[0]` reversal. Now queries all `.audio-row .audio-item` directly. Clone creation copies all `data-*` attributes from the original item via attribute iteration.
- Simple paths (untagged single-def `[audio:]` and `[sound:]`): No changes — they already set `data-audio="def"` and `data-def-role` is correctly omitted for single-def items.

**What changed in `css.css`:**
- Added CSS `order` rules for `.audio-row-bottom` before the bottom audio row section (same as Chinese/Japanese cards).
- Replaced single `.tategaki .audio-row-bottom .audio-item[data-audio="def"] { order: 1; }` rule with explicit ordering for word (0), sentence (1), primary/single def (2), secondary def (3). Tategaki rules (specificity 0-4-0) override non-tategaki rules (0-3-0).

**What JS still does (unchanged):**
- All playback logic (`playSingle`, `playAll`, `playGroup`, `__playLockedDefAudio`, `__autoPlayDefAudio`)
- Toggle listeners, keyboard handlers
- Untagged and single-def audio paths (no `data-def-role` needed)
- Auto-play deferred via `setTimeout(fn, 0)`

**Gotchas:** None.

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

### The 3-touch pattern

Each setting follows the same implementation pattern:

1. **Define the CSS variable** in `:root`
2. **Read it in JS** and set a `data-*` attribute
3. **Write CSS rules** that respond to the attribute

This ensures:
- Users edit only CSS (`:root` variables) to change behavior
- JS only translates variables into attributes (no layout logic)
- CSS handles all visual consequences
- Tategaki and future modes just add their own CSS rules for the same attributes

### Settings catalog

| Variable | Values | Default | Description |
|----------|--------|---------|-------------|
| `--tategaki` | `on`, `off` | `off` | Vertical writing mode |
| `--word` | `front`, `back`, `off` | `back` | Target word placement or hidden |
| `--sentence` | `front`, `back`, `off` | `back` | Sentence placement or hidden |
| `--pitch-graph` | `on`, `off` | `on` | Pitch accent graph (always on back) |
| `--image` | `front`, `back` | `back` | Image placement |
| `--word-audio` | `front`, `back` | `front` | Word audio button placement |
| `--sentence-audio` | `front`, `back` | `front` | Sentence audio button placement |

### Setting interactions

- `--word: off` forces `--pitch-graph: off` (nothing to graph).
- `--pitch-graph` is always on the back, independent of `--word` position.
- Content on the front is rendered as plain white text + furigana only (no pitch accent coloring). This is intentional — pitch accent recall is part of the test, so accent colors are only revealed on the back.
- Content on the back always gets full pitch accent coloring regardless of the front setting.
- When content is positioned on the front, it appears on **both** sides — plain text on the front, colorized in `.answer` on the back.
- `.front-content` is hidden on the back via CSS to prevent duplication.

### CSS settings block

Located at the very top of `:root` in `css.css`, before design tokens:

```css
:root,
:root[class*=night-mode] {
    /* ═══════════════════════════════════════════════════════
       ⚙  SETTINGS — Change these to customize your cards.
       ═══════════════════════════════════════════════════════ */

    /* Layout */
    --tategaki: off;              /* on | off                  */

    /* Content — front, back, or off                          */
    --word: back;                 /* front | back | off        */
    --sentence: back;             /* front | back | off        */
    --pitch-graph: on;            /* on | off (always on back) */

    /* Media */
    --image: back;                /* front | back              */

    /* Audio buttons */
    --word-audio: front;          /* front | back              */
    --sentence-audio: front;      /* front | back              */

    /* ═══════════════════════════════════════════════════════ */

    /* Design tokens below — edit only if you know CSS        */
    --canvas: #0c0d12;
    ...
}
```

### What users see

| Setting | Front | Back |
|---------|-------|------|
| `--word: front` | plain word + furigana | colorized word + pitch graph |
| `--word: back` | — | colorized word + pitch graph |
| `--word: off` | — | — (pitch graph forced off) |
| `--sentence: front` | plain sentence + furigana | colorized sentence |
| `--sentence: back` | — | colorized sentence |
| `--sentence: off` | — | — |
| `--pitch-graph: on` | — | pitch graph |
| `--pitch-graph: off` | — | — |
| `--image: front` | image | image |
| `--image: back` | — | image |
| `--word-audio: front` | word audio button | word audio button |
| `--word-audio: back` | — | word audio button |
| `--sentence-audio: front` | sentence audio button | sentence audio button |
| `--sentence-audio: back` | — | sentence audio button |

Any combination of these settings is valid, including in tategaki mode.

---

## Phase 3 Design: Front/Back Content Positioning

### The core problem

Currently, front.html contains only audio buttons. All content (word, sentence, image) lives in back.html. For elements to appear on the front, their markup and rendering logic must be available in front.html.

The key insight: `{{FrontSide}}` carries front.html content into the back, so anything in front.html is available on both sides. But back.html content is never available on the front.

### Two content zones

The solution uses two independent content zones. Each zone has its own rendering and the back-side zone always renders everything. CSS hides the front zone on the back to prevent duplication.

#### front.html (after Phase 3)

```
.card-inner > .front
  .audio-row                    ← existing (word audio, sentence audio)
  .front-content                ← NEW
    .target-word                  (plain white text + furigana, no accent colors)
    .sentence                     (plain white text + furigana, no accent colors)
    .image-wrap                   ({{Image}})
  #raw-word        [hidden]     ← NEW: {{Word}} raw Mustache data for JS
  #raw-sentence    [hidden]     ← NEW: {{Sentence}} raw Mustache data for JS
  #raw-image       [hidden]     ← NEW: {{Image}} raw Mustache data for JS
```

The raw data containers (`#raw-word`, etc.) provide Mustache field values to front-side JS. They are always `display: none`. The front-content children are populated by JS only when their setting is `front`.

#### back.html (after Phase 3)

**No structural changes.** `.answer` continues to render all content with full pitch accent coloring:

```
.card-inner > .back
  {{FrontSide}}                 ← includes .front with .audio-row + .front-content
  .answer                       ← UNCHANGED
    .word-column
      .target-word                (colorized + furigana)
      .pitch-graph                (SVG)
      .image-wrap
    .sentence                     (colorized + furigana)
    .audio-row-bottom
    .def
    .jp-def-section
```

### Rendering contract

#### Front-side rendering (front.html)

The front-side renderer is intentionally simple — ~15-20 lines of JS:

1. Read settings via `getComputedStyle`
2. For content with setting = `front`: parse bracket notation (`食[た]べる＼`) into `<ruby>` tags. Strip pitch notation markers (`＼`, `{`, `}`, accents). Plain white text only — **no pitch accent parsing, no colorization, no pitch library**.
3. For content with setting = `back` or `off`: leave container empty
4. Stamp `data-side` on `.front-content` children and audio items
5. Skip autoplay for audio items with `data-side="back"`
6. Guard all front-content logic with `if (document.querySelector('.back')) return;`

#### Back-side rendering (back.html)

`_renderBack()` gains three on/off checks. No position-awareness needed — the back always renders everything:

- `--word: off` → `data-show="off"` on `.target-word`, skip pitch graph generation
- `--sentence: off` → `data-show="off"` on `.sentence`
- `--pitch-graph: off` → `data-state="empty"` on `.pitch-graph`, skip SVG generation

Everything else in `_renderBack()` is unchanged.

### CSS rules (Phase 3 additions)

```css
/* Front: hide back-only content and audio */
.front [data-side="back"]               { display: none; }
.front .audio-item[data-side="back"]    { display: none; }

/* Back: hide front-content entirely (answer has colorized versions) */
.back .front-content                     { display: none; }

/* Disabled elements (on/off toggle) */
[data-show="off"]                        { display: none; }
```

### Data attributes (Phase 3 additions)

| Attribute | Set on | Values | Set by |
|-----------|--------|--------|--------|
| `data-side` | `.front-content` children, `.audio-item` | `front`, `back` | front.html JS |
| `data-show` | `.target-word`, `.sentence` in `.answer` | `off` (or absent) | back.html `_renderBack()` |

These complement the existing `data-state="empty"` (used for pitch graph) and `data-def-layout` attributes.

---

## Phase 3 Implementation Checklist

Phase 3 is split into two sessions. Session 1 is back-side only (on/off flags). Session 2 adds front positioning. Each session is independently testable.

### Session 1: On/off flags + CSS settings block

Back-side only. No front.html changes. Users can turn elements off but cannot reposition them to the front yet.

**css.css:**
- [ ] Restructure `:root` — move `--tategaki` into a settings header block at the top, add `--word`, `--sentence`, `--pitch-graph`, `--image`, `--word-audio`, `--sentence-audio` with defaults and comments
- [ ] Add `[data-show="off"] { display: none; }` rule
- [ ] Verify `[data-state="empty"] { display: none; }` already exists (for pitch graph)

**back.html — `_renderBack()`:**
- [ ] Add `setting()` helper at top of render function
- [ ] Read `--word`, `--sentence`, `--pitch-graph`
- [ ] `--word: off` → stamp `data-show="off"` on `.target-word` in `.answer`, skip word rendering
- [ ] `--word: off` → force skip pitch graph generation (same as the existing empty-word-data code path)
- [ ] `--sentence: off` → stamp `data-show="off"` on `.sentence` in `.answer`, skip sentence rendering
- [ ] `--pitch-graph: off` → stamp `data-state="empty"` on `.pitch-graph`, skip SVG generation

**Testing Session 1:**
- [ ] Default settings (everything on/back) → card looks identical to pre-Phase-3
- [ ] `--word: off` → hides word and pitch graph on back
- [ ] `--sentence: off` → hides sentence on back
- [ ] `--pitch-graph: off` → hides pitch graph, word still visible
- [ ] `--word: off` + `--pitch-graph: on` → both hidden (word: off cascades)
- [ ] All above in tategaki mode
- [ ] All above on mobile

### Session 2: Front positioning + audio placement

Adds `.front-content` zone, furigana renderer, `data-side` stamping, and audio positioning.

**front.html — markup:**
- [ ] Add `.front-content` container inside `.front`, after `.audio-row`, with empty `.target-word`, `.sentence`, `.image-wrap`
- [ ] Add hidden raw data containers: `#raw-word` with `{{Word}}`, `#raw-sentence` with `{{Sentence}}`, `#raw-image` with `{{Image}}` (Mustache-conditional with `{{#Field}}...{{/Field}}`)

**front.html — JS:**
- [ ] Add `setting()` helper function (reads CSS variable, returns trimmed value or fallback)
- [ ] Add simple furigana renderer: parse `食[た]べる＼` → `<ruby>食<rt>た</rt></ruby>べる`, stripping pitch markers. Plain white text, no accent colors. ~15-20 lines.
- [ ] Add front-content population script (guarded with `if (document.querySelector('.back')) return`):
  - [ ] Read `--word`, `--sentence`, `--image` settings
  - [ ] If `--word: front` → render word into `.front-content .target-word` via furigana renderer
  - [ ] If `--sentence: front` → render sentence into `.front-content .sentence` via furigana renderer
  - [ ] If `--image: front` → populate `.front-content .image-wrap` from `#raw-image`
  - [ ] Stamp `data-side` on each `.front-content` child based on setting
- [ ] Audio item `data-side` stamping:
  - [ ] Read `--word-audio`, `--sentence-audio` settings
  - [ ] Stamp `data-side` on `.audio-item[data-audio="word"]`
  - [ ] Stamp `data-side` on `.audio-item[data-audio="sentence"]`
- [ ] Autoplay script: skip items with `data-side="back"`
- [ ] Height-locking: verify `.front-content` content doesn't break mobile padding/height calculations

**css.css:**
- [ ] `.front-content` base layout rules (spacing, font sizing for plain word/sentence)
- [ ] `.front [data-side="back"] { display: none; }`
- [ ] `.back .front-content { display: none; }`
- [ ] `.front .audio-item[data-side="back"] { display: none; }`
- [ ] `.front-content` styling for tategaki mode
- [ ] `.front-content` mobile responsive rules

**back.html:**
- [ ] No structural changes needed beyond Session 1. `.answer` always renders everything regardless of position settings.

**Testing Session 2:**
- [ ] Default settings → card identical to pre-Phase-3 (and post-Session-1)
- [ ] `--word: front` → plain word on front, colorized word + pitch graph on back
- [ ] `--sentence: front` → plain sentence on front, colorized on back
- [ ] `--image: front` → image on front and back
- [ ] `--word-audio: back` → no word audio on front, visible on back
- [ ] `--sentence-audio: back` → no sentence audio on front, visible on back
- [ ] Mixed: `--word: front` + `--sentence: back` + `--image: front`
- [ ] `--word: off` still works (from Session 1)
- [ ] All above in tategaki mode
- [ ] All above on mobile (height locking, bottom audio row)
- [ ] Front autoplay respects `data-side` (skips back-only audio items)
- [ ] Keyboard shortcuts still work on both sides

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
