# Text-as-Play-Button: Soft Background Pill

Card body text (word, sentence, definition) itself acts as a clickable play button. Hovering reveals a tinted pill behind the text; clicking plays the associated audio with a breathing glow animation.

## Visual Design

### Hover State
- Rounded rectangle (`border-radius: 6px`) behind the text fills with `--accent-soft` (rgba of accent at ~12% opacity)
- Subtle inset border: `box-shadow: inset 0 0 0 1px var(--accent-glow)`
- Text color shifts to `--accent-text`
- Cursor changes to pointer
- Transition: 250ms ease on background, color, box-shadow

### Playing State
- Same pill appearance as hover (accent-soft bg + inset border)
- Background brightness breathes in and out (1.6s ease-in-out infinite):
  - `--accent-soft` → `rgba(200, 128, 90, 0.20)` → back
- Text stays `--accent-text`
- `.playing` class added on click, removed when audio ends

### Idle State
- No visible decoration — text looks exactly as it does today
- Negative margins (`margin: -6px -4px`) cancel out the padding so idle text doesn't shift position

## Why This Variation

Five approaches were prototyped (see `mockup-text-play.html` and `mockup-text-play-tategaki.html`):

1. **Side-Line Reveal** — accent line on the reading-start edge. Clean but only marks the first column of multi-column text.
2. **Soft Background Pill** — chosen. See below.
3. **Opacity Lift + Glow** — per-glyph text-shadow. Subtle but hover state is too faint to clearly signal clickability.
4. **Top-Edge Bar** — horizontal bar above text. Feels disconnected from the text itself, more like a section divider.
5. **Per-Column Dots** — `text-decoration: underline dotted` on each column. Visually busy with multi-column text and the dotted→solid transition is jarring (not animatable).

The pill wins because:
- **Direction-agnostic** — background, box-shadow, and border-radius work identically in horizontal-tb and vertical-rl. No writing-mode adaptation needed.
- **Multi-column safe** — for text that wraps into multiple columns in tategaki, the pill encompasses all columns as one unit. No per-column issues.
- **Clear affordance** — the highlighted region makes the clickable target obvious, unlike glow-only approaches where the hover effect is too ambient.
- **Consistent with existing UI** — the switcher buttons in settings already use `--accent-soft` + `--accent-glow` for active state, so users already associate this visual pattern with interactivity.

## Tategaki Considerations

In `writing-mode: vertical-rl`, the pill naturally rotates with the text:
- Padding axes swap: more vertical padding (`6px 4px` instead of `2px 6px`) to match the taller, narrower columns
- Negative margins swap correspondingly (`-6px -4px`)
- Background, box-shadow, border-radius, and animations need zero changes
- Multi-column text (sentence wrapping into 3+ columns, definition into 2+) creates a wider pill — this looks natural as it groups the columns visually

## Implementation Notes

### CSS

```css
/* Base — always present, zero visual impact when idle */
.text-play {
  cursor: pointer;
  border-radius: 6px;
  padding: 2px 6px;      /* horizontal-tb */
  margin: -2px -6px;
  transition: background 250ms ease, color 250ms ease, box-shadow 250ms ease;
}

/* Tategaki override */
.tategaki .text-play {
  padding: 6px 4px;
  margin: -6px -4px;
}

/* Hover — desktop only */
@media (hover: hover) {
  .text-play:hover {
    background: var(--accent-soft);
    color: var(--accent-text);
    box-shadow: inset 0 0 0 1px var(--accent-glow);
  }
}

/* Playing */
.text-play.playing {
  background: var(--accent-soft);
  color: var(--accent-text);
  box-shadow: inset 0 0 0 1px var(--accent-glow);
  animation: text-play-breathe 1.6s ease-in-out infinite;
}

@keyframes text-play-breathe {
  0%, 100% { background: var(--accent-soft); }
  50%      { background: rgba(200, 128, 90, 0.20); }
}
```

### JavaScript

The click handler follows the same pattern as existing replay buttons:

```
click/tap on .text-play element
  → determine which audio source is associated (word, sentence, definition)
  → __stopAllAudio()
  → add .playing to the clicked element
  → play audio via existing __safePlay / __playMobile path
  → on audio end → remove .playing
```

For mobile (touch devices), use the existing `__onTap` handler with double-tap to stop. The `@media (hover: hover)` guard prevents sticky hover states on touch devices.

### Which elements get `.text-play`

- `.target-word` — plays word audio
- `.sentence` — plays sentence audio
- `.def` / `.jp-def` — plays definition audio (if audio exists for that definition)
- Only add the class when the corresponding audio field is populated; don't make text look clickable if there's nothing to play

### Interaction with existing replay buttons

The circular replay buttons in `.audio-row` / `.audio-row-bottom` / `.mid-audio-row` remain unchanged. Text-play is an additional way to trigger the same audio — both update the same playback state. When text is clicked:
- The replay button for that audio should also get `.playing` (visual consistency)
- When the replay button is clicked, the text should also get `.playing`
- `__stopAllAudio()` clears `.playing` from both text and buttons
