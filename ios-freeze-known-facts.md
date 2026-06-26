# iOS Review Freeze: Current Understanding

## Reported Behavior

- A user reported that AnkiMobile on iOS can freeze while reviewing cards with the updated note type.
- **Latest production report (after `b47cd43` + `89ba3fc`, as reported 2026-06-26):** "I know it updated because my sentence order changed but it's still giving me that error. This one around the 8th card one time."
  - Interpret carefully: the visible sentence-order/rendering change was `288136d`, which predates the current no-`close()` budget fix. So the sentence-order observation proves *a* template update happened, but does **not** by itself prove the user had `b47cd43`/`89ba3fc`, synced, and fully killed/relaunched AnkiMobile.
  - If the user did have `b47cd43`/`89ba3fc` in a fresh AnkiMobile process, the remaining likely triggers are not `close()` but one of the still-present WebKit touches: synchronous `new AudioContext()` without prior close, `resume()` on a sick context, or optimistic `decodeAudioData()` / `source.start()` on a context whose `state` says `running` while `currentTime` is frozen.
- **Prior report (after the `098b65a` close-the-leak fix):** "Anki freezes while reviewing cards continues with the updated note type on iOS. When this happens, if I back out to the main menu, get back in the session, I get a black screen. Now it happens like 3 times per session. I have to kill the app and get back on Anki."
- Report history by template version:
  - **Pre-`2dcc8ae` versions** (recovery ran at card transition / `visibilitychange` and called `ctx.close()` before recreating): freezes **about three times per study session**; card sometimes did not advance after answering on the back of the card.
  - **`2dcc8ae`** (recovery playback-scoped, **no `close()` anywhere**): still froze, but **only late in the session** ("usually around when I have 4 cards left"); backing out and re-entering showed a black card area or "No current card."
  - **`098b65a`** (playback-scoped recovery + `close()` reintroduced before recreation): freezes back to **~3 times per session**, black screen on re-entry, app kill required.
  - **`b47cd43` + `89ba3fc`** (never close, budget constructions): one later field report says the problem persists, once around the 8th card. This refutes only the claim that the budget/no-close design fully solved the freeze; it does not re-implicate `close()`, because current templates still have no executable `close()` / `suspend()` calls.
- Killing AnkiMobile and reopening it always makes the app work again.
- The changed failure pattern after `098b65a` (3×/session spread out vs. once late-session) confirms the user was actually running the updated template.
- The issue started after upgrading to the new card type.
- The issue is not reproducible by us locally.

## Constraints

- The current templates use `[audio:...]` tags for controlled card audio.
- The note type intentionally avoids native `[sound:...]` tags because AnkiMobile auto-plays native sound fields independently of the card's audio settings.
- The user does not want the large iOS `HTMLAudioElement` latency as a general fallback, and does not want AnkiMobile native `[sound:...]` playback as the normal solution. As of 2026-06-26 Matt says latency is a complete deal-breaker, so `<audio>` fallback is diagnostic only, not an acceptable final design.
- The affected user is now willing to participate in debugging via a visible on-card overlay and screenshots. We still cannot rely on Web Inspector logs or invasive diagnostics.

## Relevant Commits

- `6406118` ("Port Web Audio API playback to Japanese and MVJ cards") — replaced mobile `HTMLAudioElement` playback with Web Audio to reduce iOS latency.
- `83a27ba` ("Recover stalled iOS AudioContext on card transition") — first recovery; recreated the context.
- `00116c4` ("Probe iOS AudioContext clock to defeat WebKit stall") — added `__audioCtxRecover()` and the clock probe; ran recovery from scope activation/card transition and `visibilitychange`. Recovery **called `ctx.close()`** before recreating. Era of ~3×/session freezes.
- `f77daf9` ("Bound iOS audio recovery") — wrapped recovery ops (including `close()`) with timeouts/backoff. Still ~3×/session freezes — JS-level timeouts cannot un-wedge WebKit's audio machinery once `close()` has been issued.
- `2dcc8ae` ("Make iOS audio recovery playback-scoped") — moved recovery to playback time only AND (unintentionally load-bearing) **removed `close()` entirely**. Per-recovery freezes stopped; a new late-session-only freeze appeared (leaked contexts accumulating to WebKit's live-context cap).
- `098b65a` ("Close leaked iOS AudioContext to fix late-session freeze") — reintroduced `close()` (release-gated, one-in-one-out) while keeping playback-scoped timing. **Failed in the field: freezes returned to ~3×/session.** This is the decisive A/B: timing was held constant and `close()` alone was reintroduced; the per-recovery freeze returned with it.
- `b47cd43` ("Stop closing iOS AudioContexts; budget constructions instead") — the **current fix**. Never calls `close()`; budgets constructions; resumes suspended/interrupted contexts in place. See "The Current Fix" below.
- `89ba3fc` ("Route AudioContext construction through one budgeted choke point") — code-review follow-up to `b47cd43`: single `__newAudioCtx()` construction choke point with named budget and a 10s construction cooldown; fixed a stale comment that still mentioned closing.
- Both pushed to `origin/main` on 2026-06-11.

## Current Diagnostic Build (2026-06-26)

We shipped a **private debug addon package**, not a production fix:

- Branch: `ios-audio-debug-overlay`
- Commit: `dcf0b29` ("Add iOS audio debug overlay"), pushed to `origin/ios-audio-debug-overlay`
- Package uploaded to Google Drive: `mvj-note-type-ios-audio-debug-2026-06-26.ankiaddon`
- Share link: <https://drive.google.com/file/d/1kvtyoxBqv2PJD4QB26qifz9yx5fcXygm/view?usp=drivesdk>
- Direct download: <https://drive.google.com/uc?id=1kvtyoxBqv2PJD4QB26qifz9yx5fcXygm&export=download>
- The debug addon keeps the same package id (`mvj_note_type`) and installs over the normal addon. Its `addon/notetype.py` points `_BASE_URL` at the debug branch, so running the note-type update downloads instrumented templates from `ios-audio-debug-overlay`.
- The debug overlay is unconditional in the debug branch and appears as a dark `#__iosAudioDebugPanel` at the top of the card. It is capped at `34vh`, uses `pointer-events: none`, and shows build id `ios-audio-debug-2026-06-26-a`.
- The overlay writes breadcrumbs immediately before risky WebKit audio operations: `new AudioContext`, newborn and old-context `resume()`, both `currentTime` probe reads, `decodeAudioData`, `source.start`, and fallback `<audio>.play()`.
- Important: the debug build should not change the audio policy or try to fix the freeze. It exists to screenshot the last breadcrumb before a hard WebView wedge.

User test flow:

1. Install the debug `.ankiaddon` over the existing addon on Anki desktop.
2. Restart Anki if prompted.
3. Open the MvJ Note Type settings and run the note-type update/install action.
4. Sync.
5. Fully kill and relaunch AnkiMobile; do not just background/foreground it.
6. Review normally. If it freezes, screenshot the card with the debug overlay visible and report whether the freeze happened on front/back, autoplay/manual tap, and approximate card number.

Rollback:

1. Reinstall the normal addon package.
2. Run the normal note-type update again (normal updater points back at `main`).
3. Sync.
4. Fully kill and relaunch AnkiMobile.
5. Confirm the debug overlay/build id is gone from cards.

## Root Cause (revised)

There are **two distinct freeze mechanisms**, both real:

1. **Per-recovery freeze (the dominant one, ~3×/session): `AudioContext.close()`.** Every template version that called `close()` froze ~3×/session regardless of *when* recovery ran (transition-time in the `00116c4`/`f77daf9` era, playback-time in `098b65a`). The only version that never called `close()` (`2dcc8ae`) never showed this per-recovery freeze. The earlier hypothesis that recovery *timing* (overlapping reviewer navigation) caused the freezes is **refuted** by the `098b65a` field result. Probable mechanism: `close()` initiates an async teardown of WebKit's audio rendering stack (and AVAudioSession interaction with AnkiMobile's own native audio); the synchronous `new AudioContext()` issued immediately after blocks the WebContent process's main thread against that in-flight teardown. A wedged main thread matches the symptoms exactly: reviewer dead, app chrome still navigable, black card area on re-entry (same wedged webview process), full app kill required.
2. **Late-session freeze: leaked-context accumulation.** With no `close()` at all (`2dcc8ae`), each recovery abandoned a live context; iOS/WebKit caps live `AudioContext` objects, and hitting the cap late in long sessions made context creation fail/wedge. This mechanism was correctly identified before `098b65a`; closing was just the wrong cure.

The bind: unbounded recreation requires `close()` (else mechanism 2), but `close()` triggers mechanism 1. The resolution is to make recreation **bounded** so neither applies.

## The Current Fix (commits `b47cd43` + `89ba3fc`)

Applied identically to `note-types/mvj/front.html` and `note-types/chinese/front.html`.

- **`close()` is never called. `__releaseContext` is deleted.** No close → no per-recovery wedge (mechanism 1).
- **Constructions are budgeted per document lifetime, through a single choke point.** All construction goes through `window.__newAudioCtx()`, which counts (`window.__audioCtxCreates`), enforces the budget (`window.__audioCtxBudget = 3`, including the eager card-setup construction), and enforces a **10s cooldown** between constructions. The cooldown prevents one transient AVAudioSession contention episode from burning multiple budget slots back-to-back (a context constructed mid-episode is usually born stalled, and the next card would otherwise immediately construct again). The `2dcc8ae` field data shows the cap is only reached after a whole session of leaked recoveries (well above 3), so ≤3 live-but-abandoned contexts cannot trigger mechanism 2. The choke point exists because the original leak came from exactly this drift class: a refactor dropping one lifecycle call at one of several construction sites.
- **Suspended/interrupted contexts are resumed in place, not replaced.** App backgrounding / OS audio-session interruptions leave the context `suspended` (or iOS 17+ `interrupted`); a replacement would start in the same gesture-gated state, so recreating would only burn budget. The in-place `resume()` is bounded (300ms) and probe-verified. If `resume()` lands the context in `running` but the clock is still frozen, the probe fails, that playback falls back to `<audio>`, and the *next* card's recovery sees a running-but-stalled context and replaces it within budget.
- **Past the budget, playback degrades instead of freezing.** Recovery resolves `false` fast, `__audioCtxState` goes `failed`, the card plays via the `<audio>` fallback, and the per-card optimistic probe keeps watching for the old context's clock to come back (stalls from AVAudioSession contention can clear on their own).
- **Kept from `098b65a`:** playback-time-only recovery; `__webAudioPlay` capturing the context once and bailing if it is swapped mid-playback; `viaFresh` settling only on an intentional `__stopAllAudio()` (gen-bump-gated `pause`), so OS interruptions don't make the autoplay queue skip clips.
- The eager card-setup construction is now wrapped in try/catch (a construction failure no longer aborts the whole setup script block).

Field status: a later report says the freeze still occurred once around the 8th card.
So this fix is **not proven sufficient**. The current working theory is that `close()`
was one real trigger, but another WebKit operation in the still-present recovery /
optimistic playback path may also wedge the WebView.

## Code Facts (current, after the fix)

- The MvJ and Chinese front templates use low-latency Web Audio through `AudioContext` as the primary iOS playback path; the audio regions of the two templates are byte-identical.
- The `AudioContext.currentTime` clock probe is still used because `AudioContext.state === "running"` is not trusted on iOS.
- Card activation and `visibilitychange` mark iOS audio health `unknown` but never run recovery.
- `__audioCtxRecover(scope, expectedGen)` is a playback-time refresh, scoped and token-guarded so a stale card cannot complete recovery side effects.
- There is **no `close()` and no `suspend()` anywhere** in the templates.
- `window.__newAudioCtx()` is the only code that constructs an `AudioContext`; `window.__audioCtxCreates` is the per-document counter, `window.__audioCtxBudget` (3) the budget, `window.__audioCtxCreatedAt` the cooldown timestamp (10s between constructions).
- Back-side autoplay is scheduled with `setTimeout(..., 0)` and converges through `window.__playMobile()`.
- Sequential mobile queues use mutable `genRef` tokens; `window.__webAudioGen` is incremented only by `__stopAllAudio()`.

## Deployment Facts (how a fix or debug build actually reaches the affected user)

- The normal addon does **not** bundle the templates. `addon/notetype.py` downloads
  `front.html`/`back.html`/`css.css` at runtime from this repo's GitHub `main` branch
  (`raw.githubusercontent.com/mattvsjapan/mvj-notetype/main/note-types/mvj/`). A production fix exists for users only after `git push` to `origin/main`.
- The private debug addon is different only in its updater URL: its packaged
  `addon/notetype.py` downloads from
  `raw.githubusercontent.com/mattvsjapan/mvj-notetype/ios-audio-debug-overlay/note-types/mvj/`.
  That is why the debug branch must stay pushed while the user tests.
- `_auto_install_notetype()` (on profile open) only installs when the note type does
  **not** already exist. Existing users get new templates **only** by manually running
  the note-type update action in the addon (Tools menu / settings dialog), which
  fetches whatever branch that installed addon's `_BASE_URL` points at.
- Full update path for the affected user: install the intended addon package → run
  the manual note-type update on desktop → sync → user **fully kills and relaunches
  AnkiMobile** (a surviving webview/document keeps old script globals and possibly
  wedged state).
- There is no production version constant or hash anywhere that records which template
  version a user is running. The debug overlay is the temporary exception: screenshots
  should show build id `ios-audio-debug-2026-06-26-a`.

## External Platform Facts

- WebKit/iOS treats `AudioContext` as an expensive object and enforces an implementation-defined maximum number of live contexts.
- WebKit bug reports document iOS cases where Web Audio goes silent while `state` is `"running"` and `currentTime` stops advancing (e.g. bug 263627), where `resume()` promises hang as pending, and where contexts get stuck `suspended`/`interrupted` after backgrounding (bugs 237878, 261554).
- On iOS, an audio-session interruption (call, Siri, backgrounding) pauses media elements without auto-resume.
- MDN documents the `interrupted` `AudioContext` state on Apple platforms.

## Known, Deferred / Not Final Solutions

These were confirmed by review but deferred because they only bite in already-degraded
states, their cost is bounded latency (not intended to be a freeze fix), and fixing
them would add new state/branches to freeze-critical paths right before a field test.
Do **not** treat `<audio>` fallback as an acceptable final solution: Matt explicitly
said the latency is a deal-breaker. It can still be used as a short diagnostic
experiment if needed, but the current plan is to use the debug overlay first.

- **Suspended/interrupted dead end.** If a context gets stuck `suspended`/`interrupted`
  and `resume()` persistently fails, every card pays the 300ms resume timeout before
  falling back to `<audio>`, indefinitely; `createReplacement` is unreachable from that
  branch by design (a replacement would be born equally gesture-gated). Possible fix if
  field-relevant: after a resume failure, fire resume without waiting (resolve false
  immediately) for ~30s stretches.
- **Post-budget-exhaustion waste.** With the budget exhausted and a permanently stalled
  `running` context, every autoplay card wastes a full fetch + decodeAudioData
  (discarded at the gen check) plus the 80ms probe before falling back. Possible fix if
  field-relevant: a sticky exhausted-and-stalled marker that switches the unknown path
  to probe-first (no optimistic decode), cleared when a probe passes. Not done now
  because budget-exhausted-but-healthy is the *expected* good case (the third context
  usually works), and probe-first would add 80ms to every card in that healthy state.
- **Slow-starting replacement burns its slot.** A viable context that takes >120ms to
  start advancing fails its probe but keeps the budget slot. Reviewed and accepted: the
  next card's optimistic probe re-blesses it at zero budget cost, and the slot
  accounting is correct anyway (a live construction counts against WebKit's cap
  regardless of probe outcome).
- **Pre-existing latency items** (untouched by these commits, candidates for a later
  tuning pass): recovery serializes before the context-independent fetch could start;
  a probe-fail-then-recover playback fetches and decodes the same clip twice; the 40ms
  settle before probing is kept even after an awaited resume.

## How To Interpret The Next Debug Report

The next useful report should be a screenshot of the debug overlay after a freeze.
Read the **last line** first; it is the last operation started before the WebView
wedged.

- Last line contains **`newAudioCtx before constructor`** → synchronous
  `new AudioContext()` itself is the likely trigger, even without prior `close()`.
- Last line contains **`recover old resume before`** or
  **`recover newborn resume before`** → `resume()` on a sick/suspended context is the
  likely trigger.
- Last line contains **`webAudio before decodeAudioData`** → optimistic decoding on a
  bad-but-`running` context is the likely trigger.
- Last line contains **`webAudio before source.start`** → starting a decoded
  `BufferSourceNode` is the likely trigger.
- Last line contains **`probe before first currentTime`** or
  **`probe before second currentTime`** → even the clock probe read may be involved.
- If the freeze happens but the screenshot does **not** show
  `ios-audio-debug-2026-06-26-a`, the user is not running the debug template; first
  verify install → note-type update → sync → full AnkiMobile relaunch.
- If the debug build produces no freeze in several sessions, that does **not** prove
  the issue is fixed; instrumentation may have shifted timing. It only means the next
  step needs either another field report or a less intrusive probe.
