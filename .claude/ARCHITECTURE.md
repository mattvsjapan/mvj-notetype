# Card Template Architecture Spec

This document is the current JS/CSS contract for the Japanese, Chinese, and
MVJ card templates. It describes the target state the templates should keep.

## Core Principle

JS decides what things are. CSS decides where they go.

JS populates content, creates audio items, and stamps semantic attributes.
CSS owns visibility, ordering, layout, typography, and responsive behavior.

## Data Attribute Catalog

### `data-audio`

Set on `.audio-item` elements in `.audio-row`, `.audio-row-bottom`, and details
audio clones.

| Value | Meaning |
| --- | --- |
| `word` | Word pronunciation audio |
| `sentence` | Sentence audio |
| `def` | Definition audio |

### `data-def-lang`

Set on MVJ definition text slots and definition audio items.

| Element | Values | Meaning |
| --- | --- | --- |
| `.def` | `mono`, `bi` | Stable language slot for text |
| `.audio-item[data-audio="def"]` | `mono`, `bi` | Audio language |

MVJ uses explicit mono/bi language state instead of a role abstraction.
Definition audio DOM order is created by JS from the final text state:
inline-language item first, toggled-language item second, hidden items last.

### `data-def-show`

Set on MVJ definition text slots.

| Value | Meaning |
| --- | --- |
| `inline` | Definition text is visible immediately |
| `toggle` | Definition text is revealed by `#def-toggle` |
| `hidden` | Definition text is hidden and its audio is side-off |

CSS uses this attribute to hide hidden definitions, hide toggled definitions
until `#def-toggle` is checked, and hide the whole definition section when no
slot is inline or toggled.

### `data-mono-state`

Set on `.answer` for MVJ.

| Value | Meaning |
| --- | --- |
| `unlocked` | `<!-- def-type="monolingual" -->` is present |
| `locked` | only `<!-- def-type="LOCKED_monolingual" -->` is present |
| `absent` | no monolingual block is present |

For bilingual predicates keyed on "mono is locked", `absent` behaves like
`locked`. For monolingual predicates keyed on "unlocked", `absent` is not
unlocked.

### `data-bi-state`

Set on `.answer` for MVJ.

| Value | Meaning |
| --- | --- |
| `present` | Bilingual definition exists |
| `absent` | Bilingual definition does not exist |

### Other shared attributes

| Attribute | Set on | Meaning |
| --- | --- | --- |
| `data-state="empty"` | content elements | No content was rendered, so CSS hides the element |
| `data-show="off"` | content elements | User setting hides this content |
| `data-side="front/back/off"` | front/back routed content and audio | Side visibility |
| `data-btn-off` | audio items | Hide button UI while keeping audio available to explicit code paths |

For definition audio, `data-side="off"` means either the corresponding
definition text slot is hidden or the original audio item has been moved to
details. Autoplay and hotkey selectors use this to skip hidden items.

## MVJ Definition Settings

### Main definition text

| Variable | Values | Default |
| --- | --- | --- |
| `--definition-text-mono` | `on`, `off`, `on when unlocked, otherwise off`, `on when unlocked, otherwise toggle` | `on when unlocked, otherwise toggle` |
| `--definition-text-bi` | `on`, `off`, `on when mono locked, otherwise off`, `on when mono locked, otherwise toggle` | `on when mono locked, otherwise toggle` |

The sole-item exception is preserved: if exactly one definition type exists and
that type would be hidden, JS forces it to `inline`. If both mono and bi exist
and both settings evaluate to `hidden`, both stay hidden.

### Definition autoplay

| Variable | Values | Default |
| --- | --- | --- |
| `--definition-autoplay-mono` | `on`, `on when unlocked`, `on when unlocked or on reveal`, `off` | `on when unlocked or on reveal` |
| `--definition-autoplay-bi` | `on`, `on when mono is locked`, `on when mono is locked or on reveal`, `off` | `on when mono is locked or on reveal` |

Back autoplay only considers `.audio-row` items that are not `data-side="off"`.
If `--details-definition-audio: on` moves definition audio into details, that
movement supersedes card-flip autoplay timing. Details reveal can then play the
details audio according to the same predicate, with `...or on reveal` variants
always playing on reveal.

### Definition audio buttons and text-play

| Variable | Values | Meaning |
| --- | --- | --- |
| `--definition-audio-buttons` | `on`, `fallback`, `off` | Button UI policy |
| `--definition-text-play` | `on`, `off` | Clickable definition text policy |

Audio elements are still created when definition audio exists. Button settings
hide controls; they do not remove audio from text-play or explicit hotkeys.

### Details definition settings

| Variable | Values | Default |
| --- | --- | --- |
| `--details-definition-text-mono` | `on`, `off` | `off` |
| `--details-definition-text-bi` | `on`, `off` | `off` |
| `--details-definition-audio` | `on`, `off` | `off` |

If both definition text slots move to details, the whole `.def-section` moves
so the toggle continues to work. If exactly one slot moves, that slot is forced
to `inline` before moving because it is no longer controlled by `.def-section`.

## MVJ Definition DOM

The MVJ back template uses stable language slots:

```html
<div class="def-section" id="def-section" style="--d:170">
  <div class="def" id="def-bilingual" data-def-lang="bi"></div>
  <input type="checkbox" id="def-toggle" class="def-toggle-input">
  <label for="def-toggle" class="def-toggle-label" onclick=""></label>
  <div class="def" id="def-monolingual" data-def-lang="mono"></div>
</div>
```

JS always renders bilingual text into `#def-bilingual` and monolingual text into
`#def-monolingual`. JS sets `data-def-show`; CSS handles visibility and order.

## CSS Ordering

### Audio rows

All audio rows use the same type order:

```css
.audio-item[data-audio="word"] { order: 0; }
.audio-item[data-audio="sentence"] { order: 1; }
.audio-item[data-audio="def"] { order: 2; }
```

Within definition audio items, flexbox falls back to DOM order. JS inserts
definition audio in final playback order, so no per-language CSS order is
needed.

### MVJ definition text

```css
.def[data-def-show="inline"] { order: 1; }
#def-toggle,
.def-toggle-label { order: 2; }
.def[data-def-show="toggle"] { order: 3; }
```

Hidden definition slots use `display: none`. Toggled slots are hidden until
`#def-toggle` is checked. The toggle UI hides automatically when no slot is in
`toggle` state.

## Details Ordering

MVJ details movement uses fixed anchors inserted at the start of the details
phase:

```text
word-text -> pitch-graph -> word-audio -> image -> sentence-text ->
sentence-audio -> def-mono-text -> def-bi-text -> def-section ->
def-audio -> notes-text
```

Text moves before text-play wiring. Audio moves after button hiding and bottom
row cloning, so details clones inherit `data-btn-off`, and mobile bottom-row
clones remain independent of later details movement.

## Hotkeys

MVJ uses `--hotkey-def-toggle` for `#def-toggle`. The definition audio hotkey
plays the first non-hidden definition audio item in DOM order and deliberately
bypasses `data-btn-off`; play-all does not bypass `data-btn-off`.
