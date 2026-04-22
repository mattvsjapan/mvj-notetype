# iOS AudioContext dead after transition from legacy native-audio card

## Problem

On iPhone AnkiMobile, reviewing the Kaishi deck: a card using the **legacy MVJ note type** (plays audio via Anki's native `pycmd('play:...')` path) followed by a card using the **new MVJ note type** (plays audio via Web Audio `AudioContext`). The new card goes silent — autoplay emits no sound, replay buttons do nothing. Backing out to the deck browser and re-entering fixes it until the next legacy→new transition.

Only affects iPhone. Only affects legacy→new. New→new is fine. New→legacy is fine (legacy doesn't use `AudioContext` at all).

## Root cause

Two audio backends share one iOS `AVAudioSession`:

- Legacy MVJ (`note-types/_legacy/old-mvj/front.html`) — `pycmd('play:<filename>')` → AnkiMobile's native iOS player → takes the `AVAudioSession`.
- New MVJ (`note-types/mvj/front.html`) — Web Audio via a persistent `window.__audioCtx` + `__webAudioPlay` / `__playMobile`.

When AnkiMobile's native player grabs the session, iOS transitions the WebView's `AudioContext` to `"suspended"` or the non-standard `"interrupted"` state. The context does **not** auto-resume when the native player finishes. The WebView persists `window` across cards in the same review session, so the dead context carries over to the next card.

`__playMobile` at `note-types/mvj/front.html:673` branches on `audioCtx.state === 'running'` and takes the Web Audio path against a dead context → no sound.

### Why existing recovery didn't fire

- `__audioCtxVisHandler` (`note-types/mvj/front.html:191`) runs a full recovery (including the WebKit #263627 stall workaround), but only on `visibilitychange`. Card-to-card transitions inside a single review session don't fire `visibilitychange`.
- `__audioCtxTouchHandler` (`note-types/mvj/front.html:178`) only calls `resume()` when `state !== 'running'`, and requires a touch — autoplay fires from `setTimeout(0)` before any gesture.
- Initial suspend-check at `note-types/mvj/front.html:160` only runs at card-template execution and only handles `"suspended"` (not the stalled-running case), and a gestureless `resume()` can silently fail.

### Why backing out and re-entering fixes it

AnkiMobile tears down / hides the review WebView when returning to the deck browser. The WebView is either rebuilt on re-entry (fresh `AudioContext`) or `visibilitychange` fires (triggers `__audioCtxVisHandler` recovery).

## What we shipped (2026-04-22)

Listen for `AudioContext` `statechange` events, mark the context dirty on any transition away from `"running"`, and recover at the single playback bottleneck (`__playMobile`) before playing.

Applied identically to `note-types/mvj/front.html` and `note-types/chinese/front.html`. Back templates inherit the fix via the shared `__playMobile`.

### 1. Statechange listener at AudioContext creation

`note-types/mvj/front.html:164` (and `note-types/chinese/front.html:33`):

```javascript
if (!window.__audioCtxStateHandler) {
    window.__audioCtxStateHandler = function() {
        if (window.__audioCtx && window.__audioCtx.state !== 'running') {
            window.__audioCtxDirty = true;
        }
    };
    window.__audioCtx.addEventListener('statechange', window.__audioCtxStateHandler);
}
```

Guard mirrors existing `__audioCtxTouchHandler` / `__audioCtxVisHandler` pattern — prevents duplicate listeners when `{{FrontSide}}` re-executes on back side.

### 2. Recovery at `__playMobile` entry

`note-types/mvj/front.html:673` (and `note-types/chinese/front.html:456`):

```javascript
window.__playMobile = function(src, btn, scope) {
    if (scope === undefined) scope = window.__currentCardScope;
    if (!window.__isCardScopeActive(scope)) return Promise.resolve();
    function proceed() {
        if (window.__audioCtx && window.__audioCtx.state === 'running') {
            return window.__webAudioPlay(src, btn, window.__webAudioGen, scope);
        }
        var fa = window.__freshPlay(src, btn, scope);
        if (!fa) return Promise.resolve();
        window.__startPlaying(fa, btn);
        return new Promise(function(resolve) { fa.onended = resolve; });
    }
    if (window.__audioCtxDirty && window.__audioCtx) {
        return window.__audioCtx.suspend()
            .then(function() { return window.__audioCtx.resume(); })
            .then(function() { window.__audioCtxDirty = false; })
            ['catch'](function() {})
            .then(function() {
                if (!window.__isCardScopeActive(scope)) return;
                return proceed();
            });
    }
    return proceed();
};
```

**Key properties:**
- Healthy cards pay nothing — `__audioCtxDirty` is false, recovery branch skipped.
- Dirty cards pay one `suspend().then(resume)` cycle (tens of ms) before playback.
- On recovery **failure**, the flag stays set (not cleared in the catch) — next play retries recovery. The catch still lets `proceed()` run, so playback falls through to `__freshPlay` (native `<audio>`) for this attempt.
- All playback entry points (autoplay, replay buttons, text-play, hotkeys, back-side definition audio) converge at `__playMobile`, so one fix covers all of them.

### What's unchanged

- `__audioCtxVisHandler` — still handles app-background recovery including WebKit #263627 stall.
- `__audioCtxTouchHandler` — still catches gestureless-resume edge cases.
- `__webAudioGen`, `__currentCardScope`, `__freshPlay` fallback path — unchanged.

## Things to investigate if this doesn't work

Run a device test: Kaishi deck on iPhone, build a review queue with alternating legacy/new MVJ cards, confirm autoplay + replay button + text-play + keyboard hotkey all work after a legacy→new transition.

### If the new card is still silent

**First: check whether `statechange` actually fired.** Add a `console.log` inside `__audioCtxStateHandler` and in the dirty-flag branch of `__playMobile`. Look at AnkiMobile's remote debugger output.

- **If `statechange` never fires when AnkiMobile's native player takes the session:** WebKit doesn't expose the interruption through `AudioContext` events in this WebView. The whole Option 1 design is invalid. Fall back to one of:
  - **`navigator.audioSession` events** (WebKit-specific): listen for `interruptionbegin` / `interruptionend` if available. Spec-wise these aren't standardized but some WKWebView builds expose them.
  - **Unconditional recovery on card load:** accept the ~200ms hit per card. User has explicitly rejected this.
  - **Proactive dirty-flag from the legacy template:** modify `note-types/_legacy/old-mvj/front.html` to set `window.__audioCtxDirty = true` after every `pycmd('play:...')`. Requires users to re-install the old template.

- **If `statechange` fires but playback is still silent (context reports `"running"` but is stalled):** this is WebKit #263627 hitting on card transitions, not just on visibility changes. Add **lazy post-playback detection (Option 2)** to `__webAudioPlay`:

  ```javascript
  // Inside __webAudioPlay, after source.start():
  var t0 = window.__audioCtx.currentTime;
  setTimeout(function() {
      if (window.__audioCtx.state === 'running'
          && window.__audioCtx.currentTime === t0) {
          // Context is stalled — force dirty flag and let the next
          // __playMobile call run recovery. Also cancel this source
          // and restart via __freshPlay.
          window.__audioCtxDirty = true;
          try { source.stop(); } catch(e) {}
          window.__freshPlay(src, btn, scope);
      }
  }, 250);
  ```

  Cost: ~250ms of silence before the fallback kicks in, only on cards where the stall hits. Healthy cards unaffected.

- **If recovery runs but `suspend().then(resume)` doesn't unstick the context:** the `suspend()/resume()` cycle is a known WebKit workaround but isn't guaranteed. Try `window.__audioCtx.close().then(() => { window.__audioCtx = new AudioContext(); window.__audioCtxStateHandler(/* re-attach */); })`. This is destructive — any in-flight `AudioBufferSourceNode`s become invalid — so only do it as a last resort and after `__stopAllAudio`.

### If manual button taps work but autoplay doesn't

Autoplay fires from `setTimeout(0)` before any touch. If button taps succeed but autoplay fails, the recovery path needs to run *before* autoplay, not at the first `__playMobile` call. Check the order of operations in `note-types/mvj/front.html:1294-1302` (autoplay block). A fix would be to `await` a recovery check synchronously at the top of the autoplay block, which adds latency to every card — user has rejected this.

### If new→new cards now have audible latency

The recovery branch should only run when `__audioCtxDirty` is true. If healthy cards are taking the recovery path, something is setting the flag spuriously. Check:
- Does `statechange` fire during normal playback start/stop? It shouldn't in `"running"` → `"running"` cycles, but verify.
- Does `__stopAllAudio` trigger a statechange? Audit.

### Architectural alternative (last resort)

Drop the Web Audio path on iPhone entirely and always use `__freshPlay` (native `<audio>`). Sidesteps the whole WebKit #263627 class of bugs. Trade-off: loses `navigator.audioSession.type = 'playback'` + Web Audio combo that plays audibly through the iPhone mute switch. User has flagged this as **not an option** because per-card features (fine-grained autoplay control, no-autoplay audio via button, etc.) depend on the Web Audio path.

## References

- `.claude/ios-audiocontext-background.md` — sibling fix for the app background/foreground case (the `visibilitychange` handler this fix builds on).
- `.claude/ios-audio-latency.md` — intrinsic HTMLAudioElement latency on iOS; motivates keeping the Web Audio path.
- WebKit bug #263627 — `AudioContext` reports `"running"` while `currentTime` is frozen.
- iOS `AudioContext.state` can be `"interrupted"` (non-standard, WebKit-specific).
