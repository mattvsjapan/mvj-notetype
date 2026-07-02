"""Static guards for the one-off iOS Audio debug overlay.

Run directly from the repo root:

    python3 addon/tests/test_ios_audio_debug_overlay.py

These tests do not prove iOS behavior. They prove the debug branch keeps the
freeze-critical audio control flow recognizable while placing breadcrumbs
immediately before the risky WebKit audio calls we need to isolate.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FRONT = (ROOT / "note-types" / "mvj" / "front.html").read_text()
BACK = (ROOT / "note-types" / "mvj" / "back.html").read_text()
NOTETYPE = (ROOT / "addon" / "notetype.py").read_text()


def _assert_contains(text: str, needle: str, label: str) -> None:
    assert needle in text, f"missing {label}: {needle}"


def _assert_count(text: str, needle: str, expected: int, label: str) -> None:
    actual = text.count(needle)
    assert actual == expected, f"{label}: expected {expected}, got {actual} for {needle!r}"


def _assert_order(text: str, needles: list[str], label: str) -> None:
    pos = -1
    for needle in needles:
        nxt = text.find(needle, pos + 1)
        assert nxt != -1, f"{label}: missing after position {pos}: {needle}"
        pos = nxt


def _assert_local_snippet(snippet: str, label: str) -> None:
    assert snippet in FRONT, f"missing immediate local snippet for {label}"


def _executable_text(text: str) -> str:
    lines = []
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("//"):
            continue
        lines.append(line)
    return "\n".join(lines)


def _debug_helper_body() -> str:
    start = FRONT.index("// iOS Audio freeze diagnostic overlay")
    end = FRONT.index("// AnkiDroid gate", start)
    return FRONT[start:end]


def test_debug_identity_and_updater() -> None:
    _assert_contains(FRONT, "ios-audio-debug-2026-07-01-a", "visible debug build id")
    _assert_contains(FRONT, "__iosAudioDebugPanel", "overlay panel id")
    _assert_contains(
        NOTETYPE,
        "mattvsjapan/mvj-notetype/ios-audio-debug-overlay/note-types/mvj/",
        "debug branch template URL",
    )
    assert "mattvsjapan/mvj-notetype/main/note-types/mvj/" not in NOTETYPE, (
        "debug package updater must not point at main"
    )


def test_no_new_close_or_suspend_calls() -> None:
    code = _executable_text(FRONT + "\n" + BACK)
    assert ".close(" not in code, "debug template must not call AudioContext.close()"
    assert ".suspend(" not in code, "debug template must not call AudioContext.suspend()"


def test_debug_helper_does_not_read_current_time() -> None:
    helper = _debug_helper_body()
    assert "currentTime" not in helper, "debug helper must not read AudioContext.currentTime"


def test_risky_call_counts() -> None:
    _assert_count(FRONT, "return new Ctor();", 1, "AudioContext constructor")
    _assert_count(FRONT, "function createReplacement()", 0, "deleted replacement helper")
    _assert_count(FRONT, "recover newborn resume before", 0, "deleted newborn resume breadcrumb")
    _assert_count(FRONT, "var pr = old.resume();", 1, "old-context resume")
    _assert_count(FRONT, "ctx.currentTime", 2, "probe currentTime reads")
    _assert_count(FRONT, "return actx.decodeAudioData(buf);", 1, "decodeAudioData")
    _assert_count(FRONT, "source.start();", 1, "BufferSource start")
    _assert_count(FRONT, "var p = a.play();", 1, "fresh audio play")


def test_immediate_breadcrumbs_before_risky_calls() -> None:
    _assert_local_snippet(
        "window.__iosAudioDbg && window.__iosAudioDbg('newAudioCtx before constructor');\n"
        "        return new Ctor();",
        "new AudioContext constructor",
    )
    _assert_local_snippet(
        "window.__iosAudioDbg && window.__iosAudioDbg('recover old resume before');\n"
        "                var pr = old.resume();",
        "old resume",
    )
    _assert_local_snippet(
        "window.__iosAudioDbg && window.__iosAudioDbg('probe before first currentTime');\n"
        "        var t0 = ctx.currentTime;",
        "first currentTime read",
    )
    _assert_local_snippet(
        "window.__iosAudioDbg && window.__iosAudioDbg('probe before second currentTime');\n"
        "                ok = ctx.currentTime > t0;",
        "second currentTime read",
    )
    _assert_local_snippet(
        "window.__iosAudioDbg && window.__iosAudioDbg('webAudio before decodeAudioData');\n"
        "            return actx.decodeAudioData(buf);",
        "decodeAudioData",
    )
    _assert_local_snippet(
        "window.__iosAudioDbg && window.__iosAudioDbg('webAudio before source.start');\n"
        "                source.start();",
        "source.start",
    )
    _assert_local_snippet(
        "window.__iosAudioDbg && window.__iosAudioDbg('fresh before audio.play');\n"
        "    var p = a.play();",
        "fallback audio.play",
    )


def test_play_mobile_branch_sequence_unchanged() -> None:
    _assert_order(
        FRONT,
        [
            "function viaFresh() {",
            "var fa = window.__freshPlay(src, btn, scope);",
            "fa.addEventListener('pause', function() {",
            "if (window.__isAndroid && window.__isAndroid()) {",
            "return viaFresh();",
            "function viaRecoveredWebAudio(expectedGen) {",
            "return window.__audioCtxRecover(scope, expectedGen).then(function(ok) {",
            "return window.__webAudioPlay(src, btn, expectedGen, scope);",
            "if (window.__isCardScopeActive(scope)) return viaFresh();",
            "if (!ios) {",
            "return window.__webAudioPlay(src, btn, window.__webAudioGen, scope);",
            "return viaFresh();",
            "if (window.__audioCtxState === 'healthy') {",
            "return viaRecoveredWebAudio(window.__webAudioGen);",
            "if (window.__audioCtxState === 'failed') {",
            "return viaFresh();",
            "if (!ctx || ctx.state !== 'running') {",
            "return viaRecoveredWebAudio(window.__webAudioGen);",
            "var gen = window.__webAudioGen;",
            "var optimistic = window.__webAudioPlay(src, btn, gen, scope);",
            "if (optimistic && optimistic['catch']) optimistic['catch'](function(){});",
            "return window.__audioCtxProbe(80).then(function(healthy) {",
            "window.__audioCtxState = 'healthy';",
            "return optimistic;",
            "var internalCancel = gen === window.__webAudioGen;",
            "window.__stopAllAudio();",
            "if (internalCancel && opts.genRef) opts.genRef.gen = window.__webAudioGen;",
            "return viaRecoveredWebAudio(internalCancel ? window.__webAudioGen : gen);",
        ],
        "__playMobile branch/cancellation sequence",
    )


def test_recovery_and_web_audio_sequences_unchanged() -> None:
    _assert_order(
        FRONT,
        [
            "if (window.__webAudioSource) {",
            "try { window.__webAudioSource.stop(); } catch(e) {}",
            "var old = window.__audioCtx;",
            "function probeCtx(ctx) {",
            "if (old && (old.state === 'suspended' || old.state === 'interrupted') && old.resume) {",
            "var pr = old.resume();",
            "return;",
            "resolve(false);",
            "window.__audioCtxState = ok ? 'healthy' : 'failed';",
        ],
        "__audioCtxRecover recovery sequence",
    )
    _assert_order(
        FRONT,
        [
            "return fetch(src)",
            "return r.arrayBuffer();",
            "return actx.decodeAudioData(buf);",
            "if ((gen !== undefined && gen !== window.__webAudioGen)",
            "var source = actx.createBufferSource();",
            "source.buffer = audioBuf;",
            "source.connect(actx.destination);",
            "source.start();",
            "window.__webAudioSource = source;",
            "source.onended = function() {",
        ],
        "__webAudioPlay fetch/decode/start sequence",
    )


def test_autoplay_sequences_unchanged() -> None:
    _assert_contains(
        FRONT,
        "window.__autoplayItems('.audio-row .audio-item[data-side=\"front\"]', function(type) {",
        "front autoplay selector",
    )
    _assert_contains(
        BACK,
        "window.__autoplayItems('.audio-row .audio-item:not([data-side=\"off\"])', function(type, item) {",
        "back autoplay selector",
    )
    _assert_order(
        FRONT,
        [
            "var genRef = { gen: window.__webAudioGen };",
            "if (genRef.gen !== window.__webAudioGen || !window.__isCardScopeActive(scope)) return;",
            "window.__playMobile(entry.src, entry.btn, scope, { autoplay: true, genRef: genRef })",
            "if (genRef.gen === window.__webAudioGen",
        ],
        "__autoplayItems genRef sequence",
    )


def main() -> int:
    tests = [
        ("debug identity/updater", test_debug_identity_and_updater),
        ("no close/suspend", test_no_new_close_or_suspend_calls),
        ("helper avoids currentTime", test_debug_helper_does_not_read_current_time),
        ("risky call counts", test_risky_call_counts),
        ("immediate breadcrumbs", test_immediate_breadcrumbs_before_risky_calls),
        ("playMobile sequence", test_play_mobile_branch_sequence_unchanged),
        ("recover/webAudio sequence", test_recovery_and_web_audio_sequences_unchanged),
        ("autoplay sequence", test_autoplay_sequences_unchanged),
    ]
    failed = 0
    for label, fn in tests:
        try:
            fn()
            print(f"PASS  {label}")
        except AssertionError as e:
            failed += 1
            print(f"FAIL  {label}: {e}")
        except Exception as e:  # noqa: BLE001
            failed += 1
            print(f"ERROR {label}: {type(e).__name__}: {e}")
    print()
    print(f"{len(tests) - failed}/{len(tests)} passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
