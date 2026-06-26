# iOS Freeze Fix Plan v4 — Never close; budget context construction

> Status: **committed and pushed to production main** — `b47cd43` (core fix) +
> `89ba3fc` (review follow-ups: construction choke point, cooldown, comment fix)
> in `note-types/mvj/front.html` and `note-types/chinese/front.html`, pushed to
> `origin/main` 2026-06-11. Supersedes v3 ("close the leaked AudioContext"), which
> shipped as `098b65a` and **failed in the field** — freezes returned to ~3×/session
> with a black screen on re-entering the reviewer.
>
> **Field update 2026-06-26:** this v4 design is **not proven sufficient**. The user
> later reported the same error/freeze once around the 8th card after an apparent
> template update. That report does not prove the user had this exact build in a fresh
> AnkiMobile process, but if they did, the remaining trigger is likely another WebKit
> operation still present in the recovery/playback path: bare `new AudioContext()`,
> `resume()`, `decodeAudioData()`, `source.start()`, or possibly the `currentTime`
> probe itself. A private debug overlay build was shipped to identify the exact call;
> see `ios-freeze-known-facts.md`.

## What the v3 failure taught us

v3 held recovery timing constant (playback-scoped, the good part of `2dcc8ae`) and
reintroduced exactly one thing: `AudioContext.close()` before constructing a
replacement. The per-recovery freeze came back with it. Combined with the earlier
history — every `close()`-era version froze ~3×/session, the only `close()`-free
version (`2dcc8ae`) froze only at the late-session context cap — this is a clean A/B:

- **`close()` is the per-recovery freeze trigger**, not recovery timing.
- The leak/cap mechanism v3 fixed was real, but it was the *second* mechanism, not
  the dominant one.

Probable mechanism: `close()` starts an async teardown of WebKit's audio stack (plus
AVAudioSession traffic that contends with AnkiMobile's own native audio); the
synchronous `new AudioContext()` right after blocks the WebContent main thread
against that in-flight teardown. JS-level timeouts can't help — once `close()` is
issued the process is at risk. A wedged main thread matches every symptom: frozen
card, app chrome alive, black card area on re-entry, app kill required.

## The bind, and the resolution

- Unbounded recreation without `close()` → leaked contexts hit WebKit's live-context
  cap late in long sessions (the `2dcc8ae` freeze).
- Recreation with `close()` → per-recovery wedge (~3×/session).

So recreation must be **bounded**: never close, and refuse to construct more than a
small fixed number of contexts per document lifetime. The `2dcc8ae` field data shows
the cap is only reached after a full session of leaked recoveries, so a budget of 3
total constructions stays far below it.

## Implemented changes (identical in both templates)

1. **`__releaseContext` deleted; no `close()` (or `suspend()`) anywhere.**
2. **`window.__newAudioCtx()` construction choke point.** The only code that
   constructs an `AudioContext`. It enforces the budget
   (`window.__audioCtxBudget = 3`, counted in `window.__audioCtxCreates`,
   including the eager setup construction) and a 10s cooldown between
   constructions (`window.__audioCtxCreatedAt`), so one transient contention
   episode spanning a card flip cannot burn multiple budget slots on
   born-stalled replacements. Returns `null` (caller falls back to `<audio>`
   for that playback) when over budget, cooling down, or construction throws.
3. **Resume-in-place for `suspended`/`interrupted` contexts.** Backgrounding and OS
   audio-session interruptions leave the context gesture-recoverable; a replacement
   would start in the same state, so recreating only burns budget. Bounded resume
   (300ms timer, first-wins guard) → 40ms settle → clock probe:
   - probe passes → recovery resolves `true`, context kept;
   - resume times out / context not `running` → resolve `false` (this playback uses
     the `<audio>` fallback; a later card retries);
   - resume succeeds but clock frozen → probe fails → resolve `false`; the *next*
     card's recovery sees a running-but-stalled context and takes the replacement
     path within budget.
4. **Replacement path** (missing context, or running with frozen clock — the WebKit
   stall, where `resume()` is a no-op): construct within budget, assign
   `window.__audioCtx` immediately, resume-if-suspended, 40ms settle, probe. The old
   context is abandoned, never closed.
5. **Past budget:** recovery resolves `false` quickly → `__audioCtxState = 'failed'`
   → `<audio>` fallback for that card. Each new card resets state to `unknown`, so
   the optimistic probe keeps checking whether the stalled context's clock came back
   (AVAudioSession contention can clear on its own); Web Audio resumes automatically
   if it does.
6. **Kept from v3/`098b65a`:** playback-time-only recovery; `__webAudioPlay`
   captures the context once and bails if swapped mid-playback; `viaFresh` settles
   only on intentional `__stopAllAudio()` stops (gen-bump-gated `pause`).

## What this v4 plan still proves — and no longer proves

- It still proves the clean A/B against `098b65a`: `AudioContext.close()` is a real
  per-recovery freeze trigger and should stay removed.
- It still protects against the known late-session live-context cap by bounding
  constructions to 3 per document lifetime.
- It no longer proves the overall freeze is solved. A later field report says a
  freeze/error still occurred. The unresolved question is which remaining WebKit audio
  operation wedges AnkiMobile when the context is already sick.

## Accepted trade-offs in v4

- A session with ≥2 genuine running-stalled events ends up on `<audio>` fallback
  latency until the stall self-clears or the app restarts. This is **not** acceptable
  as a final user-facing solution for Matt because iOS `<audio>` latency is a
  deal-breaker; it was accepted only as a safer degradation than freezing.
- An abandoned stalled context keeps its (small) resources until the document goes
  away; bounded at 2.

## Verification

- Static: no `close(`/`__releaseContext` outside comments in either template.
- Static: every `new Ctor()` / eager construction is counted, and `createReplacement`
  checks the budget before constructing.
- The audio regions of `mvj/front.html` and `chinese/front.html` are byte-identical
  (verified by extracting the region and comparing).
- All `<script>` blocks in both templates pass `node --check`.
- Real signal now comes from the private debug overlay build described in
  `ios-freeze-known-facts.md`: install debug addon → run note-type update → sync →
  fully relaunch AnkiMobile → screenshot the overlay if it freezes. The last overlay
  breadcrumb should identify whether the trigger is constructor, resume, decode,
  source start, probe, or something else.
