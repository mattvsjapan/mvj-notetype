# iOS Review Freeze: Current Understanding

## Status

The active production fix is **v5: construct `AudioContext` once at card setup and never construct again for that document lifetime**. The field-evidenced freeze trigger is post-setup `AudioContext` construction during an already-sick iOS audio-stack episode. The card now degrades that episode to `<audio>` fallback instead of trying to make a new context.

This document is operational context for the main-branch templates and the private debug-overlay branch. It intentionally separates what is field-evidenced from what remains a residual risk.

## Reported Behavior

- A user reported that AnkiMobile on iOS can freeze while reviewing cards with the updated note type.
- First debug-overlay field report, received 2026-07-01 after several clean days on the June debug build:
  - Freeze happened mid-session on a front side; nothing autoplayed and the user could not advance to the back.
  - Tapping **Edit** produced a black screen; navigating back returned a new card without a full app kill. That is consistent with iOS killing and reloading the wedged WebContent process, which also resets document globals.
  - The overlay showed a failed clock probe followed by the old post-setup construction arm and stopped at **`newAudioCtx before constructor`** with no later breadcrumb.
  - The template had no executable `close()` call. The bare synchronous constructor itself wedged when issued during contention.
- Earlier production report after the no-`close()`/bounded-construction v4 update: one freeze around the 8th card. The report proved a template update happened, but not necessarily that the exact v4 build had loaded in a freshly relaunched AnkiMobile document.
- Prior report after the `close()`-based leak fix (`098b65a`): freezes returned to about three times per session, black screen on re-entry, app kill required.
- Killing AnkiMobile and reopening it always made the app work again.
- The issue started after moving this note type to Web Audio for low-latency iOS playback.
- The issue is not reproducible locally.

## Constraints

- The templates use `[audio:...]` tags for card-controlled audio.
- The note type intentionally avoids native `[sound:...]` tags as the normal card-audio mechanism because AnkiMobile may autoplay native sound fields independently of the card's settings.
- Matt does not accept iOS `HTMLAudioElement` latency as the normal path. `<audio>` fallback is acceptable only for degraded episodes where the alternative is a freeze.
- We cannot rely on Web Inspector logs from the affected device. The private overlay exists because screenshots are the field evidence channel.
- A surviving AnkiMobile WebView keeps old template globals. Any iOS test of a new fix requires a full app kill and relaunch after sync.

## Relevant Commits and Eras

- `6406118` — ported Web Audio playback to Japanese and MvJ cards to avoid iOS `<audio>` latency.
- `83a27ba` / `00116c4` / `f77daf9` era — recovery could recreate contexts and used `close()` before constructing a new one. Field freezes were roughly three times per session.
- `2dcc8ae` — moved recovery to playback time and, load-bearing by accident, removed `close()`. Per-recovery freezes stopped, but a late-session freeze remained, consistent with leaked live contexts accumulating.
- `098b65a` — reintroduced `close()` before making a new context to avoid the leak. Failed in the field: freezes returned to roughly three times per session. This isolates `close()` as a real per-recovery freeze trigger.
- `b47cd43` + `89ba3fc` — v4 no-`close()` bounded construction through a single constructor choke point. Safer than `close()`, but insufficient: the 2026-07-01 overlay showed the constructor itself wedging when called during contention.
- v5 — current main-branch design: one setup-time construction attempt, counted before `new Ctor()`, no post-setup construction arm, no construction cooldown, no context replacement.

## Root Cause (current model)

There are three distinct mechanisms in the history:

1. **Per-recovery freeze from `AudioContext.close()`.** Every era that called `close()` froze around three times per session. The close-free era did not show that per-recovery pattern. Probable mechanism: `close()` starts asynchronous WebKit / AVAudioSession teardown; any adjacent audio-stack operation can block the WebContent main thread while that teardown is in flight.
2. **Late-session live-context pressure.** A close-free design that kept making new contexts can accumulate enough abandoned live contexts to hit iOS/WebKit's implementation-defined limit late in a long session.
3. **Construction-during-contention freeze, evidenced 2026-07-01.** The debug overlay stopped immediately before the synchronous `AudioContext` constructor in a template with no `close()`. Construction is usually safe at fresh document setup, but it is not safe as recovery while the audio stack is already sick.

v5 resolves the bind by eliminating post-setup construction rather than trying to make it safer. The only `AudioContext` construction attempt is the eager setup attempt for a fresh document. If setup fails, the session uses `<audio>` fallback. If the context later stalls or is missing, playback degrades to `<audio>` for that episode instead of constructing.

## Current Fix (v5)

Applied identically to `note-types/mvj/front.html` and `note-types/chinese/front.html` in the shared lifecycle and `__playMobile` blocks.

- `AudioContext.close()` is never called, and there is no `suspend()` unstick path.
- `window.__newAudioCtx()` is the only constructor choke point.
- The budget is one construction **attempt** per document lifetime. `window.__audioCtxCreates++` happens before `new Ctor()`, so a throwing constructor consumes the attempt and cannot be retried later during a sick episode.
- Eager setup construction remains the sole executable call site: `window.__audioCtx = window.__newAudioCtx() || undefined`, Android-gated.
- `__audioCtxRecover(scope, expectedGen)` keeps its token/dedup/card-scope machinery and still resumes `suspended` / `interrupted` contexts in place.
- If recovery sees no context, or a `running` context whose clock is stalled, it resolves `false` quickly. It does not construct, resume, decode, or start new Web Audio in that false-fast arm.
- `__playMobile()` already maps recovery `false` to `__freshPlay()`; that degraded episode pays iOS `<audio>` latency instead of risking a WebContent freeze.
- The optimistic unknown-state path still starts Web Audio before the 80ms probe so healthy cards keep the low-latency path.
- Card-scope guards and autoplay generation tokens remain load-bearing: stale cards cannot complete recovery side effects, and internal cancellation resyncs the autoplay queue's mutable generation reference.

## Code Facts (current)

- The MvJ and Chinese front templates use low-latency Web Audio as the primary mobile path when the once-constructed context is healthy.
- Android is gated to the native `<audio>` path because AnkiDroid does not share iOS WKWebView's Web Audio behavior.
- The `AudioContext.currentTime` clock probe is still required because iOS WebKit can report `state === "running"` while the clock is frozen.
- Card activation and `visibilitychange` mark iOS audio health `unknown`; they do not run recovery.
- Recovery is playback-time only and scoped to the active card.
- There is no executable `close()`, `suspend()`, `__releaseContext`, post-setup constructor call, constructor cooldown timestamp, or context-replacement helper in either template.
- Sequential mobile queues use mutable `genRef` tokens; `window.__webAudioGen` is incremented by `__stopAllAudio()`.

## Deployment Facts

- The normal addon does **not** bundle updated templates for existing users. `addon/notetype.py` downloads `front.html` / `back.html` / `css.css` at runtime from this repo's GitHub `main` branch.
- A production template fix reaches users only after the commit is pushed to `origin/main`, the user manually runs the note-type update action on desktop, syncs, and fully kills/relaunches AnkiMobile.
- `_auto_install_notetype()` only installs automatically when the note type does not already exist. Existing users need the manual update action.
- There is no production template version constant. The debug overlay branch is the temporary exception: field screenshots must show the expected v5 debug build id after the overlay branch is rebased.
- A report from a surviving pre-v5 WebView is void for v5. Fresh-document proof requires full AnkiMobile relaunch.

## External Platform Facts

- WebKit/iOS treats `AudioContext` as an expensive object and enforces an implementation-defined maximum number of live contexts.
- WebKit bug reports document cases where Web Audio goes silent while `state` is `"running"` and `currentTime` stops advancing, where `resume()` promises hang, and where contexts get stuck `"suspended"` / `"interrupted"` after backgrounding.
- On iOS, an audio-session interruption can pause media elements without auto-resume.
- MDN documents the non-standard `interrupted` `AudioContext` state on Apple platforms.

## Known, Deferred / Not Final Solutions

Do not treat `<audio>` fallback as the final normal path. It is only the safer degraded-episode path while the main Web Audio context is unhealthy.

- **Suspended/interrupted dead end.** If a context gets stuck `suspended` / `interrupted` and `resume()` persistently fails, each attempted Web Audio playback may pay the bounded resume wait before falling back. Possible later tuning: temporarily fail fast after repeated resume failures.
- **Optimistic work on a running-stalled context.** In unknown state, autoplay still starts fetch/decode/start optimistically before the probe. That avoids adding probe latency to healthy cards. The overlay has not identified decode or source start as a freeze trigger, but this remains instrumented risk.
- **Duplicate degraded fetch.** A probe-fail playback can fetch/decode optimistically and then play through `<audio>`. Avoiding that would require probe-first behavior that slows the healthy path.
- **Setup failure means session fallback.** A setup-time constructor failure now burns the only attempt. That is intentional: a stack sick enough to fail at setup should not be retried later during review.

## How To Interpret The Next Debug Report

After the debug-overlay branch is rebased onto v5, useful screenshots must show the new v5 debug build id (`ios-audio-debug-2026-07-01-a`) and must come from a freshly relaunched AnkiMobile document.

Read the last breadcrumb first:

- Last line contains `recover old resume before` → `resume()` on a sick/suspended context is the likely remaining trigger.
- Last line contains `webAudio before decodeAudioData` → optimistic decoding on a bad-but-`running` context is the likely trigger.
- Last line contains `webAudio before source.start` → starting a decoded `BufferSourceNode` is the likely trigger.
- Last line contains `probe before first currentTime` or `probe before second currentTime` → even the clock probe read may be involved.
- Last line contains `fresh before audio.play` → the degraded fallback path itself needs investigation.
- A v5 overlay should not show a post-setup constructor breadcrumb. If it does, the template did not load v5 or a new call site was introduced.
- If a screenshot does not show the expected v5 build id, first verify install → note-type update → sync → full AnkiMobile relaunch.
