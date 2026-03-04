# iOS AudioContext not resuming after app background/foreground

## Problem

On iOS AnkiMobile, when a user switches away from the app while reviewing a card and returns, audio no longer plays. Tapping audio buttons produces silence.

## Root cause

iOS suspends the WebView's `AudioContext` when the app is backgrounded. The context transitions to `"suspended"` or the non-standard `"interrupted"` state and does not automatically resume when the app returns to foreground.

Additionally, **WebKit bug #263627** means the context can report `state === "running"` while `currentTime` is actually frozen — so a naive `if (state !== 'running') resume()` check is insufficient.

## Why existing code didn't handle it

- The existing `touchend` safety net only fires on user interaction, so the first tap after returning may work (if the user taps an audio button), but autoplay fails silently.
- There was no `visibilitychange` listener to detect the foreground transition and proactively resume the context.

## What we tried

### Fix: `visibilitychange` listener (2026-02-25, branch `flexible-settings`)

Added a `visibilitychange` handler in all three front templates (chinese, japanese, mvj) immediately after the existing `__audioCtxTouchHandler` setup:

```javascript
if (!window.__audioCtxVisHandler) {
    window.__audioCtxVisHandler = function() {
        if (document.visibilityState !== 'visible' || !window.__audioCtx) return;
        if (window.__audioCtx.state !== 'running') {
            window.__audioCtx.resume()['catch'](function() {});
        } else {
            // Context may claim 'running' while stalled (WebKit bug #263627).
            var t = window.__audioCtx.currentTime;
            setTimeout(function() {
                if (window.__audioCtx && window.__audioCtx.state === 'running'
                    && window.__audioCtx.currentTime === t) {
                    window.__audioCtx.suspend().then(function() {
                        return window.__audioCtx.resume();
                    })['catch'](function() {});
                }
            }, 200);
        }
    };
    document.addEventListener('visibilitychange', window.__audioCtxVisHandler);
}
```

**Logic:**
1. On `visibilitychange` to `visible`, check the AudioContext state.
2. If `state !== 'running'` (suspended/interrupted), call `resume()`.
3. If `state === 'running'`, snapshot `currentTime`, wait 200ms, and check if it advanced. If frozen (WebKit bug), do a `suspend()` then `resume()` cycle to unstick it.

**Guard:** `if (!window.__audioCtxVisHandler)` follows the same pattern as the touch handler — prevents duplicate listeners when Anki re-evaluates the front template on card flip.

## Things to investigate if this doesn't work

- **`visibilitychange` may not fire on AnkiMobile:** If AnkiMobile's WKWebView doesn't dispatch `visibilitychange` when backgrounding/foregrounding, the handler will never run. Alternative: try `pageshow`/`pagehide` events, or poll `document.hidden` on a timer.
- **`resume()` may require a user gesture on iOS:** If the AudioContext was suspended by the OS (not by script), `resume()` without a gesture might be silently ignored. In that case, we'd need to set a flag and resume on the next `touchend` instead.
- **The 200ms delay for the frozen-time check may be too short or too long:** If the context takes longer than 200ms to actually resume after `visibilitychange`, we might false-positive on the frozen check. Could increase to 500ms or add a retry.
- **`suspend().then(resume)` may not unstick a truly frozen context:** The suspend/resume cycle is a known workaround but isn't guaranteed. Alternative: destroy and recreate the AudioContext entirely (`window.__audioCtx.close()` then `new AudioContext()`).
- **`onstatechange` as an alternative trigger:** Instead of (or in addition to) `visibilitychange`, listen for `audioCtx.onstatechange` to detect when iOS changes the state to `interrupted`/`suspended` and queue a resume for when the app returns.

## References

- WebKit bug #263627: AudioContext reports `running` but `currentTime` is frozen
- iOS `AudioContext.state` can be `"interrupted"` (non-standard, WebKit-specific)
- `navigator.audioSession.type = 'playback'` routes Web Audio through media channel (already in our templates)
