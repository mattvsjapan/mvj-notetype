# Grid `auto-fit` rows don't work inside flex-grow containers

## The problem

`grid-template-rows: repeat(auto-fit, minmax(76px, auto))` with `grid-auto-flow: column` is meant to fill rows first, then wrap into new columns. But `auto-fit` needs a **definite height** to calculate how many rows fit.

A flex child with `flex-grow: 1; flex-basis: 0` does **not** have a definite height at the time the grid resolves `auto-fit`. This is a circular dependency: flex needs the grid's intrinsic size to allocate space, but the grid needs flex's resolved height to know how many rows to create.

Per the CSS spec ([MDN: repeat()](https://developer.mozilla.org/en-US/docs/Web/CSS/Reference/Values/repeat)):

> When auto-fill or auto-fit is given as the repetition number, and the grid container has a **definite** size or max size in the relevant axis, the number of repetitions is the largest possible positive integer that does not cause the grid to overflow. **Otherwise, the specified track list repeats only once.**

So `auto-fit` falls back to one repetition, the grid creates one row slot per item, and its intrinsic width calculation becomes bloated — pushing the parent wider than needed even though all items visually stack in one column.

Related CSSWG issues: [#1865](https://github.com/w3c/csswg-drafts/issues/1865), [#6777](https://github.com/w3c/csswg-drafts/issues/6777).

## Where this bit us

`.tategaki .mid-audio-row` inside `.tategaki .word-column`. The mid-audio-row is a grid with `auto-fit` rows and `grid-auto-flow: column`, but its height comes from `flex-grow: 1` in the word-column flex container. The bloated intrinsic width forces the word-column much wider than its content needs.

## Solutions

### 1. ResizeObserver (JS) — most robust

Let flex resolve the height, then set the row count from JS:

```js
const ROW_HEIGHT = 76;
const GAP = 12;
const observer = new ResizeObserver(([entry]) => {
  const height = entry.contentBoxSize[0].blockSize;
  const rows = Math.max(1, Math.floor((height + GAP) / (ROW_HEIGHT + GAP)));
  container.style.gridTemplateRows = `repeat(${rows}, minmax(${ROW_HEIGHT}px, auto))`;
});
observer.observe(container);
```

### 2. Flexbox column-wrap instead of grid

`flex-direction: column; flex-wrap: wrap` respects flex-resolved height for wrapping (same layout pass). Downsides: no grid-level alignment; known bug where container width doesn't grow to fit wrapped columns ([flexbugs #11](https://github.com/philipwalton/flexbugs)).

### 3. Hardcode the row count

Use `repeat(N, minmax(76px, auto))` with a known max. Extra empty rows are harmless with `grid-auto-flow: column`. Simplest but doesn't adapt to varying heights.

### 4. Writing-mode trick

Swap axes so `auto-fit` operates on width (which is definite). Only helps if the *width* is the unknown axis — doesn't apply when *height* is the flex-determined one.

### 5. Container query units (`cqh`)

Requires `container-type: size`, which itself demands a definite height. Same chicken-and-egg problem.
