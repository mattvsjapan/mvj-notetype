# iOS Freeze Fix Plan v5 — Construct once; never construct after card setup

> Status: implemented on `main` by the v5 cycle, pending code review, push, note-type update, sync, and field validation. Supersedes v4 (no `close()`, bounded post-setup construction), which the 2026-07-01 debug overlay showed was not sufficient.

## Goal

Eliminate the field-evidenced iOS AnkiMobile freeze trigger by removing every post-setup `AudioContext` construction from the card templates. The context is constructed at most once per fresh document, at card setup, and is never replaced.

## Why v5 Exists

The v4 design correctly removed `AudioContext.close()`, but it still allowed bounded post-setup construction when recovery found a missing or running-stalled context. The first debug-overlay freeze report received 2026-07-01 stopped at `newAudioCtx before constructor` in that old recovery arm, in a template with no executable `close()`.

That evidence changes the rule. Construction is not merely something to budget; it is unsafe when issued during audio-stack contention. Recovery reaches that arm only after a failed probe, which is exactly the contested state. Therefore v5 deletes post-setup construction instead of trying to cool it down or cap it.

## Invariants

1. **Single construction attempt.** The only executable construction path is `new Ctor()` inside `window.__newAudioCtx()`, and the only executable call site is eager card setup.
2. **Attempt-counting.** `window.__audioCtxCreates++` happens before `new Ctor()`. A throwing constructor consumes the one attempt.
3. **No teardown.** No executable `close()`, `suspend()`, or `__releaseContext` exists in either template.
4. **No post-setup construction.** `__audioCtxRecover()` never calls `__newAudioCtx()` and has no helper that makes a replacement context.
5. **Resume-in-place survives.** `suspended` / `interrupted` contexts still use bounded `resume()` on the same object, followed by the clock probe.
6. **Degrade, never freeze.** Missing context or running-stalled context resolves recovery `false` and lets `__playMobile()` fall back to `<audio>` for that episode.
7. **Template parity.** The shared AudioContext lifecycle block and `__playMobile` block remain byte-identical between MvJ and Chinese templates. `__webAudioPlay` bodies are allowed to differ; only the comment wording is shared.
8. **Autoplay/card-scope semantics unchanged.** Generation tokens, card-scope guards, optimistic healthy path, AnkiDroid gate, and `viaFresh` settle rules are preserved.

## Implemented Template Changes

Applied to both `note-types/mvj/front.html` and `note-types/chinese/front.html`.

### `window.__newAudioCtx()`

- Budget changed from multiple constructions to one construction attempt per document lifetime.
- Attempt counter now increments before the constructor.
- The cooldown timestamp and cooldown branch were deleted.
- The choke-point comment now explains that the one-attempt budget is a mechanical guard against future post-setup call sites and cites the 2026-07-01 overlay evidence.

### Eager setup construction

Unchanged shape:

```javascript
if (!window.__isAndroid()) {
    if (!window.__audioCtx) {
        window.__audioCtx = window.__newAudioCtx() || undefined;
    }
}
```

This remains Android-gated and remains the sole executable call site.

### `window.__audioCtxRecover(scope, expectedGen)`

- The post-setup construction arm was deleted.
- Missing context and running-stalled context now resolve `false` directly, with a comment naming the v5 invariant and the overlay evidence.
- Token/dedup/scope machinery remains.
- In-place resume for `suspended` / `interrupted` context remains.
- The 40ms settle and 80ms `currentTime` probe remain for resumed contexts.
- `.then()` cleanup remains.

### `window.__webAudioPlay()`

The capture-once comment was updated. The code still captures `window.__audioCtx` into `actx` and checks identity/state before starting a source. After v5 this is defense-in-depth against stale async playback, not protection against context replacement.

### `window.__playMobile()`

No code change. It was already structured so `__audioCtxRecover(...).then(ok)` maps `ok === false` to `viaFresh()`. That branch is now a load-bearing degraded path and is covered by headless tests.

## Runtime Behavior

- **Healthy iOS path:** unchanged. Web Audio remains primary and low-latency.
- **Setup constructor fails:** the one attempt is consumed; the session falls back to `<audio>` rather than retrying later during review.
- **Background / interruption:** recovery tries bounded in-place `resume()` on the existing context. If resume/probe fails, that playback falls back.
- **Running-but-stalled context:** unknown-state autoplay still attempts the optimistic Web Audio start and parallel probe. If the probe fails, the optimistic source is stopped, the autoplay generation reference is resynced, recovery returns `false`, and playback falls back to `<audio>`.
- **Missing context:** recovery returns `false` immediately; no constructor, resume, decode, or source start occurs in that arm.
- **Watchdog reload:** a real WebContent reload creates a fresh document, so the single setup attempt is allowed again.
- **Android:** unchanged native `<audio>` path.

## Verification

Deposited proof lives in `addon/tests/test_audio_ctx_lifecycle.py` and runs directly:

```bash
python3 addon/tests/test_audio_ctx_lifecycle.py
```

The test covers:

- Row 1: lifecycle runtime behavior — eager setup constructs once; throwing setup burns the attempt; missing/running-stalled recovery returns `false` without construction; suspended resume works in place; hanging resume times out false.
- Row 1b: whole-template static scan — only `new Ctor()` in the choke point; no direct `new AudioContext`; executable `__newAudioCtx` references are definition plus eager setup call; budget is one; increment precedes constructor.
- Row 2: `__playMobile` branch behavior — Android fresh path, desktop Web Audio / fresh branches, iOS missing-context fallback, iOS failed-state fallback.
- Row 3: optimistic stalled path clears the source, bumps/resyncs generation, reaches fallback, and settles; external pause without generation bump does not settle the queue, while generation-bumped pause does.
- Row 3b: card-scope guards at `__playMobile` entry, `__audioCtxRecover` entry, stale mid-recovery, and generation mismatch before recovered playback.
- Row 4: whole-template no-teardown/deleted-path scan.
- Row 5: lifecycle and `__playMobile` block byte parity across templates.
- Row 6: every extracted script block passes `node --check`.

Manual/field proofs remain outside this code change:

- Desktop card smoke for MvJ and Chinese template paths.
- Fresh-document AnkiMobile field validation with the debug overlay rebased onto v5 and build id `ios-audio-debug-2026-07-01-a` visible.

## Deployment Notes

Production users receive this fix only after:

1. Commit pushed to `origin/main`.
2. User runs the normal note-type update on desktop.
3. User syncs.
4. User fully kills and relaunches AnkiMobile.

The full relaunch is required because the AnkiMobile WebView can keep old globals across card transitions and background/foreground cycles.

## Accepted Residual Risks

- Evidence is one field sample for the constructor wedge. The overlay branch remains the way to identify any next trigger.
- Optimistic `decodeAudioData()` and `source.start()` on a running-stalled context remain in the healthy-latency path. They were not the final breadcrumb in the 2026-07-01 report.
- `__webAudioSource.stop()` can run while clearing the optimistic stalled path. It has not appeared as a risky breadcrumb and is required to prevent double audio.
- A dead-at-setup audio stack costs a whole session of `<audio>` latency. That is accepted over retrying the constructor during review.
- The iOS freeze-elimination claim is unverified until real fresh-document sessions run clean.
