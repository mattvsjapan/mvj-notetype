# iOS AudioContext after background / foreground

## Problem

On iOS AnkiMobile, the WebView's `AudioContext` can become unusable after app backgrounding, OS audio-session interruption, or nearby native audio playback. Tapping audio buttons or autoplay may then produce silence even though the card is still visible.

## Current Root Cause Model

There are two iOS Web Audio states the templates must handle:

1. The context can report `state === 'suspended'` or the Apple-specific `state === 'interrupted'` after backgrounding or interruption.
2. WebKit can report `state === 'running'` while `currentTime` is frozen, so a state check alone is not a health check.

The second case is why the template still probes `currentTime`: sample, wait briefly, and require the clock to advance.

## Current Design

The canonical implementation is the AudioContext lifecycle block in:

- `note-types/mvj/front.html`
- `note-types/chinese/front.html`

The v5 rule is:

- create the `AudioContext` eagerly at card setup,
- count the setup construction attempt before calling the constructor,
- never construct a replacement after setup,
- never call `close()` as recovery,
- never call `suspend()` as an unstick tactic,
- resume `suspended` / `interrupted` contexts in place, and
- if the context is missing or running-stalled, resolve recovery `false` and let `__playMobile()` use `<audio>` fallback for that degraded episode.

The root history and field evidence live in `ios-freeze-known-facts.md`. The short version: the 2026-07-01 debug overlay captured a freeze at `newAudioCtx before constructor` in a template with no executable `close()`. That constructor was issued during a sick audio-stack episode. So post-setup construction is now treated as the evidenced freeze trigger.

## Recovery Flow

`__audioCtxRecover(scope, expectedGen)` runs only at playback time and only for the active card scope.

1. If scope or generation is stale, return `false` without side effects.
2. Stop any current `BufferSourceNode` to prevent double audio.
3. If the existing context is `suspended` or `interrupted`, call `resume()` on that same context.
4. Bound the resume wait. If it does not settle in time, return `false`.
5. After a settled resume, wait briefly and probe `currentTime`.
6. If the probe passes, mark healthy and continue Web Audio.
7. If the probe fails, return `false`; `__playMobile()` falls back to `<audio>`.
8. If there is no context, or a `running` context has a frozen clock, return `false` directly. Do not construct.

The recovery token, scope, and generation checks are load-bearing because AnkiMobile keeps one WebView document across card transitions. A stale card must not mark the shared context healthy/failed after the reviewer has moved on.

## What We No Longer Do

Do not reintroduce these older recipes:

- **No `suspend().then(resume)` unstick cycle.** It was a speculative workaround for a running-but-frozen clock. It touches the sick audio stack and is now on the wrong side of the freeze boundary.
- **No `close()`-then-construct recovery.** Every `close()` era froze repeatedly in the field. `close()` is an evidenced crash/freeze class for this card runtime.
- **No post-setup `new AudioContext()` recovery.** The debug overlay showed the constructor itself wedging when issued during contention.
- **No visibilitychange recovery work.** Visibility changes only mark health `unknown`; actual audio lifecycle work waits until playback.
- **No touchend construction safety net.** User interaction does not make post-setup construction safe under the v5 evidence model.

## Operational Notes

- A full AnkiMobile kill/relaunch is required before judging an iOS template change. A surviving WebView keeps old globals.
- Android is gated to `<audio>` and does not use this recovery machinery.
- `<audio>` fallback has higher latency on iOS and is not the normal path. It is the degraded-episode path when the setup context cannot be trusted.
- If a future debug overlay identifies `resume()`, `decodeAudioData()`, `source.start()`, or the `currentTime` probe as the last breadcrumb, update `ios-freeze-known-facts.md` first and then change the lifecycle block.

## References

- `ios-freeze-known-facts.md` — field timeline, root cause model, deployment facts.
- `ios-freeze-fix-plan.md` — current v5 fix and verification matrix.
- WebKit bug #263627 — `AudioContext` can report running while `currentTime` is frozen.
- MDN / WebKit notes for Apple `AudioContext.state === 'interrupted'` behavior.
