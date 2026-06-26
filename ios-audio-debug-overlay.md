# iOS Audio Debug Overlay Handoff

Status as of 2026-06-26: **debug build delivered; waiting for user field report.**

## Why this exists

The production no-`close()` / budgeted-construction fix (`b47cd43` + `89ba3fc`) did not conclusively end the iOS AnkiMobile freeze. The user later reported the same error/freeze once around the 8th card after an apparent template update.

Matt rejected `<audio>` fallback latency as a final solution. The current task is therefore diagnostic, not a workaround: identify the exact WebKit audio operation that wedges the card WebView.

## Debug build shipped

- Branch: `ios-audio-debug-overlay`
- Commit: `dcf0b29` — `Add iOS audio debug overlay`
- Remote branch: pushed to `origin/ios-audio-debug-overlay`
- Package: `mvj-note-type-ios-audio-debug-2026-06-26.ankiaddon`
- Google Drive share link: <https://drive.google.com/file/d/1kvtyoxBqv2PJD4QB26qifz9yx5fcXygm/view?usp=drivesdk>
- Direct download: <https://drive.google.com/uc?id=1kvtyoxBqv2PJD4QB26qifz9yx5fcXygm&export=download>

The debug addon keeps package id `mvj_note_type`, so it installs over the normal addon. Its `addon/notetype.py` points `_BASE_URL` at:

```text
https://raw.githubusercontent.com/mattvsjapan/mvj-notetype/ios-audio-debug-overlay/note-types/mvj/
```

That means the user must install the debug addon **and then run the MvJ note-type update** on desktop. Installing the addon alone does not update existing card templates.

## User instructions already given / expected

1. Install the debug `.ankiaddon` over the existing addon on Anki desktop.
2. Restart Anki if prompted.
3. Open MvJ Note Type settings.
4. Run the note-type update/install action.
5. Sync.
6. Fully kill and relaunch AnkiMobile. Background/foreground is not enough.
7. Review normally.
8. If it freezes, screenshot the card with the debug overlay visible.
9. Report front/back, autoplay/manual tap, approximate card number, and whether audio started.

Rollback:

1. Reinstall the normal addon.
2. Run the normal note-type update.
3. Sync.
4. Fully kill and relaunch AnkiMobile.
5. Confirm the debug overlay/build id is gone.

## Overlay behavior

The overlay is an unconditional debug-branch panel:

- DOM id: `__iosAudioDebugPanel`
- Build id shown: `ios-audio-debug-2026-06-26-a`
- Position: fixed at top of card
- Max height: `34vh`
- `pointer-events: none`, so it should not block taps
- Shows the last 8 events; the last line is the most important

It writes a breadcrumb **immediately before** each risky WebKit audio call. If WebKit hard-freezes, JavaScript stops, so the last visible breadcrumb is the evidence.

## How to interpret the next screenshot

Read the last overlay line first.

- `newAudioCtx before constructor` → bare synchronous `new AudioContext()` is likely the trigger.
- `recover old resume before` → `resume()` on the existing sick context is likely the trigger.
- `recover newborn resume before` → `resume()` on a newly constructed context is likely the trigger.
- `webAudio before decodeAudioData` → optimistic decode on a bad-but-`running` context is likely the trigger.
- `webAudio before source.start` → `BufferSourceNode.start()` is likely the trigger.
- `probe before first currentTime` or `probe before second currentTime` → even the clock probe read may be involved.
- No `ios-audio-debug-2026-06-26-a` in the screenshot → user is not running the debug template; re-check install → note-type update → sync → full AnkiMobile relaunch.

If the debug build does not freeze, do not conclude the bug is fixed. The overlay may alter timing enough to hide the race.

## Verification already done

- Plan review passed on round 3.
- Code review passed: no blocking findings.
- `python3 addon/tests/test_ios_audio_debug_overlay.py` passed 8/8.
- Extracted 15 script blocks from `note-types/mvj/front.html` and `note-types/mvj/back.html`; `node --check` passed for all.
- Package zip was inspected: same package/name, debug `_BASE_URL`, dev/test files excluded.
- Remote raw URLs were verified after push for `front.html`, `back.html`, `css.css`, and all MvJ font files. Remote `front.html` contains build id `ios-audio-debug-2026-06-26-a`.

## Working tree note

At the time this handoff was written, the repo was on branch `ios-audio-debug-overlay`, pushed to origin. There were pre-existing unrelated local changes/untracked docs in the working tree (`.gitignore`, root freeze docs). Do not assume those are part of the debug overlay commit unless committed separately.
