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

**IMPORTANT: `.audio-row` has `order: 1` in tategaki** (from `.tategaki .front .audio-row` base rule). Pseudo-elements default to `order: 0`, so both `::before` and `::after` render before `.audio-row`. You must set explicit `order` values: `::before` gets `order: -1`, `::after` gets `order: 2`, so flex order is `::before` → `.audio-row` (order 1) → `::after`.

**IMPORTANT: `.front-content` has `height: 100%` in tategaki** (from `.tategaki .card-inner:not(:has(> .back)) .front-content`). Even when empty (audio-only case), it's a flex child that consumes the full container height, preventing spacers from working. It must be set to `display: none` in the audio-only context.

```css
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
        order: -1;
    }
    .tategaki :not(.back) > .card-inner:not(:has(> .back))
        .front:not(:has(.front-content [data-side="front"])):not(:has(.image-wrap[data-side="front"]))::after {
        content: '';
        flex-grow: 1;
        order: 2;
    }
    .tategaki :not(.back) > .card-inner:not(:has(> .back))
        .front:not(:has(.front-content [data-side="front"])):not(:has(.image-wrap[data-side="front"])) .audio-row {
        margin-top: 0;
        padding-top: 0;
        margin-bottom: 0;
    }
    .tategaki :not(.back) > .card-inner:not(:has(> .back))
        .front:not(:has(.front-content [data-side="front"])):not(:has(.image-wrap[data-side="front"])) .front-content {
        display: none;
    }
}
```

The `:not(:has(.image-wrap[data-side="front"]))` guard is critical — without it, this conflicts with the existing image-only tategaki layout (lines 1953-1977).

**Verify Phase 2:**
- Desktop tategaki, audio-only front: buttons top-aligned (UNCHANGED — spacers are mobile-only)
- Mobile tategaki, audio-only front: buttons at ~2/3 down
- Tategaki with content (word, sentence, etc.): NO change
- Tategaki image-only front: NO change (the `:not(:has(.image-wrap))` guard protects this)

---

### Phase 3: Non-tategaki back audio-only (CSS + JS)

This phase adds a new capability that didn't exist before: when the back of a card has nothing visible except audio buttons, position them like the front audio-only case.

**What to change in `back.html`:**

Add detection JS after all content rendering, right before the "Trigger reveal animations" comment (original line ~1667). The code must run AFTER all `data-show`, `data-state`, `data-def-layout`, and `data-def-text` attributes have been set.

```javascript
// Detect audio-only back — set attribute for CSS spacer positioning
(function() {
    var back = document.querySelector('.back');
    if (!back) return;

    // Check each content type using the same attributes the CSS uses to hide them.
    // Word: data-show="off" means hidden. Empty word with word-text on still has
    // no content, so also check textContent.
    var wordVisible = targetEl
        && targetEl.getAttribute('data-show') !== 'off'
        && targetEl.textContent.trim() !== '';

    // Pitch graph: data-state="empty" means hidden
    var graphVisible = graphEl && !graphEl.hasAttribute('data-state');

    // Sentence: data-show="off" means hidden; also check for empty content
    var sentVisible = sentEl
        && sentEl.getAttribute('data-show') !== 'off'
        && sentEl.textContent.trim() !== '';

    // Image: may not exist in DOM (Mustache conditional). If it exists,
    // data-show="off" means hidden.
    var imgEl = document.querySelector('.answer .image-wrap');
    var imgVisible = imgEl && imgEl.getAttribute('data-show') !== 'off';

    // Definitions: data-def-layout="none" means no definitions exist.
    // data-def-text="off" means definitions are configured off.
    var defVisible = answerEl
        && answerEl.getAttribute('data-def-layout') !== 'none'
        && answerEl.getAttribute('data-def-text') !== 'off';

    // Front-content items shown on front (they're repeated on the back)
    var frontContentVisible = !!document.querySelector(
        '.front-content [data-side="front"]'
    );

    var hasContent = wordVisible || graphVisible || sentVisible
                  || imgVisible || defVisible || frontContentVisible;

    if (!hasContent) {
        back.setAttribute('data-audio-only', '');
    }
})();
```

Variables `targetEl`, `graphEl`, `sentEl`, `answerEl` are already in scope — they're declared earlier in `_renderBack()`.

**What to change in `css.css`:**

Add rules near the back layout section (after line ~1140 area, near the existing `.back` flex rules):

```css
/* Audio-only back: spacer positioning */
html:not(.tategaki) .card-inner:has(> .back[data-audio-only]) {
    display: flex;
    flex-direction: column;
}
html:not(.tategaki) .back[data-audio-only] {
    flex: 1;
}
html:not(.tategaki) .back[data-audio-only]::before,
html:not(.tategaki) .back[data-audio-only]::after {
    content: '';
    flex-grow: 1;
}
@media (hover: none) {
    html:not(.tategaki) .back[data-audio-only]::before {
        flex-grow: 2;
    }
}
```

**How `.back` gets height:** Making the outer `.card-inner` a flex column lets `.back` use `flex: 1` to stretch to fill it. On desktop, `.card-inner` has no min-height, so `.back` wraps content and spacers collapse — same compact look as the front. On mobile, `.card-inner` has `min-height: ~100dvh`, so `.back` stretches and spacers have room.

**About back-side audio rows:** On the back, audio can appear in two places:
- `.audio-row` (from FrontSide, dissolved via `display: contents` on `.front`) — shows on desktop if it has front-side buttons
- `.audio-row-bottom` (inside `.answer`) — shows on mobile always; on desktop only when `.audio-row` has no front buttons

They never both show on desktop simultaneously. On mobile, only `.audio-row-bottom` shows (`.back .audio-row` is `display: none` on mobile — line 1098-1099). The spacers on `.back` center whichever one is visible.

**Verify Phase 3:**
- Back with content (word, definitions, etc.): NO change — `data-audio-only` is not set
- Back audio-only on desktop: buttons in compact card with padding (same look as front)
- Back audio-only on mobile: buttons at ~2/3 mark
- Back audio-only on iPad: buttons at ~2/3 within 650px card

---

### Phase 4: Tategaki back audio-only (CSS only)

**What to change in `css.css`:**

1. **Remove** the three tategaki `.audio-row-bottom` padding-top rules (section C above):
   - Line 2066-2073 (iOS mobile)
   - Line 2074-2079 (Android mobile)
   - Line 2082-2084 (iPad)

   **IMPORTANT:** These rules apply to ALL tategaki `.audio-row-bottom` usage, not just audio-only. They position the audio column when the back has content too (sentence, word, etc.). Removing them changes the tategaki back audio column position for ALL cards, not just audio-only ones.

   **This is the trickiest part of the refactor.** The tategaki `.audio-row-bottom` has `height: 100%` and uses `padding-top` to push its buttons down within the full-height column. For cards WITH content, the buttons should be top-aligned (near the sentence). For audio-only cards, they should be centered/two-thirds.

   **Therefore:** Do NOT remove these padding-top rules as a blanket change. Instead, only override them for audio-only:

```css
/* Tategaki audio-only back */
.tategaki .back[data-audio-only] {
    writing-mode: horizontal-tb;
    display: flex;
    flex-direction: column;
    align-items: center;
}
.tategaki .back[data-audio-only]::before,
.tategaki .back[data-audio-only]::after {
    content: '';
    flex-grow: 1;
}
@media (hover: none) {
    .tategaki .back[data-audio-only]::before {
        flex-grow: 2;
    }
}
.tategaki .back[data-audio-only] .audio-row-bottom {
    height: auto;
    padding-top: 0;
    margin: 0;
    order: 0;
}
.tategaki .back[data-audio-only] .answer {
    height: auto;
    writing-mode: horizontal-tb;
}
```

The `writing-mode: horizontal-tb` on `.back` switches the entire back to horizontal layout for audio-only. The overrides on `.audio-row-bottom` and `.answer` undo the tategaki-specific styles that assume vertical writing mode.

2. The tategaki front `.audio-row` margin-top rules (section B — removed in Phase 2) are pure front-side rules and can be safely removed. But the `.audio-row-bottom` padding-top rules (this phase) affect the back with content. **Only remove them if you're sure they can be replaced by the `[data-audio-only]`-scoped overrides above.**

   Actually, re-reading the original rules: they apply to `.tategaki .audio-row-bottom` unconditionally (not scoped to audio-only). They position the back-side audio column for ALL tategaki cards. So:
   - **Keep the original padding-top rules for non-audio-only tategaki back** (they position the audio column next to the sentence)
   - **Override to zero only for `[data-audio-only]`** (as shown above)

**Verify Phase 4:**
- Tategaki back with content: audio column positioned correctly next to sentence (UNCHANGED from before)
- Tategaki back audio-only on desktop: buttons centered
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

### L. Tategaki `.audio-row` has `order: 1`

**Confirmed in Phase 2.** `.tategaki .front .audio-row` has `order: 1` (for positioning in vertical writing mode). Pseudo-elements default to `order: 0`, so both `::before` and `::after` render *before* the audio-row in flex order, pushing buttons to the bottom. Fix: set explicit `order` on pseudo-elements (`::before` gets `order: -1`, `::after` gets `order: 2`) to bracket the audio-row.

**Rule for later phases:** When adding spacer pseudo-elements in tategaki, always check if the target element has an `order` property and set explicit `order` values on `::before`/`::after` accordingly.

### M. Tategaki `.front-content` has `height: 100%`

**Confirmed in Phase 2.** `.tategaki .card-inner:not(:has(> .back)) .front-content` has `height: 100%`. Even when empty (no `[data-side="front"]` children), it remains a flex child consuming the full container height, preventing spacers from distributing space. Fix: set `display: none` on `.front-content` in the audio-only context.

### N. Desktop tategaki spacers must be mobile-only

**Confirmed in Phase 2.** Unlike non-tategaki desktop (where `.card-inner` has no min-height so spacers collapse to zero), tategaki desktop has a definite `height` on `.card-inner`. Spacers would actively center the buttons, but the intended desktop behavior is top-aligned. All tategaki spacer rules must be inside `@media (hover: none)`.

---

## 8. Summary of What Gets Removed vs Added

### Removed from `css.css` (9 rules across 6 blocks)

| Location | Selector | Property | Scope |
|----------|----------|----------|-------|
| ~line 524 | `.front:not(:has(...))` | `padding-top: calc(...)` | iOS mobile |
| ~line 541 | `.android .front:not(:has(...))` | `padding-top: calc(...)` | Android mobile |
| ~line 555 | `.front:not(:has(...))` | `padding-top: 354px` | iPad |
| ~line 2007 | `.tategaki .front .audio-row` | `margin-top: min(...)` | iOS mobile |
| ~line 2013 | `.android.tategaki .front .audio-row` | `margin-top: min(...)` | Android mobile |
| ~line 2026 | `.tategaki .front .audio-row` | `margin-top: calc(...)` | iPad |

**NOT removed** (kept for non-audio-only tategaki back):
| ~line 2066-2084 | `.tategaki .audio-row-bottom` | `padding-top: ...` | All mobile tategaki |

### Removed from `front.html` (2 JS blocks)

| Location | What |
|----------|------|
| ~line 219 | `lock()` paddingTop inline style |
| ~line 981-996 | "Adjust front padding" correction block |

### Added to `css.css` (~50 lines)

1. Non-tategaki front spacer rules (base + mobile override)
2. Tategaki front spacer rules (base + mobile override + margin-top: 0)
3. Non-tategaki back spacer rules (base + mobile override)
4. Tategaki back spacer rules (base + mobile override + property resets)

### Added to `back.html` (~20 lines)

Audio-only back detection JS (sets `data-audio-only` on `.back`).
