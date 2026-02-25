# iOS Audio Autoplay Latency in Anki WKWebView

## The Problem

Audio autoplay on iOS Anki has ~900ms lag between calling `play()` and hearing audio. Manual taps feel the same delay but it's less noticeable because the user initiated the action.

## Root Cause

**HTMLAudioElement has ~900ms pipeline latency on iOS WKWebView**, regardless of:
- Whether the file is preloaded (`preload='auto'` is ignored on iOS)
- Whether `audio.load()` is called explicitly (also ignored)
- Whether `new Audio(src).play()` is used vs a pre-created element
- Whether an AudioContext is keeping the audio session warm

The latency is intrinsic to iOS WKWebView's HTMLAudioElement implementation. It is NOT caused by:
- Audio session cold-start (persists even with a warm AudioContext)
- File loading (fetch() loads the same file in ~12ms)
- Audio decoding (decodeAudioData() takes ~3ms)
- JavaScript execution time (only ~30ms before play() is called)
- Anki's rendering pipeline (~241ms, but this is before JS even runs)

## Diagnostic Approach

Added `performance.now()` timing instrumentation to measure:
- **JS start**: when the first `<script>` executes (relative to page navigation)
- **play() called**: when `audio.play()` is invoked
- **audio playing**: when the `playing` event fires

Results from a typical card (several cards into a session):
```
JS start:      67387ms
play() called: 67444ms  (JS work: 57ms)
audio playing: 68380ms  (pipeline: 936ms)
```

Then added a parallel fetch + Web Audio API decode test:
```
fetch: 12ms (18KB) | decode: 3ms | WebAudio total: 15ms
```

This proved the file is available in 15ms — the 900ms is entirely HTMLAudioElement overhead.

## Why Web Audio Was Silent During Testing

Web Audio API executed correctly (buttons highlighted, `onended` fired, timing showed ~15ms) but produced **no audible output**. The cause: **the iOS ringer/silent switch**.

- HTMLAudioElement routes through the **media channel** → plays regardless of mute switch
- Web Audio API routes through the **ringer channel** → silenced when mute switch is on
- Documented in [WebKit Bug #237322](https://bugs.webkit.org/show_bug.cgi?id=237322)

### Fix: `navigator.audioSession.type = "playback"` (iOS 16.4+)

```js
navigator.audioSession.type = "playback";
```

This routes Web Audio output through the media channel instead of the ringer channel. Available since Safari 16.4 ([WebKit blog](https://webkit.org/blog/13966/webkit-features-in-safari-16-4/)).

Alternative: the [unmute](https://github.com/swevans/unmute) library pattern — play a continuous silent `<audio>` loop to force the audio mixer to merge Web Audio onto the media channel. More complex and has downsides (lock screen media controls, battery).

## Solution: Web Audio API for All Mobile Playback

Use `fetch()` → `AudioContext.decodeAudioData()` → `BufferSourceNode.start()` instead of HTMLAudioElement for both autoplay and manual taps on mobile. This bypasses the 900ms HTMLAudioElement pipeline entirely.

### Key Implementation Details

**AudioContext starts `running` in Anki's WKWebView without a user gesture.** Normally, iOS requires a user gesture to move AudioContext from `suspended` to `running`. But Anki's WKWebView sets `mediaTypesRequiringUserActionForPlayback = []`, and this permissive autoplay policy extends to Web Audio — calling `resume()` at page load succeeds immediately. This means Web Audio works from the very first card, with no HTMLAudioElement fallback needed.

A touchend handler is kept as a safety net in case the eager `resume()` ever fails (e.g., different iOS version or Anki configuration). In that case, the first card would fall back to HTMLAudioElement (~900ms), and subsequent cards would use Web Audio after the first tap resumes the AudioContext.

**`navigator.audioSession.type = "playback"` must be set** before creating the AudioContext, so Web Audio output goes through the media channel and isn't silenced by the mute switch.

**Generation counter for cancellation.** Web Audio playback is async (fetch → decode → play). A `__webAudioGen` counter increments on each `__stopAllAudio()` call. Each playback chain checks `gen === window.__webAudioGen` before proceeding to the next file, preventing stale chains from continuing after the user taps a button or a new card loads.

**BufferSourceNode.onended for sequencing.** Sequential playback (word → sentence → definition) chains via the `onended` event on each BufferSourceNode, similar to how HTMLAudioElement uses `audio.onended`.

### Architecture

```
ALL MOBILE PLAYBACK (autoplay + manual taps):
  fetch(src) → arrayBuffer → decodeAudioData → BufferSourceNode.start()
  ~15ms total, works from card 1

FALLBACK (if audioCtx somehow not running):
  new Audio(src).play() via __freshPlay()
  ~900ms on iOS WKWebView

DESKTOP:
  Pre-created <audio> element, __safePlay() with retry logic
  Near-instant (desktop audio pipeline is fast)
```

## Things That Did NOT Help

1. **`audio.load()` after setting src** — iOS ignores it, same as `preload='auto'`. [Apple docs](https://developer.apple.com/library/archive/documentation/AudioVideo/Conceptual/Using_HTML5_Audio_Video/Device-SpecificConsiderations/Device-SpecificConsiderations.html) confirm: "preload and autoplay are disabled" and "load() is inactive until the user initiates playback"
2. **`__freshPlay()` (new Audio + immediate play) for autoplay** — same 900ms pipeline latency; the issue is HTMLAudioElement itself, not how the element is created
3. **Persistent AudioContext to "warm" the audio session** — the session was already warm; the latency is in the HTMLAudioElement implementation, not session activation
4. **Moving autoplay `setTimeout` earlier in the render function** — setTimeout(fn, 0) can't fire until all synchronous JS completes regardless of where it's queued
5. **Web Audio without `navigator.audioSession.type = "playback"`** — AudioContext processed the buffer correctly (onended fired, timing ~15ms) but produced no audible sound because output went through the ringer channel (silenced by mute switch)

## Anki-Specific Context

- Anki iOS uses WKWebView with `mediaTypesRequiringUserAction = []` — this permissive autoplay policy extends to both HTMLAudioElement and AudioContext, so `resume()` succeeds at page load without a user gesture
- WKWebView runs audio in a separate process with its own AVAudioSession, ignoring the host app's settings ([WebKit Bug #167788](https://bugs.webkit.org/show_bug.cgi?id=167788))
- The `window` object persists across card transitions (Anki updates DOM in-place, doesn't navigate)
- `performance.now()` values increase across cards (confirms same page context)
- `[audio:]` is a custom tag parsed by our JavaScript; `[sound:]` is Anki's native tag
- Audio files are local (~18KB for word audio), served through Anki's local HTTP server
- Anki's native `[sound:]` handler likely bypasses WKWebView entirely (uses native AVAudioPlayer), which is why native playback doesn't have the same latency ([Anki forum thread](https://forums.ankiweb.net/t/sluggish-audio-loading-on-ankimobile-with-large-media-collection/64480/1))

## References

- [Apple: iOS-Specific Considerations for HTML5 Audio](https://developer.apple.com/library/archive/documentation/AudioVideo/Conceptual/Using_HTML5_Audio_Video/Device-SpecificConsiderations/Device-SpecificConsiderations.html)
- [WebKit Bug #237322: Web Audio API muted when iOS ringer is muted](https://bugs.webkit.org/show_bug.cgi?id=237322)
- [WebKit Bug #167788: WKWebView ignores host app's AVAudioSession](https://bugs.webkit.org/show_bug.cgi?id=167788)
- [WebKit Features in Safari 16.4 — AudioSession API](https://webkit.org/blog/13966/webkit-features-in-safari-16-4/)
- [Anki Forums: Sluggish Audio Loading on AnkiMobile](https://forums.ankiweb.net/t/sluggish-audio-loading-on-ankimobile-with-large-media-collection/64480/1)
- [unmute library: Enable Web Audio with iOS mute switch](https://github.com/swevans/unmute)
