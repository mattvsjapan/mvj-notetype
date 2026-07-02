"""Headless guards for the iOS AudioContext v5 lifecycle.

Run directly from the repo root:

    python3 addon/tests/test_audio_ctx_lifecycle.py

The tests extract and execute the real template JavaScript in Node with a small
browser stub. They do not prove the real iOS WebKit audio runtime; they prove the
mechanizable v5 invariants the templates can enforce headlessly.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TEMPLATE_PATHS = {
    "mvj": ROOT / "note-types" / "mvj" / "front.html",
    "chinese": ROOT / "note-types" / "chinese" / "front.html",
}
TEMPLATES = {name: path.read_text() for name, path in TEMPLATE_PATHS.items()}


class TemplateParts:
    def __init__(self, html: str) -> None:
        self.html = html
        self.scripts = _extract_scripts(html)
        self.lifecycle = _lifecycle_block(html)
        self.scope_guard = _assignment(html, "window.__isCardScopeActive = function")
        self.stop_all_audio = _assignment(html, "window.__stopAllAudio = function")
        self.start_playing = _assignment(html, "window.__startPlaying = function")
        self.fresh_play = _assignment(html, "window.__freshPlay = function")
        self.web_audio_play = _assignment(html, "window.__webAudioPlay = function")
        self.play_mobile = _commented_assignment(
            html,
            "// Hybrid dispatch by call kind.",
            "window.__playMobile = function",
        )




BROWSER_STUB = r"""
const assert = require('assert');
global.window = global;

class FakeClassList {
    constructor() { this.items = new Set(); }
    add(name) { this.items.add(name); }
    remove(name) { this.items.delete(name); }
    contains(name) { return this.items.has(name); }
    toggle(name, force) {
        const next = force === undefined ? !this.items.has(name) : !!force;
        if (next) this.items.add(name); else this.items.delete(name);
        return next;
    }
}

class FakeEvent {
    constructor(type) { this.type = type; }
}
global.Event = FakeEvent;

function makeNode() {
    return {
        isConnected: true,
        classList: new FakeClassList(),
        style: {},
        children: [],
        parentNode: null,
        appendChild(node) { node.parentNode = this; this.children.push(node); return node; },
        removeChild(node) { this.children = this.children.filter((n) => n !== node); node.parentNode = null; },
        querySelectorAll() { return []; },
        querySelector() { return null; },
        addEventListener() {},
        removeEventListener() {},
        closest() { return null; },
        getAttribute() { return null; },
        setAttribute() {},
        removeAttribute() {},
        load() {},
        pause() {},
        remove() { this.isConnected = false; if (this.parentNode) this.parentNode.removeChild(this); },
    };
}

const documentElement = makeNode();
const body = makeNode();
const cardRoot = makeNode();
body.appendChild(cardRoot);
global.document = {
    documentElement,
    body,
    visibilityState: 'visible',
    addEventListener() {},
    removeEventListener() {},
    createElement() { return makeNode(); },
    querySelector(selector) { return selector === '.card-inner' ? cardRoot : null; },
    querySelectorAll() { return []; },
};

global.navigator = { audioSession: { type: '' }, userAgent: 'iPhone', userAgentData: null };
window.matchMedia = function(query) {
    return { matches: query.indexOf('(hover: none)') !== -1 };
};
global.MutationObserver = class {
    observe() {}
    disconnect() {}
};
global.requestAnimationFrame = function(fn) { return setTimeout(fn, 0); };

let fakeAudios = [];
class FakeAudio {
    constructor(src) {
        this.src = src;
        this.style = {};
        this.listeners = {};
        this.paused = true;
        this.readyState = 4;
        this.parentNode = null;
        fakeAudios.push(this);
        window.__lastFreshAudio = this;
    }
    addEventListener(type, cb, opts) {
        if (!this.listeners[type]) this.listeners[type] = [];
        this.listeners[type].push({ cb, once: !!(opts && opts.once) });
    }
    removeEventListener(type, cb) {
        if (!this.listeners[type]) return;
        this.listeners[type] = this.listeners[type].filter((entry) => entry.cb !== cb);
    }
    dispatchEvent(event) {
        const type = typeof event === 'string' ? event : event.type;
        const entries = (this.listeners[type] || []).slice();
        for (const entry of entries) entry.cb(event);
        if (this.listeners[type]) this.listeners[type] = this.listeners[type].filter((entry) => !entry.once);
    }
    play() {
        this.paused = false;
        if (window.__fakeAudioAutoEnd !== false) {
            setTimeout(() => this.dispatchEvent(new Event('ended')), 0);
        }
        return Promise.resolve();
    }
    pause() {
        this.paused = true;
        this.dispatchEvent(new Event('pause'));
    }
    load() {}
    removeAttribute(name) { if (name === 'src') this.src = ''; }
    remove() { if (this.parentNode) this.parentNode.removeChild(this); }
}
global.Audio = FakeAudio;

class FakeSource {
    constructor() {
        this.buffer = null;
        this.onended = null;
        this.stopped = false;
        window.__lastSource = this;
    }
    connect() {}
    start() {
        window.__sourceStarts = (window.__sourceStarts || 0) + 1;
        if (window.__fakeSourceAutoEnd !== false) {
            setTimeout(() => { if (this.onended) this.onended(); }, 0);
        }
    }
    stop() {
        this.stopped = true;
        window.__sourceStops = (window.__sourceStops || 0) + 1;
        if (this.onended) this.onended();
    }
}

function makeRunningCtx(advances) {
    const ctx = {
        state: 'running',
        destination: {},
        _t0: Date.now(),
        decodeAudioData() { return Promise.resolve({}); },
        createBufferSource() { return new FakeSource(); },
    };
    Object.defineProperty(ctx, 'currentTime', {
        get() { return advances ? (Date.now() - ctx._t0) / 1000 : 1; }
    });
    return ctx;
}

function makeScope() {
    const root = makeNode();
    const scope = { root, stale: false };
    window.__currentCardScope = scope;
    return scope;
}

function delay(ms) { return new Promise((resolve) => setTimeout(resolve, ms)); }

global.fetch = function() {
    return Promise.resolve({ arrayBuffer() { return Promise.resolve(new ArrayBuffer(8)); } });
};
"""


def _extract_scripts(html: str) -> list[str]:
    return re.findall(r"<script[^>]*>(.*?)</script>", html, flags=re.IGNORECASE | re.DOTALL)





def _lifecycle_block(text: str) -> str:
    start_marker = "// Route Web Audio through media channel"
    end_marker = "    document.addEventListener('visibilitychange', window.__audioCtxVisHandler);\n}"
    start = text.index(start_marker)
    end = text.index(end_marker, start) + len(end_marker)
    return text[start:end]

def _commented_assignment(text: str, comment_marker: str, assignment_marker: str) -> str:
    start = text.index(comment_marker)
    assignment_start = text.index(assignment_marker, start)
    return text[start:assignment_start] + _assignment(text, assignment_marker)


def _assignment(text: str, marker: str) -> str:
    start = text.index(marker)
    open_brace = text.index("{", start)
    close_brace = _matching_brace(text, open_brace)
    semi = text.index(";", close_brace)
    return text[start : semi + 1]


def _matching_brace(text: str, open_pos: int) -> int:
    depth = 0
    state = "code"
    quote = ""
    escape = False
    i = open_pos
    while i < len(text):
        ch = text[i]
        nxt = text[i + 1] if i + 1 < len(text) else ""
        if state == "line_comment":
            if ch == "\n":
                state = "code"
        elif state == "block_comment":
            if ch == "*" and nxt == "/":
                state = "code"
                i += 1
        elif state == "string":
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == quote:
                state = "code"
        else:
            if ch == "/" and nxt == "/":
                state = "line_comment"
                i += 1
            elif ch == "/" and nxt == "*":
                state = "block_comment"
                i += 1
            elif ch in "'\"`":
                state = "string"
                quote = ch
            elif ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    return i
        i += 1
    raise ValueError("no matching brace")


def _strip_js_comments_and_strings(code: str) -> str:
    out: list[str] = []
    state = "code"
    quote = ""
    escape = False
    i = 0
    while i < len(code):
        ch = code[i]
        nxt = code[i + 1] if i + 1 < len(code) else ""
        if state == "line_comment":
            if ch == "\n":
                out.append("\n")
                state = "code"
            else:
                out.append(" ")
        elif state == "block_comment":
            if ch == "*" and nxt == "/":
                out.extend("  ")
                state = "code"
                i += 1
            elif ch == "\n":
                out.append("\n")
            else:
                out.append(" ")
        elif state == "string":
            if ch == "\n":
                out.append("\n")
            else:
                out.append(" ")
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == quote:
                state = "code"
        else:
            if ch == "/" and nxt == "/":
                out.extend("  ")
                state = "line_comment"
                i += 1
            elif ch == "/" and nxt == "*":
                out.extend("  ")
                state = "block_comment"
                i += 1
            elif ch in "'\"`":
                out.append(" ")
                state = "string"
                quote = ch
                escape = False
            else:
                out.append(ch)
        i += 1
    return "".join(out)


PARTS = {name: TemplateParts(html) for name, html in TEMPLATES.items()}


def _node_program(name: str, setup: str, body: str, *, helpers: bool) -> str:
    parts = PARTS[name]
    helper_code = ""
    if helpers:
        helper_code = "\n".join(
            [
                parts.stop_all_audio,
                parts.start_playing,
                parts.fresh_play,
                parts.web_audio_play,
                parts.play_mobile,
            ]
        )
    return "\n".join(
        [
            BROWSER_STUB,
            setup,
            parts.lifecycle,
            parts.scope_guard,
            helper_code,
            "const scope = makeScope();",
            "(async function(){",
            body,
            "})().then(() => {}, (err) => { console.error(err && err.stack || err); process.exit(1); });",
        ]
    )


def _run_node(code: str) -> None:
    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False) as tmp:
        tmp.write(code)
        tmp_path = tmp.name
    try:
        result = subprocess.run(["node", tmp_path], text=True, capture_output=True, timeout=10)
    finally:
        os.unlink(tmp_path)
    if result.returncode != 0:
        raise AssertionError((result.stdout + result.stderr).strip())


def _run_node_check(script: str, label: str) -> None:
    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False) as tmp:
        tmp.write(script)
        tmp_path = tmp.name
    try:
        result = subprocess.run(["node", "--check", tmp_path], text=True, capture_output=True, timeout=10)
    finally:
        os.unlink(tmp_path)
    if result.returncode != 0:
        raise AssertionError(f"{label}: {(result.stdout + result.stderr).strip()}")


def _ctx_setup(*, throwing: bool = False) -> str:
    if throwing:
        return r"""
let constructorCalls = 0;
class FakeAudioContext {
    constructor() { constructorCalls += 1; throw new Error('constructor failed'); }
}
window.AudioContext = FakeAudioContext;
"""
    return r"""
let constructorCalls = 0;
class FakeAudioContext {
    constructor() { constructorCalls += 1; return makeRunningCtx(true); }
}
window.AudioContext = FakeAudioContext;
"""


def test_row_1_lifecycle_runtime() -> None:
    for name in TEMPLATES:
        normal_body = r"""
assert.strictEqual(constructorCalls, 1, 'eager setup constructs exactly once');
assert.strictEqual(window.__audioCtxCreates, 1, 'setup attempt is counted');
assert.strictEqual(window.__audioCtxBudget, 1, 'v5 budget is one attempt');
assert.strictEqual(window.__newAudioCtx(), null, 'post-setup call is mechanically refused');
assert.strictEqual(constructorCalls, 1, 'refused post-setup call does not touch constructor');

constructorCalls = 0;
window.__audioCtx = undefined;
window.__audioCtxState = 'unknown';
let ok = await window.__audioCtxRecover(scope, window.__webAudioGen);
assert.strictEqual(ok, false, 'missing context degrades false');
assert.strictEqual(constructorCalls, 0, 'missing context recovery never constructs');
assert.strictEqual(window.__audioCtxState, 'failed', 'missing context marks failed for fallback');

constructorCalls = 0;
window.__audioCtx = makeRunningCtx(false);
window.__audioCtxState = 'unknown';
ok = await window.__audioCtxRecover(scope, window.__webAudioGen);
assert.strictEqual(ok, false, 'running-stalled context degrades false');
assert.strictEqual(constructorCalls, 0, 'running-stalled recovery never constructs');

constructorCalls = 0;
let resumeCalls = 0;
const resumable = {
    state: 'suspended',
    destination: {},
    _t0: Date.now(),
    resume() { resumeCalls += 1; this.state = 'running'; this._t0 = Date.now(); return Promise.resolve(); },
    decodeAudioData() { return Promise.resolve({}); },
    createBufferSource() { return { connect(){}, start(){}, stop(){}, onended: null }; },
};
Object.defineProperty(resumable, 'currentTime', { get() { return resumable.state === 'running' ? (Date.now() - resumable._t0) / 1000 : 0; } });
window.__audioCtx = resumable;
window.__audioCtxState = 'unknown';
ok = await window.__audioCtxRecover(scope, window.__webAudioGen);
assert.strictEqual(ok, true, 'suspended context resumes in place');
assert.strictEqual(resumeCalls, 1, 'resume called once');
assert.strictEqual(constructorCalls, 0, 'resume-in-place never constructs');
assert.strictEqual(window.__audioCtx, resumable, 'resumed context object is kept');

constructorCalls = 0;
const hanging = { state: 'suspended', resume() { return new Promise(() => {}); } };
Object.defineProperty(hanging, 'currentTime', { get() { return 0; } });
window.__audioCtx = hanging;
window.__audioCtxState = 'unknown';
const started = Date.now();
ok = await window.__audioCtxRecover(scope, window.__webAudioGen);
assert.strictEqual(ok, false, 'hanging resume degrades false');
assert.ok(Date.now() - started >= 250, 'hanging resume waits for the bounded 300ms arm');
assert.strictEqual(constructorCalls, 0, 'hanging resume never constructs');
"""
        _run_node(_node_program(name, _ctx_setup(), normal_body, helpers=False))

        throwing_body = r"""
assert.strictEqual(constructorCalls, 1, 'throwing eager setup attempts constructor once');
assert.strictEqual(window.__audioCtxCreates, 1, 'throwing constructor burns the only attempt');
assert.strictEqual(window.__audioCtx, undefined, 'failed setup leaves no context');
assert.strictEqual(window.__newAudioCtx(), null, 'later call after throw is refused');
assert.strictEqual(constructorCalls, 1, 'later call after throw does not touch constructor');
"""
        _run_node(_node_program(name, _ctx_setup(throwing=True), throwing_body, helpers=False))


def test_row_1b_static_single_construction() -> None:
    for name, parts in PARTS.items():
        stripped = _strip_js_comments_and_strings("\n".join(parts.scripts))
        direct = re.findall(r"new\s+(?:window\.)?(?:webkit)?AudioContext\s*\(", stripped)
        assert not direct, f"{name}: direct AudioContext constructor call outside Ctor alias: {direct}"
        assert stripped.count("new Ctor(") == 1, f"{name}: expected exactly one new Ctor()"
        refs = re.findall(r"__newAudioCtx\b", stripped)
        assert len(refs) == 2, f"{name}: expected definition + eager call only, got {len(refs)}"
        assert re.search(r"window\.__audioCtxBudget\s*=\s*1\s*;", stripped), f"{name}: budget is not 1"
        fn = _assignment(parts.html, "window.__newAudioCtx = function")
        creates_pos = fn.index("window.__audioCtxCreates++")
        ctor_pos = fn.index("new Ctor()")
        assert creates_pos < ctor_pos, f"{name}: attempt counter must precede constructor"


def _play_setup() -> str:
    return _ctx_setup()


def _play_spy_body(scenario: str) -> str:
    return r"""
function installSpies() {
    window.__calls = { fresh: 0, start: 0, recover: 0, web: 0, stopAll: 0 };
    const origFresh = window.__freshPlay;
    window.__freshPlay = function() { window.__calls.fresh += 1; return origFresh.apply(this, arguments); };
    const origStart = window.__startPlaying;
    window.__startPlaying = function() { window.__calls.start += 1; return origStart.apply(this, arguments); };
    const origRecover = window.__audioCtxRecover;
    window.__audioCtxRecover = function() { window.__calls.recover += 1; return origRecover.apply(this, arguments); };
    const origWeb = window.__webAudioPlay;
    window.__webAudioPlay = function() { window.__calls.web += 1; return origWeb.apply(this, arguments); };
    const origStop = window.__stopAllAudio;
    window.__stopAllAudio = function() { window.__calls.stopAll += 1; return origStop.apply(this, arguments); };
}
installSpies();
""" + scenario


def test_row_2_play_mobile_branches() -> None:
    scenarios = [
        (
            "Android gate uses fresh audio",
            r"""
document.documentElement.classList.add('android');
constructorCalls = 0;
await window.__playMobile('android.mp3', null, scope);
assert.deepStrictEqual(window.__calls, { fresh: 1, start: 1, recover: 0, web: 0, stopAll: 0 });
assert.strictEqual(constructorCalls, 0, 'Android playback does not construct');
""",
        ),
        (
            "Desktop running context uses Web Audio",
            r"""
navigator.audioSession = null;
window.__audioCtx = makeRunningCtx(true);
window.__audioCtxState = 'unknown';
constructorCalls = 0;
await window.__playMobile('desktop-web.mp3', null, scope);
assert.strictEqual(window.__calls.web, 1, 'desktop running ctx uses web audio');
assert.strictEqual(window.__calls.fresh, 0, 'desktop running ctx does not use fresh audio');
assert.strictEqual(window.__calls.recover, 0, 'desktop path does not recover');
assert.strictEqual(constructorCalls, 0, 'desktop playback does not construct');
""",
        ),
        (
            "Desktop non-running context uses fresh audio",
            r"""
navigator.audioSession = null;
window.__audioCtx = { state: 'suspended' };
window.__audioCtxState = 'unknown';
constructorCalls = 0;
await window.__playMobile('desktop-fresh.mp3', null, scope);
assert.strictEqual(window.__calls.fresh, 1, 'desktop non-running ctx uses fresh audio');
assert.strictEqual(window.__calls.start, 1, 'fresh audio is wired through __startPlaying');
assert.strictEqual(window.__calls.web, 0, 'desktop non-running ctx does not use web audio');
assert.strictEqual(window.__calls.recover, 0, 'desktop path does not recover');
assert.strictEqual(constructorCalls, 0, 'desktop fresh playback does not construct');
""",
        ),
        (
            "iOS missing context recovers false then fresh audio",
            r"""
navigator.audioSession = { type: 'playback' };
window.__audioCtx = undefined;
window.__audioCtxState = 'unknown';
constructorCalls = 0;
await window.__playMobile('ios-missing.mp3', null, scope);
assert.strictEqual(window.__calls.recover, 1, 'iOS missing ctx asks recovery');
assert.strictEqual(window.__calls.fresh, 1, 'iOS missing ctx falls back to fresh audio');
assert.strictEqual(window.__calls.start, 1, 'fresh fallback is wired through __startPlaying');
assert.strictEqual(window.__calls.web, 0, 'missing ctx does not web-play');
assert.strictEqual(constructorCalls, 0, 'iOS missing recovery does not construct');
""",
        ),
        (
            "iOS failed state immediately uses fresh audio",
            r"""
navigator.audioSession = { type: 'playback' };
window.__audioCtx = undefined;
window.__audioCtxState = 'failed';
constructorCalls = 0;
await window.__playMobile('ios-failed.mp3', null, scope);
assert.strictEqual(window.__calls.recover, 0, 'failed state bypasses recovery');
assert.strictEqual(window.__calls.fresh, 1, 'failed state uses fresh audio');
assert.strictEqual(window.__calls.start, 1, 'failed-state fresh fallback is wired');
assert.strictEqual(constructorCalls, 0, 'failed-state playback does not construct');
""",
        ),
    ]
    for name in TEMPLATES:
        for label, scenario in scenarios:
            _run_node(_node_program(name, _play_setup(), _play_spy_body(scenario), helpers=True))


def test_row_3_autoplay_queue_and_stall_degrade() -> None:
    for name in TEMPLATES:
        stall_body = _play_spy_body(
            r"""
navigator.audioSession = { type: 'playback' };
window.__fakeSourceAutoEnd = false;
window.__audioCtx = makeRunningCtx(false);
window.__audioCtxState = 'unknown';
window.__webAudioGen = 7;
const genRef = { gen: window.__webAudioGen };
constructorCalls = 0;
let settled = false;
await window.__playMobile('stall.mp3', null, scope, { autoplay: true, genRef }).then(() => { settled = true; });
assert.strictEqual(settled, true, 'stall path returned promise settles');
assert.strictEqual(window.__calls.web, 1, 'stall path starts optimistic web audio');
assert.strictEqual(window.__sourceStarts, 1, 'optimistic source.start ran once');
assert.strictEqual(window.__calls.stopAll, 1, 'stall path clears optimistic source');
assert.strictEqual(window.__sourceStops, 1, 'optimistic source was stopped');
assert.strictEqual(window.__webAudioSource, null, 'source cleared before fallback completes');
assert.strictEqual(genRef.gen, window.__webAudioGen, 'autoplay genRef resynced after internal cancel');
assert.strictEqual(window.__calls.recover, 1, 'stall path asks recovery after internal cancel');
assert.strictEqual(window.__calls.fresh, 1, 'recover false falls through to fresh fallback');
assert.strictEqual(constructorCalls, 0, 'stall recovery never constructs');
"""
        )
        _run_node(_node_program(name, _play_setup(), stall_body, helpers=True))

        pause_body = _play_spy_body(
            r"""
navigator.audioSession = { type: 'playback' };
window.__fakeAudioAutoEnd = false;
window.__audioCtxState = 'failed';
window.__webAudioGen = 10;
let settled = false;
const p = window.__playMobile('pause.mp3', null, scope).then(() => { settled = true; });
await delay(20);
window.__lastFreshAudio.pause();
await delay(20);
assert.strictEqual(settled, false, 'OS/external pause without gen bump does not settle queue');
window.__webAudioGen += 1;
window.__lastFreshAudio.pause();
await p;
assert.strictEqual(settled, true, 'gen-bumped pause settles queue');
"""
        )
        _run_node(_node_program(name, _play_setup(), pause_body, helpers=True))


def test_row_3b_card_scope_guards() -> None:
    for name in TEMPLATES:
        entry_body = _play_spy_body(
            r"""
const inactive = makeScope();
inactive.stale = true;
await window.__playMobile('inactive.mp3', null, inactive);
assert.deepStrictEqual(window.__calls, { fresh: 0, start: 0, recover: 0, web: 0, stopAll: 0 });
"""
        )
        _run_node(_node_program(name, _play_setup(), entry_body, helpers=True))

        recover_entry_body = r"""
const stale = makeScope();
stale.stale = true;
window.__audioCtxState = 'unknown';
const ok = await window.__audioCtxRecover(stale, window.__webAudioGen);
assert.strictEqual(ok, false, 'stale scope at recovery entry returns false');
assert.strictEqual(window.__audioCtxRecoverToken, undefined, 'stale recovery does not create token');
assert.strictEqual(window.__audioCtxState, 'unknown', 'stale recovery does not change state');
"""
        _run_node(_node_program(name, _ctx_setup(), recover_entry_body, helpers=False))

        stale_mid_body = r"""
window.__audioCtxState = 'unknown';
const ctx = {
    state: 'suspended',
    _t0: Date.now(),
    resume() {
        this.state = 'running';
        this._t0 = Date.now();
        setTimeout(() => { scope.stale = true; scope.root.isConnected = false; }, 10);
        return Promise.resolve();
    },
};
Object.defineProperty(ctx, 'currentTime', { get() { return (Date.now() - ctx._t0) / 1000; } });
window.__audioCtx = ctx;
const ok = await window.__audioCtxRecover(scope, window.__webAudioGen);
assert.strictEqual(ok, false, 'scope stale mid-recovery returns false');
assert.strictEqual(window.__audioCtxState, 'unknown', 'stale mid-recovery does not flip health state');
"""
        _run_node(_node_program(name, _ctx_setup(), stale_mid_body, helpers=False))

        gen_mismatch_body = _play_spy_body(
            r"""
navigator.audioSession = { type: 'playback' };
window.__audioCtx = makeRunningCtx(false);
window.__audioCtxState = 'unknown';
window.__webAudioGen = 30;
setTimeout(() => { window.__webAudioGen += 1; }, 20);
await window.__playMobile('gen-mismatch.mp3', null, scope);
assert.strictEqual(window.__calls.web, 1, 'optimistic web audio started before gen mismatch');
assert.strictEqual(window.__calls.stopAll, 0, 'gen mismatch is external, not internal cancel');
assert.strictEqual(window.__calls.recover, 0, 'gen mismatch at recovered-web-audio entry skips recovery');
assert.strictEqual(window.__calls.fresh, 0, 'gen mismatch at recovered-web-audio entry skips fallback playback');
"""
        )
        _run_node(_node_program(name, _play_setup(), gen_mismatch_body, helpers=True))


def test_row_4_static_no_teardown_or_deleted_paths() -> None:
    for name, parts in PARTS.items():
        stripped = _strip_js_comments_and_strings("\n".join(parts.scripts))
        forbidden_patterns = [
            r"(?:\.|\b)close\s*\(",
            r"(?:\.|\b)suspend\s*\(",
            r"\b__releaseContext\b",
        ]
        for pattern in forbidden_patterns:
            assert not re.search(pattern, stripped), f"{name}: executable forbidden pattern remains: {pattern}"
        assert "createReplacement" not in parts.html, f"{name}: createReplacement must be deleted everywhere"
        assert "__audioCtxCreatedAt" not in parts.html, f"{name}: __audioCtxCreatedAt must be deleted everywhere"


def test_row_5_template_parity() -> None:
    mvj = PARTS["mvj"]
    chinese = PARTS["chinese"]
    assert mvj.lifecycle == chinese.lifecycle, "lifecycle block is not byte-identical"
    assert mvj.play_mobile == chinese.play_mobile, "__playMobile block is not byte-identical"


def test_row_6_script_blocks_node_check() -> None:
    for name, parts in PARTS.items():
        assert parts.scripts, f"{name}: no script blocks found"
        for index, script in enumerate(parts.scripts, start=1):
            _run_node_check(script, f"{name} script {index}")


def main() -> int:
    tests = [
        ("row 1 exact_path lifecycle single construction and recovery degrade", test_row_1_lifecycle_runtime),
        ("row 1b exact_path whole-template construction scan", test_row_1b_static_single_construction),
        ("row 2 exact_path/partial_path __playMobile fallback branches", test_row_2_play_mobile_branches),
        ("row 3 exact_path autoplay queue and stall fallback", test_row_3_autoplay_queue_and_stall_degrade),
        ("row 3b exact_path card-scope guards", test_row_3b_card_scope_guards),
        ("row 4 exact_path whole-template teardown scan", test_row_4_static_no_teardown_or_deleted_paths),
        ("row 5 exact_path template block parity", test_row_5_template_parity),
        ("row 6 syntax_only node --check all script blocks", test_row_6_script_blocks_node_check),
    ]
    failed = 0
    for label, fn in tests:
        try:
            fn()
            print(f"PASS  {label}")
        except AssertionError as exc:
            failed += 1
            print(f"FAIL  {label}: {exc}")
        except Exception as exc:  # noqa: BLE001
            failed += 1
            print(f"ERROR {label}: {type(exc).__name__}: {exc}")
    print()
    print(f"{len(tests) - failed}/{len(tests)} passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
