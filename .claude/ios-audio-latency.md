# iOS Audio Autoplay Latency in Anki WKWebView

## The Problem

Audio played through `HTMLAudioElement` in AnkiMobile's iOS WKWebView has roughly 900ms of audible latency between `play()` and sound. Autoplay exposes the delay most clearly, but manual taps use the same slow pipeline.

## Root Cause

`HTMLAudioElement` has intrinsic pipeline latency on iOS WKWebView. The delay remains even when:

- the file is preloaded (`preload='auto'` is ignored on iOS),
- `audio.load()` is called,
- `new Audio(src).play()` is used instead of a pre-created element,
- an `AudioContext` already exists, and
- the file is local and small.

Measured diagnostics showed local fetch + Web Audio decode in about 15ms while the `<audio>` pipeline took about 900ms. The latency is therefore in the iOS media-element pipeline, not in file loading, decoding, JavaScript execution, or Anki rendering.

## Why Web Audio Was Initially Silent

Web Audio executed correctly during testing, but produced no audible output when the iOS ringer/silent switch muted the ringer channel.

- `HTMLAudioElement` routes through the media channel and plays despite the mute switch.
- Web Audio routes through the ringer channel unless told otherwise.

The templates set:

```javascript
navigator.audioSession.type = 'playback';
```

before creating the `AudioContext`, which routes Web Audio through the media channel on supported iOS versions.

## Current Architecture

Mobile playback is split by platform:

```text
iOS AnkiMobile / WKWebView:
  primary: Web Audio through the once-constructed setup AudioContext
  degraded episode fallback: new Audio(src).play() via __freshPlay()

Android / AnkiDroid:
  always native <audio> via __freshPlay()

Desktop:
  pre-created <audio> element + __safePlay() retry behavior
```

### iOS: Web Audio Primary, Construct Once

The iOS path uses:

```text
fetch(src) → arrayBuffer → AudioContext.decodeAudioData() → BufferSourceNode.start()
```

when the setup-time context is healthy. That is the low-latency path Matt wants.

The important lifecycle rule after the 2026-07-01 freeze investigation is:

- construct `AudioContext` once at card setup,
- count that construction attempt before `new Ctor()`,
- never construct again after setup,
- never close or suspend the context as an unstick tactic,
- resume a `suspended` / `interrupted` context in place, and
- fall back to `<audio>` for the degraded episode when the context is missing or stalled.

This means `<audio>` is not the normal iOS path. It is the safe fallback when the alternative is touching a sick Web Audio stack in a way that field evidence says can freeze the WebView.

### Android: Native `<audio>` Always

AnkiDroid's WebView allows `<audio>` autoplay but does not lift the separate Web Audio user-gesture policy in the same way iOS AnkiMobile does. Android is therefore gated out of Web Audio and always uses the native `<audio>` path.

### Cancellation and Sequencing

Web Audio playback is asynchronous. A global `__webAudioGen` increments on `__stopAllAudio()`. Playback chains check the generation before starting stale audio, and autoplay queues carry a mutable `genRef` so an internal cancellation during stalled-context recovery does not strand the queue.

`BufferSourceNode.onended` sequences Web Audio clips. `<audio>` fallback sequences through `ended` / `error`, plus a generation-bumped `pause` from `__stopAllAudio()`; an OS pause without a generation bump is not treated as queue completion.

## What `<audio>` Fallback Means Now

The fallback is a degraded-episode safety valve, not a reversal of the Web Audio latency work.

It is used when:

- Android is detected,
- desktop/mobile non-Web-Audio branches need native playback,
- iOS setup never produced a context,
- iOS recovery marks the context failed for that playback, or
- the iOS context is missing/stalled and v5 refuses to construct after setup.

On iOS this can cost about 900ms for that playback, but that tradeoff is accepted only to avoid the evidenced freeze class.

## Things That Did Not Help

1. `audio.load()` after setting `src` — ignored by iOS for preloading purposes.
2. `new Audio(src).play()` for autoplay — same media-element latency.
3. A persistent `AudioContext` just to warm the audio session — the latency is in `HTMLAudioElement`, not a cold session.
4. Moving autoplay `setTimeout(..., 0)` earlier — it still cannot run until synchronous card JavaScript yields.
5. Web Audio without `navigator.audioSession.type = 'playback'` — work completes but can be muted by the ringer channel.
6. Touchend as a general safety net — current iOS behavior is governed by the setup context and playback-time recovery, not by constructing/resuming from a touchend hook.
7. "No fallback needed" as a rule — field evidence now requires a degraded fallback when the context is absent or stalled.

## Anki-Specific Context

- Anki iOS uses WKWebView with a permissive media autoplay policy; Web Audio has worked from card setup in this environment.
- The `window` object persists across card transitions because Anki updates the DOM in place.
- A full AnkiMobile kill/relaunch is required to prove a new template version on iOS.
- `[audio:]` is a custom tag parsed by template JavaScript; `[sound:]` is Anki's native tag.
- Audio files are local and served through Anki's local HTTP server.

## References

- [Apple: iOS-Specific Considerations for HTML5 Audio](https://developer.apple.com/library/archive/documentation/AudioVideo/Conceptual/Using_HTML5_Audio_Video/Device-SpecificConsiderations/Device-SpecificConsiderations.html)
- [WebKit Bug #237322: Web Audio API muted when iOS ringer is muted](https://bugs.webkit.org/show_bug.cgi?id=237322)
- [WebKit Bug #167788: WKWebView ignores host app's AVAudioSession](https://bugs.webkit.org/show_bug.cgi?id=167788)
- [WebKit Features in Safari 16.4 — AudioSession API](https://webkit.org/blog/13966/webkit-features-in-safari-16-4/)
- [Anki Forums: Sluggish Audio Loading on AnkiMobile](https://forums.ankiweb.net/t/sluggish-audio-loading-on-ankimobile-with-large-media-collection/64480/1)
- [unmute library: Enable Web Audio with iOS mute switch](https://github.com/swevans/unmute)
