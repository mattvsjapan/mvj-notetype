# Audio-Only Spacer Refactor

This document is a map for refactoring how audio buttons are vertically positioned when they are the only visible content on a card side. Multiple AI contexts should reference this document; each should implement one phase at a time and verify before moving on.

**Files involved:**
- `note-types/mvj/css.css` (~2500 lines)
- `note-types/mvj/front.html` (~1010 lines)
- `note-types/mvj/back.html` (~1700 lines)

**Start from the clean HEAD commit** (`6e704a9`). If working code already exists with partial changes, `git checkout HEAD -- note-types/mvj/css.css note-types/mvj/front.html note-types/mvj/back.html` first.

---

## 1. What This Card Is

An Anki flashcard template for Japanese vocabulary. Each card can show: a target word, sentence, image, pitch accent graph, bilingual/monolingual definitions, and audio buttons. Every piece of content is independently togglable via CSS custom properties (`--word-text`, `--sentence-text`, `--image`, etc.). The template supports two writing modes: horizontal (default) and vertical/tategaki.

The card looks like a physical flashcard — it's only as tall as its content needs, except audio-only cards get extra breathing room so they don't look unnaturally small.

---

## 2. DOM Structure

### Front side

```
.card-inner                     ← outer container, has padding, border, max-width
  .front                        ← front wrapper
    .audio-row                  ← flex row of audio buttons (word + sentence)
      .audio-item[data-audio="word"]
      .audio-item[data-audio="sentence"]
    #raw-word                   ← hidden raw data container
    #raw-sentence               ← hidden raw data container
    #raw-image                  ← hidden raw data container
    .front-content              ← flex column: word, sentence, image for front display
      h1.target-word
      p.sentence
      .image-wrap
```

### Back side

Anki injects `{{FrontSide}}` inside `.back`, creating a nested `.card-inner > .front` that gets dissolved:

```
.card-inner                     ← outer container (same element, re-rendered)
  .back                         ← back wrapper, display: flex column
    .card-inner                 ← inner (from FrontSide) → display: contents
      .front                   ← from FrontSide → display: contents
        .audio-row             ← visible on desktop if has front-side buttons
        .front-content         ← visible if has [data-side="front"] children
    .answer                    ← flex column: all back-side content
      .word-column
        .word-pitch-group
          h1.target-word
          .pitch-graph
        .image-wrap            ← only exists if {{Image}} field is populated
      p.sentence
      .audio-row-bottom        ← back-side audio (always used on mobile)
      .divider
      p.def
      .jp-def-section
```

Key CSS rules that dissolve the FrontSide nesting:
```css
.back > .card-inner { display: contents; }           /* line 1112 */
.back > .card-inner::before,
.back > .card-inner::after { display: none; }         /* line 1113-1114 */
.back .front { display: contents; }                   /* line 1115 */
```

Because of `display: contents`, the effective flex children of `.back` are: `.audio-row`, `.front-content`, and `.answer` (plus hidden raw containers which have `display: none` inline).

---

## 3. Card Height Model

Understanding how the card gets its height is critical — spacers only work if there's height to distribute.

### Desktop (`@media (hover: hover)`)

- `.card` has `padding: 20px`, `min-height: auto`
- `.card-inner` has `padding: 40px clamp(20px, 6vw, 44px)`, `max-width: 580px`
- **No min-height on `.card-inner` or `.front`** — the card wraps its content
- For audio-only front: the card height is just `card-inner padding (40+40) + audio-row padding (48) + buttons (~44px) + audio-row margin (48)` ≈ 220px
- **Spacers collapse to zero on desktop** because there's no extra height — the card is exactly as tall as needed. This is intentional; the padding/margin on `.audio-row` provides the "roomy" look.

### Desktop tategaki

- `.tategaki .card-inner` has `height: min(calc(100vh - 80px), 668px)` — a **definite height**
- `.tategaki .front` gets `height: 100%`
- **Spacers are NOT used on desktop tategaki.** Although the container has a definite height, desktop tategaki audio-only buttons should remain top-aligned (their natural position). Spacer rules are scoped to `@media (hover: none)` only.

### Mobile phone (`@media (hover: none)`)

- `.card-inner` has `min-height: calc(100dvh - 40px - var(--bottom-inset, 0px) + 35px + 1px)` — roughly fills the screen
- `.front` needs to stretch to fill this min-height for spacers to work

### Mobile tategaki

- `.tategaki .card-inner` has `height: calc(100dvh - max(40px, var(--bottom-inset, 0px) + 7px))`
- `.tategaki .front` has `height: 100%`

### iPad (`@media (hover: none) and (min-width: 768px)`)

- `.card-inner` min-height capped at `650px`
- Tategaki: `height: min(668px, calc(100dvh - ...))`

---

## 4. Current Positioning (Original Code — What to Remove)

Currently, audio-only positioning uses hardcoded viewport calculations in 3 places:

### A. CSS padding-top on `.front` (non-tategaki mobile)

Three platform-specific rules, all inside `@media (hover: none)`:

```css
/* iOS — line 524-526 */
html:not(.tategaki) .front:not(:has(.front-content [data-side="front"])) {
    padding-top: calc((100dvh - var(--bottom-inset, 0px) + 35px - 120px) * 0.52);
}

/* Android — line 541-543 */
.android:not(.tategaki) .front:not(:has(.front-content [data-side="front"])) {
    padding-top: calc((100dvh - 120px) * 0.52);
}

/* iPad — line 555-557, inside @media (hover: none) and (min-width: 768px) */
html:not(.tategaki) .front:not(:has(.front-content [data-side="front"])) {
    padding-top: 354px;
}
```

### B. CSS margin-top on tategaki `.front .audio-row`

Three blocks:

```css
/* iOS mobile — line 2007-2012 */
.tategaki .front .audio-row {
    margin-top: min(
        calc((100dvh - var(--bottom-inset, 0px) - 120px) * 0.52),
        calc(100dvh - max(40px, var(--bottom-inset, 0px) + 7px) - 88px - 260px)
    );
}

/* Android mobile — line 2013-2018 */
.android.tategaki .front .audio-row {
    margin-top: min(
        calc((100dvh - 120px) * 0.52),
        calc(100dvh - 388px)
    );
}

/* iPad — line 2026-2028 */
.tategaki .front .audio-row {
    margin-top: calc((min(668px, ...) - 120px) * 0.52);
}
```

### C. CSS padding-top on tategaki `.audio-row-bottom` (back side)

Three blocks:

```css
/* iOS mobile — line 2066-2073 */
.tategaki .audio-row-bottom {
    padding-top: min(
        calc((100dvh - var(--bottom-inset, 0px) - 120px) * 0.52),
        calc(100dvh - max(40px, ...) - 88px - 260px)
    );
}

/* Android mobile — line 2074-2079 */
.android.tategaki .audio-row-bottom { ... }

/* iPad — line 2082-2084 */
.tategaki .audio-row-bottom { padding-top: calc(...); }
```

### D. JS in front.html — `lock()` function

Inside the `lock()` IIFE near line 219-221 of front.html:
```javascript
if (fr && !fr.querySelector('.front-content [data-side="front"]')) {
    fr.style.paddingTop = isTablet ? '354px' : Math.round((h - bi - 120) * 0.52) + 'px';
}
```

This sets paddingTop via inline style before `data-side` attributes exist. It's a timing workaround — `lock()` runs immediately, but `data-side` is stamped later by the main script block.

### E. JS in front.html — "Adjust front padding" block

Near line 981-996 of front.html, a correction that runs AFTER `data-side` is stamped:
```javascript
if (window.matchMedia('(hover: none)').matches) {
    var fc = document.querySelector('.front-content');
    var fr = document.querySelector('.front');
    if (fc && fr && fr.style.paddingTop) {
        if (fr.querySelector('.front-content [data-side="front"]')) {
            fr.style.paddingTop = '';  // clear — not audio-only
        } else {
            var contentH = fc.offsetHeight;
            if (contentH > 0) {
                var curPad = parseInt(fr.style.paddingTop) || 0;
                fr.style.paddingTop = Math.max(0, curPad - contentH) + 'px';
            }
        }
    }
}
```

This clears the padding if front-content has visible items, or reduces it if `.front-content` has residual height (empty elements taking space).

---

## 5. The Spacer Approach (What to Add)

Replace all of the above with flex `::before` / `::after` pseudo-elements using `flex-grow` ratios.

### How it works

Make the container a flex column. Add `::before` and `::after` pseudo-elements. Give them `flex-grow` values. They absorb available space in the specified ratio, pushing the audio content to the desired vertical position.

```
┌─────────────────────┐
│ ::before (flex-grow) │  ← absorbs space above
├─────────────────────┤
│    audio buttons     │  ← actual content
├─────────────────────┤
│ ::after  (flex-grow) │  ← absorbs space below
└─────────────────────┘
```

- **Desktop:** `flex-grow: 1` / `flex-grow: 1` → centered (1:1 ratio). On non-tategaki desktop, spacers collapse to zero because there's no extra height — visual is unchanged.
- **Mobile:** `flex-grow: 2` / `flex-grow: 1` → two-thirds down (2:1 ratio) for thumb reach.

### Key selectors

Audio-only front (non-tategaki):
```
html:not(.tategaki) :not(.back) > .card-inner > .front:not(:has(.front-content [data-side="front"]))
```
This existing selector pattern already distinguishes audio-only from content-on-front. It relies on `data-side="front"` being set by JS.

Audio-only back: Requires JS detection → sets `data-audio-only` attribute on `.back`.

---

## 6. Implementation Phases

**Do one phase at a time. Verify visually before moving to the next.**

### Phase 1: Non-tategaki front (CSS only)

**What to change in `css.css`:**

1. **Remove** the three `padding-top` rules (sections A above):
   - Line 524-526 (iOS, inside `@media (hover: none)`)
   - Line 541-543 (Android, inside same media query)
   - Line 555-557 (iPad, inside `@media (hover: none) and (min-width: 768px)`)

2. **Add** new spacer rules. Place them right before the "FRONT — centered audio" comment (currently line 1016). They go OUTSIDE any media query (base rules), with a mobile override inside `@media (hover: none)`:

```css
/* Audio-only front: flex spacer positioning */
html:not(.tategaki) :not(.back) > .card-inner > .front:not(:has(.front-content [data-side="front"])) {
    display: flex;
    flex-direction: column;
    align-items: center;
}
html:not(.tategaki) :not(.back) > .card-inner > .front:not(:has(.front-content [data-side="front"]))::before,
html:not(.tategaki) :not(.back) > .card-inner > .front:not(:has(.front-content [data-side="front"]))::after {
    content: '';
    flex-grow: 1;
}
```

The base rules give 1:1 (centered). On desktop, the spacers collapse (no extra height), so the visual is identical to current.

For mobile, `.front` needs to stretch to fill `.card-inner`. Currently `.card-inner` is a block container, so `min-height: 100%` on `.front` won't resolve against it. The cleanest fix: make `.card-inner` a flex column for this specific case so `.front` can use `flex: 1`:

```css
@media (hover: none) {
    html:not(.tategaki) .card-inner:not(:has(> .back)) {
        display: flex;
        flex-direction: column;
    }
    html:not(.tategaki) .card-inner:not(:has(> .back)):not(:has(.front-content [data-side="front"])) {
        padding: clamp(20px, 6vw, 44px);
    }
    html:not(.tategaki) :not(.back) > .card-inner > .front:not(:has(.front-content [data-side="front"])) {
        flex: 1;
    }
    html:not(.tategaki) :not(.back) > .card-inner > .front:not(:has(.front-content [data-side="front"]))::before {
        flex-grow: 2;
    }
    html:not(.tategaki) :not(.back) > .card-inner > .front:not(:has(.front-content [data-side="front"])) .audio-row {
        padding-top: 0;
        margin-bottom: 0;
    }
}
```

**NOTE (learned in implementation):** The original `.card-inner` selector used nested `:has()` (`:has(> .front:not(:has(...)))`) which silently fails in iOS WebKit — see Hazard H. Simplified to `:not(:has(> .back))` which applies flex to all front-side cards. Safe because only audio-only `.front` gets `flex: 1`. Also: `.card-inner` padding equalized for audio-only (Hazard J), and `.audio-row` padding/margin zeroed (Hazard I).

**Why making `.card-inner` flex is safe here:** Its `::before` and `::after` pseudo-elements are `position: absolute` (for grain/shimmer effects), so they don't become flex items. The `.card-inner > *` rule (`position: relative; z-index: 1`) is fine on flex items.

3. **Remove** the JS in `front.html` — both the `lock()` paddingTop line (section D) and the "Adjust front padding" block (section E). These are no longer needed because the CSS spacer rules handle positioning declaratively.

**TIMING HAZARD:** The CSS selector `:not(:has(.front-content [data-side="front"]))` evaluates before JS stamps `data-side` attributes. This means the spacer layout briefly activates for ALL cards on initial render, then deactivates when `data-side="front"` gets set. This is the same behavior as the original CSS `padding-top` rules, and the same timing gap that the removed JS code was compensating for. In practice, this is not visible because Anki clients paint after JS execution. If it becomes visible on slow devices, the fix would be to add a JS guard that sets `data-side` earlier (in the `lock()` function), but do NOT attempt this until there's evidence of a real problem.

**Verify Phase 1:**
- Desktop, audio-only front: buttons sit in upper half of a compact card with padding (same as before)
- Mobile phone, audio-only front: buttons at ~2/3 down the screen
- iPad, audio-only front: buttons at ~2/3 down within the 650px card
- Desktop/mobile with content on front (word, sentence, image): NO visual change. The spacer rules must not match; the existing content-on-front flex layout must still work.

---

### Phase 2: Tategaki front (CSS only)

**What to change in `css.css`:**

1. **Remove** the three tategaki `margin-top` rules (section B above):
   - Line 2007-2012 (iOS mobile `.tategaki .front .audio-row`)
   - Line 2013-2018 (Android mobile)
   - Line 2026-2028 (iPad)

2. **Add** spacer rules for tategaki audio-only front. Place them in the tategaki section, after the existing `.tategaki .front .audio-row` base rules (around line 1975 area).

The approach: switch `.front` to `writing-mode: horizontal-tb` for audio-only. This normalizes the flex axis so `flex-direction: column` means top-to-bottom, and spacers work identically to non-tategaki. This is the same pattern used by the existing image-only tategaki front (lines 1953-1977 of the original file).

**IMPORTANT: All rules must be inside `@media (hover: none)`.** Unlike non-tategaki desktop (where spacers collapse because there's no extra height), tategaki desktop has a definite height on `.card-inner`, so spacers would NOT collapse — they'd center the buttons. Desktop tategaki audio-only buttons should remain top-aligned (their natural position), so spacers must be mobile-only.

**IMPORTANT: `.audio-row` had `order: 1` in tategaki** (from `.tategaki .front .audio-row` base rule). During Phase 2 this was changed to `order: -1` (audio-first ordering). Pseudo-elements default to `order: 0`, so you must set explicit `order` values to bracket the audio-row: `::before` gets `order: -2`, `::after` gets `order: 0`.

**IMPORTANT: `.front-content` has `height: 100%` in tategaki** (from `.tategaki .card-inner:not(:has(> .back)) .front-content`). Even when empty (audio-only case), it's a flex child that consumes the full container height, preventing spacers from distributing space. It must be set to `display: none` in the audio-only context.

**IMPORTANT: `.audio-row` has `margin-left: 16px`** (added in Phase 2 for column spacing when content is present). This must be zeroed for audio-only. A base (non-media-query) rule is needed for desktop, and the mobile spacer rule also zeroes it.

```css
/* Tategaki audio-only front: zero margin when audio is alone */
.tategaki :not(.back) > .card-inner:not(:has(> .back))
    .front:not(:has(.front-content [data-side="front"])):not(:has(.image-wrap[data-side="front"])) .audio-row {
    margin-left: 0;
}

/* Tategaki audio-only front: flex spacers push buttons ~2/3 down on mobile */
@media (hover: none) {
    .tategaki :not(.back) > .card-inner:not(:has(> .back))
        .front:not(:has(.front-content [data-side="front"])):not(:has(.image-wrap[data-side="front"])) {
        writing-mode: horizontal-tb;
        flex-direction: column;
        flex-wrap: nowrap;
        align-items: center;
    }
    .tategaki :not(.back) > .card-inner:not(:has(> .back))
        .front:not(:has(.front-content [data-side="front"])):not(:has(.image-wrap[data-side="front"]))::before {
        content: '';
        flex-grow: 2;
        order: -2;
    }
    .tategaki :not(.back) > .card-inner:not(:has(> .back))
        .front:not(:has(.front-content [data-side="front"])):not(:has(.image-wrap[data-side="front"]))::after {
        content: '';
        flex-grow: 1;
        order: 0;
    }
    .tategaki :not(.back) > .card-inner:not(:has(> .back))
        .front:not(:has(.front-content [data-side="front"])):not(:has(.image-wrap[data-side="front"])) .audio-row {
        margin-top: 0;
        margin-left: 0;
        padding-top: 0;
        margin-bottom: 0;
    }
    .tategaki :not(.back) > .card-inner:not(:has(> .back))
        .front:not(:has(.front-content [data-side="front"])):not(:has(.image-wrap[data-side="front"])) .front-content {
        display: none;
    }
}
```

The `:not(:has(.image-wrap[data-side="front"]))` guard is critical — without it, this conflicts with the existing image-only tategaki layout.

**Additional changes made during Phase 2** (beyond original scope but affecting codebase state for later phases):
- `.tategaki .front .audio-row` order changed from `1` to `-1` (audio-first), `margin-left: 16px` added
- Mobile tategaki: `.tategaki .front .audio-row { margin-top: auto; margin-bottom: 0; }` (bottom-align audio when content present)
- `html.tategaki { direction: rtl; }` — was `:has(.back)` only, now applies to front too (enables RTL scroll on front)
- `.tategaki .card-inner:not(:has(> .back)) { overflow: visible; }` — enables scroll-end spacing on front
- `.tategaki .card-inner::before { left: -20px; clip-path: ... }` — was back-only, now both sides
- Image-only front: `gap: 0`, `flex-wrap: nowrap`, `margin-bottom: 0` on audio-row, mobile `order: 1` flip
- `clearLastMargin` script: removed tategaki override that forced marker onto audio-row; now also runs for tategaki audio-only

**Verify Phase 2:**
- Desktop tategaki, audio-only front: buttons top-aligned (UNCHANGED — spacers are mobile-only)
- Mobile tategaki, audio-only front: buttons at ~2/3 down
- Tategaki with content (word, sentence, etc.): NO change
- Tategaki image-only front: NO change (the `:not(:has(.image-wrap))` guard protects this)

---

### Phase 3: Non-tategaki back audio-only (CSS + JS) ✓

This phase adds a new capability that didn't exist before: when the back of a card has nothing visible except audio buttons, position them like the front audio-only case.

**What was changed in `back.html`:**

1. Audio-only detection IIFE added right before "Trigger reveal animations" comment. Sets `data-audio-only` on `.back` when no content is visible. Variables `targetEl`, `graphEl`, `sentEl`, `answerEl` are already in scope from `_renderBack()`.

2. Empty `.answer` collapse block added after `clearLastMargin(.answer)`. When `.answer` has no visible content (height ≤ 2px) AND front content exists, collapses `.answer` and runs `clearLastMargin(.back)` to clear `.audio-row`'s margin. Guarded by `hasFrontContent` to preserve breathing room on audio-only backs.

3. `clearLastMargin` in `front.html` updated to recursively flatten `display: contents` (was only one level deep, needed two for `.back > .card-inner(contents) > .front(contents) > .audio-row`).

**What was changed in `css.css`:**

Spacer rules placed right after Phase 1 front spacers (cohesive audio-only section). Base rules outside media query, mobile overrides inside `@media (hover: none)`.

Key rules added:
- `.card-inner:has(> .back[data-audio-only])` → flex column (so `.back` can stretch via `flex: 1`)
- `.back[data-audio-only]::before/::after` → spacers (1:1 base, 2:1 on mobile)
- `.back[data-audio-only] .front-content` → `display: none`
- `.back[data-audio-only] .audio-row` → `padding: 48px 0 0; margin-bottom: 48px` (desktop breathing room, matching front)
- Mobile: `.audio-row` padding/margin zeroed, `.audio-row-bottom` margin zeroed, `.card-inner` padding equalized
- Divider rule tightened: only shows when back has visible content (definitions OR word/graph/sentence/image)

**Additional changes made during Phase 3** (beyond original scope but affecting codebase state for Phase 4):
- Phase 1 bug fix: `.card-inner:not(:has(> .back))` mobile rules scoped with `:not(.back) >` to prevent inner `.card-inner` (from FrontSide) from losing `display: contents` on mobile (Hazard R)
- `clearLastMargin` made recursive for `display: contents` flattening
- Divider rule for `.back:has(.front-content [data-side="front"])` now requires visible back content (definitions or content elements) — prevents divider showing when only audio buttons are below it
- `.answer` collapse logic added for "front content + empty answer" case — handles ghost `.answer` (0-1px height) that steals `clearLastMargin` targeting

**Verify Phase 3:** ✓
- Back with content (word, definitions, etc.): NO change — `data-audio-only` is not set ✓
- Back audio-only on desktop: buttons in compact card with padding (same look as front) ✓
- Back audio-only on mobile: buttons at ~2/3 mark ✓
- Back audio-only on iPad: buttons at ~2/3 within 650px card ✓
- Word on front + audio-only back: divider hidden, no extra padding below audio ✓
- Front side: NO change ✓

---

### Phase 4: Tategaki back audio-only (CSS only)

**This is the trickiest phase. Read all hazards before implementing.**

Phase 4 depends on Phase 3's JS detection being in place (`data-audio-only` attribute on `.back`).

**What to change in `css.css`:**

1. **Do NOT remove** the three tategaki `.audio-row-bottom` padding-top rules (section C). They apply to ALL tategaki `.audio-row-bottom` usage, not just audio-only. They position the audio column when the back has content (near the sentence). **Only override them for `[data-audio-only]`.**

2. **Add** spacer rules scoped to `.back[data-audio-only]`. The approach (same as Phase 2): switch to `writing-mode: horizontal-tb` so `flex-direction: column` works top-to-bottom.

**CRITICAL: Scope to mobile only (`@media (hover: none)`).** Phase 2 learned that desktop tategaki has a definite height on `.card-inner`, so spacers would actively center buttons. **ASK THE USER** whether desktop tategaki back audio-only buttons should be top-aligned (like front) or centered. Do NOT assume — the front and back may have different requirements.

**CRITICAL: Multiple elements have `height: 100%` that will consume spacer space.** This was the #1 debugging issue in Phase 2. On the back, the following tategaki elements have `height: 100%`:
- `.tategaki .answer` → `height: 100%` — Must override to `height: auto`
- `.tategaki .back .front-content` → `height: 100%` — `.front-content` is dissolved from `.front` via `display: contents` and becomes a direct flex child of `.back`. Must set `display: none` or `height: auto`
- `.tategaki .audio-row-bottom` → `height: 100%` — Must override to `height: auto`
- `.tategaki .divider` → `height: 100%` — Already hidden for audio-only by existing CSS rule, but verify

**CRITICAL: Check `order` values.** Phase 2's worst bug was pseudo-elements rendering in the wrong position due to `order` on the target element. In `.back`'s flex context (after `display: contents` dissolves `.front`):
- `.audio-row`: `display: none` in tategaki back — not a concern
- `.audio-row-bottom`: `order: -3` (base) or `order: -5` (when `data-zone="front"`)
- `.divider`: `order: -4`
- `.sentence`: `order: -3` (in tategaki `.answer` context — but this is inside `.answer`, not `.back`)
- `.front-content`: no explicit order (defaults to `order: 0`)
- `.answer`: no explicit order (defaults to `order: 0`)

**WAIT** — `.audio-row-bottom` is INSIDE `.answer`, not a direct child of `.back`. Its `order: -3` affects its position within `.answer`, not within `.back`. The direct flex children of `.back` in audio-only are: `.front-content` (order 0, dissolved), `.answer` (order 0), plus `::before`/`::after` (order 0). DOM order should work. But **verify this by reading the actual DOM structure and CSS before implementing.**

```css
/* Tategaki audio-only back */
.tategaki .back[data-audio-only] {
    writing-mode: horizontal-tb;
    flex-direction: column;
    align-items: center;
}
.tategaki .back[data-audio-only]::before,
.tategaki .back[data-audio-only]::after {
    content: '';
    flex-grow: 1;
}
/* QUESTION: Should this be mobile-only like Phase 2? Ask the user. */
@media (hover: none) {
    .tategaki .back[data-audio-only]::before {
        flex-grow: 2;
    }
}
.tategaki .back[data-audio-only] .answer {
    height: auto;
    writing-mode: horizontal-tb;
}
.tategaki .back[data-audio-only] .audio-row-bottom {
    height: auto;
    padding-top: 0;
    margin: 0;
    order: 0;
}
/* .front-content dissolved from .front — may need collapsing */
.tategaki .back[data-audio-only] .front-content {
    display: none;
}
```

**Additional properties to check/zero on `.audio-row-bottom`:**
- `margin: 0 0 0 24px` (base rule) → must zero to `margin: 0`
- `height: 100%` → must set `height: auto`
- `padding-top: min(calc(...))` (mobile rules) → must set `padding-top: 0`
- `will-change: transform` → probably fine but verify no layout side effects
- `writing-mode: horizontal-tb` → already set on the base rule, should be fine

**About the `.divider`:** The existing rule `.tategaki .back:not(:has(.front-content [data-side="front"])):not(:has(.audio-row-bottom[data-zone="front"])) .divider { display: none; }` should hide the divider for audio-only backs. Verify this matches — if `.audio-row-bottom` has `data-zone="front"`, the divider would still show. In that case, add an override: `.tategaki .back[data-audio-only] .divider { display: none; }`.

**About the clip-path on `.card-inner:has(> .back)`:** The back-side `.card-inner` uses `clip-path: inset(0 30% 0 30%)` for the reveal animation, then `clip-path: none` after `.tate-expand` class is added. This should not affect audio-only layout since it's a visual clip, not a layout constraint. But if buttons appear clipped during animation, that's why.

**Verify Phase 4:**
- Tategaki back with content: audio column positioned correctly next to sentence (UNCHANGED from before)
- Tategaki back audio-only on desktop: **verify with user** — centered or top-aligned?
- Tategaki back audio-only on mobile: buttons at ~2/3 down
- Tategaki back audio-only on iPad: buttons at ~2/3 within 668px card

---

## 7. Hazards & Landmines

### A. `display: contents` on `.front` and inner `.card-inner`

On the back side, `.front` has `display: contents`, which means `.front::before` and `.front::after` don't render. You CANNOT put spacer pseudo-elements on `.front` for the back side. The spacers must go on `.back` instead.

### B. `.card-inner::before` and `::after` are for visual effects

`.card-inner::before` is a grain texture overlay. `.card-inner::after` is a glass shimmer. Both are `position: absolute` with `inset: 0`. They do NOT become flex items when `.card-inner` becomes a flex container. This is safe.

However, on the back side, the inner `.card-inner` (from FrontSide) has its `::before` and `::after` explicitly set to `display: none` (line 1113-1114). This is also safe.

### C. Making `.card-inner` flex conditionally

When we add `display: flex; flex-direction: column` to `.card-inner` for audio-only cases, this changes how `.card-inner` sizes its children. The `.card-inner > *` rule (`position: relative; z-index: 1`) applies to `.front` or `.back` and is compatible with flex. But verify that nothing else inside `.card-inner` breaks.

### D. Timing of `data-side` attributes

The CSS selector `:not(:has(.front-content [data-side="front"]))` depends on `data-side` being set by JS. On the front side, `data-side` is set by the main script block AFTER `lock()` runs. This means:

1. `lock()` runs → no `data-side` yet → CSS thinks it's audio-only → spacer rules activate
2. Main script runs → sets `data-side="front"` on visible items → CSS re-evaluates → spacers deactivate for content cards

The brief period where spacers are wrongly active is typically not visible (Anki paints after JS). The old code had the same timing issue and compensated with the `lock()` JS padding + later correction. If visual flicker appears on slow devices, the fix is to set `data-side` earlier (in `lock()`), NOT to add more JS padding hacks.

### E. The tategaki `.audio-row-bottom` padding-top rules are NOT audio-only

These rules (section C, lines 2066-2084) apply to ALL tategaki `.audio-row-bottom` elements, even when the back has full content. They position the audio column so buttons align vertically near the sentence. Do NOT delete them thinking they're audio-only — they're general tategaki layout rules. Only add `[data-audio-only]` overrides that zero them out.

### F. `.word-pitch-group` display:none logic

CSS hides `.word-pitch-group` when both children are hidden:
```css
.word-pitch-group:has(> .target-word[data-show="off"]):has(> .pitch-graph[data-state="empty"]) {
    display: none;
}
```
If the Word field is empty but `--word-text` is not off, `data-show` is never set. The `<h1>` exists but is empty. The JS detection must check `textContent.trim()` in addition to `data-show` to handle this case.

### G. Image may not exist in DOM

The back template uses `{{#Image}}...{{/Image}}` around `.answer .image-wrap`. If the Image field is empty, the element doesn't exist at all. The JS detection must handle `querySelector` returning `null`.

### H. Nested `:has()` fails in iOS WebKit

**Confirmed in Phase 1.** The selector `.card-inner:not(:has(> .back)):has(> .front:not(:has(.front-content [data-side="front"])))` — `:has()` inside `:not()` inside `:has()` — silently fails to match in iOS Safari/WKWebView. `getComputedStyle` showed `display: block` instead of the expected `flex`.

**Fix used:** Simplify to `.card-inner:not(:has(> .back))` (apply flex to all front-side cards on mobile). This is safe because `.front` only gets `flex: 1` for audio-only via a separate rule, so content cards are unaffected.

**Rule for later phases:** Keep `:has()` nesting to one level max. If you need to scope `.card-inner` conditionally, either use a simpler selector or stamp a data attribute via JS.

### I. `.audio-row` padding/margin must be zeroed for spacer-positioned cards

The existing `.audio-row` has `padding: 48px 0 0; margin-bottom: 48px` (desktop breathing room). On mobile with spacers, this extra padding conflicts with the flex-grow positioning. Phase 1 added a zero-out rule scoped to audio-only fronts on mobile. Later phases should do the same for any audio row positioned by spacers.

### J. `.card-inner` padding is uneven (40px top/bottom vs ~20px sides)

Base `padding: 40px clamp(20px, 6vw, 44px)` gives larger top/bottom than sides on mobile. For content cards, a separate rule reduces `padding-top` to 20px. For audio-only, Phase 1 equalizes all sides with `padding: clamp(20px, 6vw, 44px)`. Later phases may need the same treatment.

### K. Source order matters

CSS specificity for many of these rules is identical (they use similarly-weighted selectors). Rules win by source order. When adding new rules, placement matters. The spacer rules should go BEFORE platform-specific overrides and AFTER base layout rules.

### L. Tategaki elements have non-zero `order` values

**Confirmed in Phase 2.** Pseudo-elements default to `order: 0`. Any element with a non-zero `order` will render before or after them, breaking the expected `::before` → content → `::after` sandwich.

Known `order` values (after Phase 2 changes):
- `.tategaki .front .audio-row`: `order: -1` (changed from `1` in Phase 2)
- `.tategaki .audio-row-bottom`: `order: -3` (inside `.answer`, not directly in `.back`)
- `.tategaki .audio-row-bottom[data-zone="front"]`: `order: -5`
- `.tategaki .divider`: `order: -4`

**Rule:** When adding spacer pseudo-elements, ALWAYS check what `order` values exist on the target element and its siblings. Set explicit `order` on `::before`/`::after` to bracket the content. Use dump debugging (not guessing) if the layout doesn't match expectations.

### M. Tategaki elements with `height: 100%` consume spacer space

**Confirmed in Phase 2 — this was the #1 time-wasting bug.** Multiple tategaki elements have `height: 100%`. Even when empty or hidden-by-children, they remain flex children consuming the full container height, preventing spacers from distributing space.

Known elements with `height: 100%`:
- `.tategaki .card-inner:not(:has(> .back)) .front-content` → front side
- `.tategaki .back .front-content` → back side (dissolved from `.front`)
- `.tategaki .answer` → back side
- `.tategaki .audio-row-bottom` → back side (inside `.answer`)
- `.tategaki .divider` → back side

**Rule:** For every spacer implementation, identify ALL flex children of the container and check their `height` values. Any with `height: 100%` must be overridden to `height: auto` or `display: none` in the audio-only context.

### N. Desktop tategaki spacers must be mobile-only (unless verified otherwise)

**Confirmed in Phase 2.** Unlike non-tategaki desktop (where `.card-inner` has no min-height so spacers collapse to zero), tategaki desktop has a definite `height` on `.card-inner`. Spacers would actively position the buttons (e.g., centering with 1:1 ratio), which may not be desired.

**Rule:** Default to `@media (hover: none)` for tategaki spacer rules. If desktop behavior should differ from "top-aligned," explicitly confirm with the user before implementing.

### O. `margin-bottom: 48px` on `.front .audio-row` becomes visible when element position changes

**Confirmed in Phase 2.** The base `.front .audio-row` rule has `padding: 48px 0 0; margin-bottom: 48px`. These values are designed for the default non-tategaki horizontal layout. When elements are reordered or repositioned (e.g., audio-row moved to top via `order: -1`, or pushed to bottom via `margin-top: auto`), these margins/paddings become visible in new directions and create unexpected gaps.

**Rule:** When repositioning audio elements with spacers or order changes, always zero out `padding-top`, `margin-bottom`, and `margin-left` as appropriate.

### P. Use dump debugging, not guessing

**Learned painfully in Phase 2.** When computed styles show correct values but the layout is wrong, the issue is often in a property you didn't check (e.g., `order`, `height: 100%` on a sibling, `margin` from a base rule). `getComputedStyle` on pseudo-elements can show heights that don't match `getBoundingClientRect` positions.

**Rule:** When something doesn't work on the first try, immediately add JS dump debugging that outputs `getBoundingClientRect()` positions for all relevant elements, computed `order`, `display`, `height`, `margin`, and `flex` values. Copy-paste the output and diagnose from real data. Do NOT guess and iterate — this wastes time.

### Q. `rowSettle` animation overrides `.back .audio-row` padding

**Confirmed in Phase 3.** `.back .audio-row` has `animation: rowSettle 0.35s var(--ease) both`. The `@keyframes rowSettle { from { padding: 48px 0 0; gap: 40px; } }` animates FROM the front-side values to the back-side values. With `fill-mode: both`, the animation's keyframe values override CSS declarations in the cascade. `getComputedStyle` shows the animated value (48px), not the CSS declaration (`padding: 0`).

**Impact:** Even though `.back .audio-row { padding: 0 }` is declared, the animation forces `padding-top: 48px` until it completes. For audio-only backs this is handled by setting `padding: 48px 0 0` explicitly (matching the animation). For the "front content + empty answer" case, the animation runs its transition normally and the padding settles to 0.

**Rule:** When debugging unexpected padding/margin values on `.audio-row` in the back, always check whether an animation is overriding the computed style. Use `el.style.animation = 'none'` in dump debugging to test.

### R. Phase 1 `.card-inner:not(:has(> .back))` matches the INNER `.card-inner` on back

**Confirmed in Phase 3.** The Phase 1 mobile rule `html:not(.tategaki) .card-inner:not(:has(> .back))` was intended for the front-side `.card-inner`, but it also matches the inner `.card-inner` from FrontSide on the back (since that element's children are `.front` and raw containers, not `.back`). This rule has higher specificity than `.back > .card-inner { display: contents }`, so it overrides `display: contents` with `display: flex`, making the inner `.card-inner` visible as a dark rectangle.

**Fix applied:** Scoped both Phase 1 mobile `.card-inner` rules with `:not(.back) >` prefix: `html:not(.tategaki) :not(.back) > .card-inner:not(:has(> .back))`. This prevents matching the inner `.card-inner` (which IS a child of `.back`).

**Rule for Phase 4:** Any rule targeting `.card-inner` with `:not(:has(> .back))` must be scoped with `:not(.back) >` to avoid matching the FrontSide inner `.card-inner`.

### S. `.answer` has ghost height (0-1px) even when all children are hidden

**Confirmed in Phase 3.** When all `.answer` children are `display: none`, `.answer` itself (a flex container) can still have 0-1px of height. This makes it appear as the bottommost element in `.back`, causing `clearLastMargin` to target it instead of `.audio-row`.

- When `.answer` is 1px: `clearLastMargin(.back)` marks `.answer` as last, `.audio-row` margin preserved (good for audio-only, bad for content+audio case)
- When `.answer` is 0px: `clearLastMargin(.back)` skips it (zero height filtered), marks `.audio-row` as last, zeroes its margin via inline style (bad for audio-only — the inline `marginBottom: 0` overrides CSS `margin-bottom: 48px`)

**Fix applied:** Do NOT run `clearLastMargin(.back)` unconditionally. Only run it inside the answer-collapse block, guarded by `hasFrontContent`. For audio-only backs, the CSS breathing room margin is preserved.

**Rule for Phase 4:** Never run `clearLastMargin` on `.back` without checking whether it would inappropriately clear breathing-room margins. The front-side pattern (skipping `clearLastMargin` for audio-only) must be mirrored on the back.

### T. Divider visibility should check for actual back content

**Confirmed in Phase 3.** The original divider rule `html:not(.tategaki) .back:has(.front-content [data-side="front"]) .divider { display: block }` unconditionally shows the divider when front content exists. But if the back only adds audio buttons (no definitions, no back-side word/sentence/image), nothing appears below the divider, making it look orphaned.

**Fix applied:** Split into two selector groups — one checking definitions (`data-def-layout`/`data-def-text`), one checking content elements via `:has(.target-word:not([data-show="off"]):not(:empty), .pitch-graph:not([data-state="empty"]), .sentence:not([data-show="off"]):not(:empty), .image-wrap:not([data-show="off"]))`.

**Rule for Phase 4:** The tategaki divider rule may need similar treatment. Check `.tategaki .back:has(.front-content [data-side="front"])) .divider` (if it exists) and apply the same content-visibility guard.

### U. Line numbers shift between phases

Phases 1 and 2 added and removed CSS rules, shifting all line numbers in the file. **Do not rely on line numbers from this document.** Instead, search for the actual selectors or comments to find the right location. Read the surrounding context before editing.

---

## 8. Summary of What Gets Removed vs Added

### Removed from `css.css`

| Selector | Property | Scope | Phase |
|----------|----------|-------|-------|
| `.front:not(:has(...))` | `padding-top: calc(...)` | iOS mobile | 1 ✓ |
| `.android .front:not(:has(...))` | `padding-top: calc(...)` | Android mobile | 1 ✓ |
| `.front:not(:has(...))` | `padding-top: 354px` | iPad | 1 ✓ |
| `.tategaki .front .audio-row` | `margin-top: min(...)` | iOS mobile | 2 ✓ |
| `.android.tategaki .front .audio-row` | `margin-top: min(...)` | Android mobile | 2 ✓ |
| `.tategaki .front .audio-row` | `margin-top: calc(...)` | iPad | 2 ✓ |

**NOT removed** (kept for non-audio-only tategaki back):
| `.tategaki .audio-row-bottom` | `padding-top: ...` | All mobile tategaki | N/A |

### Removed from `front.html` (Phase 1)

| What |
|------|
| `lock()` paddingTop inline style |
| "Adjust front padding" correction block |

### Added to `css.css`

1. ✓ Non-tategaki front spacer rules (base + mobile override) — Phase 1
2. ✓ Tategaki front spacer rules (mobile-only + margin/order resets) — Phase 2
3. ✓ Non-tategaki back spacer rules (base + mobile override) — Phase 3
4. Tategaki back spacer rules (mobile-only + height/margin/padding resets) — Phase 4

### Added to `back.html` (Phase 3)

Audio-only back detection JS (sets `data-audio-only` on `.back`).

### Additional changes made during Phase 3 (beyond original scope)

These changed the codebase state and affect what Phase 4 will encounter:
- Phase 1 bug fix: `.card-inner:not(:has(> .back))` scoped with `:not(.back) >` (Hazard R)
- `clearLastMargin` in `front.html` made recursive for `display: contents` flattening
- Divider rule for `.back:has(.front-content [data-side="front"])` now requires visible back content
- `.answer` collapse + `clearLastMargin(.back)` logic for "front content + empty answer" case
- `.back[data-audio-only] .audio-row` gets desktop breathing room (`padding: 48px 0 0; margin-bottom: 48px`), zeroed on mobile

### Additional changes made during Phase 2 (beyond original scope)

These changed the codebase state and affect what Phases 3/4 will encounter:
- `.tategaki .front .audio-row` order changed `1` → `-1`, added `margin-left: 16px`
- Mobile: `.tategaki .front .audio-row { margin-top: auto; margin-bottom: 0; }`
- `html.tategaki { direction: rtl; }` — expanded from back-only to both sides
- `.tategaki .card-inner:not(:has(> .back)) { overflow: visible; }` — new
- `.tategaki .card-inner::before` scroll-end spacing — expanded from back-only to both sides
- Image-only front layout adjustments (gap, flex-wrap, order flip on mobile)
- `clearLastMargin` script changes (removed tategaki override, expanded to run for audio-only)
