# iOS Audio Debug Overlay Handoff

Status as of 2026-07-01: **rebased onto v5 `main` at `56de8de`**. The debug overlay now observes the v5 lifecycle rule: one setup-time `AudioContext` construction attempt, no post-setup replacement path, no cooldown, and no newborn-context resume arm. The overlay remains diagnostic only; it adds breadcrumbs and the visible panel without changing audio policy.

## Why this exists

The production no-`close()` / budgeted-construction v4 fix (`b47cd43` + `89ba3fc`) did not conclusively end the iOS AnkiMobile freeze. The first field report from the June debug build captured the freeze with final breadcrumb `newAudioCtx before constructor` in the old replacement path, proving that post-setup construction during audio-stack contention can wedge the WebView.

v5 fixes that class by deleting post-setup construction. This branch keeps the overlay alive on top of v5 so a future field screenshot can identify any remaining risky operation without reintroducing the old construction behavior.

## Debug build shipped

- Branch: `ios-audio-debug-overlay`
- Base after rebase: `main` @ `56de8de` (`Never construct an AudioContext after card setup (iOS freeze v5)`)
- Visible template build id: `ios-audio-debug-2026-07-01-a`
- Remote branch: `origin/ios-audio-debug-overlay`
- Debug addon package: not rebuilt. The already-shipped addon still points `_BASE_URL` at this branch, so the user only needs to re-run the MvJ note-type update to fetch the rebased template.
- Original package: `mvj-note-type-ios-audio-debug-2026-06-26.ankiaddon`
- Google Drive share link: <https://drive.google.com/file/d/1kvtyoxBqv2PJD4QB26qifz9yx5fcXygm/view?usp=drivesdk>
- Direct download: <https://drive.google.com/uc?id=1kvtyoxBqv2PJD4QB26qifz9yx5fcXygm&export=download>

The debug addon keeps package id `mvj_note_type`, so it installs over the normal addon. Its `addon/notetype.py` points `_BASE_URL` at:

```text
https://raw.githubusercontent.com/mattvsjapan/mvj-notetype/ios-audio-debug-overlay/note-types/mvj/
```

Installing the addon alone does not update existing card templates. The user must run the note-type update after this branch is pushed.

## User instructions

1. If the debug addon is not already installed, install it over the existing addon on Anki desktop.
2. Restart Anki if prompted.
3. Open MvJ Note Type settings.
4. Run the note-type update/install action.
5. Sync.
6. Fully kill and relaunch AnkiMobile. Background/foreground is not enough.
7. Confirm the overlay shows `ios-audio-debug-2026-07-01-a`.
8. Review normally.
9. If it freezes, screenshot the card with the debug overlay visible.
10. Report front/back, autoplay/manual tap, approximate card number, and whether audio started.

Rollback:

1. Reinstall the normal addon.
2. Run the normal note-type update.
3. Sync.
4. Fully kill and relaunch AnkiMobile.
5. Confirm the debug overlay/build id is gone.

## Overlay behavior

The overlay is an unconditional debug-branch panel:

- DOM id: `__iosAudioDebugPanel`
- Build id shown: `ios-audio-debug-2026-07-01-a`
- Position: fixed at top of card
- Max height: `34vh`
- `pointer-events: none`, so it should not block taps
- Shows the last 8 events; the last line is the most important

It writes a breadcrumb immediately before each risky WebKit audio operation that remains in v5. If WebKit hard-freezes, JavaScript stops, so the last visible breadcrumb is the evidence.

## How to interpret the next screenshot

Read the last overlay line first.

| Last breadcrumb | Interpretation |
| --- | --- |
| `newAudioCtx before constructor` | Expected once during fresh document/card setup. In v5 this breadcrumb can only come from the setup-time choke point. If it appears as the final breadcrumb mid-session, that is itself a finding: either the v5 template did not load or a new post-setup constructor call site was introduced. |
| `recover old resume before` | `resume()` on the existing suspended/interrupted context is the likely remaining trigger. |
| `webAudio before decodeAudioData` | Optimistic decode on a bad-but-`running` context is the likely trigger. |
| `webAudio before source.start` | `BufferSourceNode.start()` is the likely trigger. |
| `probe before first currentTime` or `probe before second currentTime` | Even the clock probe read may be involved. |
| `fresh before audio.play` | The degraded `<audio>` fallback path itself needs investigation. |
| No `ios-audio-debug-2026-07-01-a` in the screenshot | The user is not running the rebased v5 debug template; re-check install → note-type update → sync → full AnkiMobile relaunch. |

Deleted v4 breadcrumbs such as `recover replacement enter`, `recover replacement assigned`, and `recover newborn resume before` should not appear on the v5 overlay.

If the debug build does not freeze, do not conclude the bug is fixed. The overlay may alter timing enough to hide the race.

## Verification for the rebased branch

The branch should be checked with:

```bash
python3 addon/tests/test_audio_ctx_lifecycle.py
python3 addon/tests/test_ios_audio_debug_overlay.py
git diff main -- note-types/chinese/front.html
```

Expected results:

- `test_audio_ctx_lifecycle.py` passes 8/8, preserving v5 lifecycle semantics.
- `test_ios_audio_debug_overlay.py` passes 8/8, preserving the overlay breadcrumbs that still exist on v5.
- The Chinese template diff is empty; Chinese has no overlay and stays identical to main's v5 copy.

## Working tree note

This branch is consumed through raw GitHub template URLs by the debug addon's `_BASE_URL`. The `.ankiaddon` package is intentionally not rebuilt for the v5 overlay rebase.
