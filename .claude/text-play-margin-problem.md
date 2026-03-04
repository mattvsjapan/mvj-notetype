# The text-play margin problem

## The technique

`.text-play` creates a clickable pill around text by expanding the element's box with padding, then pulling it back with equal negative margins so the text doesn't shift:

```css
.text-play {
    padding: 2px 6px;
    margin: -2px -6px;
}
```

The pill is visually larger than the text, but the element occupies the same layout space as if it had no pill. This is a standard CSS trick.

## Why it keeps breaking

### 1. Margin shorthands clobber the compensation

`.sentence` sets `margin: 0 0 20px`. This shorthand resets all four margins, wiping out the `-2px -6px` from `.text-play`. Now the padding pushes the text inward with nothing to compensate. Every context that sets margins on a text-play element needs a "restore" rule to re-establish the correct negative margins:

```css
/* This rule exists solely to undo the damage from .sentence's shorthand */
.front-content .sentence.text-play {
    margin-top: -2px;
    margin-left: -6px;
    margin-right: -6px;
    margin-bottom: 14px;
}
```

### 2. Combinatorial explosion

The compensation values depend on multiple independent factors:

- **Ruby annotations**: `:has(ruby):not(.furigana-off)` needs `padding-top: 10px; margin-top: -10px` to encompass furigana
- **Layout context**: `.front-content` vs `.answer` have different base margins
- **Writing mode**: tategaki swaps which physical axis each margin affects
- **Furigana visibility**: `furigana-front`, `furigana-hidden`, `furigana-off` each need different padding
- **Flex stretch**: stretched flex children can't use negative cross-axis margins at all

Each combination potentially needs its own rule with its own padding/margin values. Adding a new feature or fixing one combination often clobbers another because the rules interact through CSS specificity in non-obvious ways.

### 3. Stretched flex children break the model

The technique assumes the element has a natural size determined by content. Negative margins extend the box beyond that natural boundary — harmless when the element is content-sized.

But with `align-self: stretch` in a flex container, the element fills its container. Negative margins now push it *past* the container bounds. The fix for this (`box-sizing: border-box` + zero margins) is fundamentally incompatible with the original technique — you can't zero the margins and also use them to compensate for padding. So a different approach is needed for stretched elements, adding another dimension to the combinatorial problem.

### 4. Physical properties vs writing modes

`margin-bottom: 14px` means "spacing below me" in horizontal layout. In `vertical-rl`, the same property means "shrink my inline extent by 14px." A rule written for horizontal layout silently does the wrong thing in vertical. Every text-play margin rule needs a tategaki counterpart, doubling the rule count and creating more specificity conflicts.

## The fix: decouple pill visuals from layout margins

The solution is to stop using margins for the pill expansion entirely. Instead, use a `::before` pseudo-element for the pill background:

```css
.text-play {
    position: relative;
    isolation: isolate;
}

.text-play::before {
    content: '';
    position: absolute;
    inset: -2px -6px;
    border-radius: 6px;
    z-index: -1;
    transition: background 600ms ease, box-shadow 600ms ease;
}

.text-play.playing::before {
    background: var(--accent-soft-bright);
    box-shadow: inset 0 0 0 1px var(--accent-glow);
}
```

This approach:

- **Eliminates margin conflicts**: The element's margins are purely about layout spacing. No padding/margin compensation pairs to keep in sync.
- **Works with flex stretch**: The pseudo-element extends beyond the element without affecting its layout box.
- **Works across writing modes**: `inset` properties on an absolutely-positioned element aren't affected by the parent's flex layout or writing mode in the same way.
- **Reduces rule count**: No "restore" rules needed. No per-context overrides for the pill. Ruby accommodation is just `inset-top: -10px` (or `inset-block-start`) on the pseudo-element.

This pattern already exists in the codebase for the WebKit sentence case (`css.css` ~line 2232), where it was introduced specifically to avoid the pill extending into empty furigana space. Generalizing it to all text-play elements would eliminate the class of margin bugs entirely.
