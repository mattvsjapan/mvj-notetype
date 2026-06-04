"""Tests for the MvJ Japanese add-on field-mapping integration.

Covers ``_mvj_field_assignments`` -- the pure decision logic that decides what
to write onto MvJ Japanese's japanese_fields block, and crucially leaves an
existing note type selection untouched. ``aqt`` is stubbed so ``notetype``
imports without Anki. Run directly:

    python3 addon/tests/test_mvj_japanese_config.py
"""

import os
import sys
import types

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Stub the aqt imports that notetype.py performs at module load.
_aqt = types.ModuleType("aqt")
_aqt.mw = None
_aqt_utils = types.ModuleType("aqt.utils")
_aqt_utils.showWarning = lambda *a, **k: None
sys.modules.setdefault("aqt", _aqt)
sys.modules.setdefault("aqt.utils", _aqt_utils)

from notetype import _MVJ_JP_FIELD_MAP, _mvj_field_assignments  # noqa: E402

MODEL_ID = 1779545580076
PROFILE = "User 1"

EXPECTED_MAP = {
    "word": "Word",
    "fallback_word": "am-study-morphs",
    "sentence": "Sentence",
    "sentence_audio": "Sentence Audio",
    "word_audio": "Word Audio",
    "definition": "Definition",
    "definition_audio": "Definition Audio",
    "translation": "Notes",
    "image": "Image",
}


def _check(label, cond):
    print(("PASS" if cond else "FAIL"), "-", label)
    return cond


def test_assigns_everything_when_unselected():
    out = _mvj_field_assignments(None, MODEL_ID, PROFILE)
    ok = out is not None
    ok &= out.get("selected_notetype_id") == MODEL_ID
    ok &= out.get("selected_notetype_profile") == PROFILE
    for key, name in EXPECTED_MAP.items():
        ok &= out.get(key) == name
    return _check("assigns id, profile, and every field when nothing selected", ok)


def test_skips_when_different_notetype_selected():
    out = _mvj_field_assignments(999, MODEL_ID, PROFILE)
    return _check("different note type selected -> None (untouched)", out is None)


def test_skips_when_our_notetype_already_selected():
    # Already our note type (any mapping, custom or not) -> leave alone.
    out = _mvj_field_assignments(MODEL_ID, MODEL_ID, PROFILE)
    return _check("already selected -> None (untouched)", out is None)


def test_skips_when_id_is_zero():
    # Defensive: an id of 0 is still a real selection, not "unset".
    out = _mvj_field_assignments(0, MODEL_ID, PROFILE)
    return _check("id 0 is a selection -> None", out is None)


def test_no_monolingual_definition_key():
    out = _mvj_field_assignments(None, MODEL_ID, PROFILE)
    ok = "monolingual_definition" not in out
    # The field map itself must not introduce it either.
    ok &= "monolingual_definition" not in _MVJ_JP_FIELD_MAP
    # Exactly the 9 mapped fields plus id + profile.
    ok &= len(out) == len(EXPECTED_MAP) + 2
    return _check("monolingual_definition left untouched; no extra keys", ok)


def main():
    results = [
        test_assigns_everything_when_unselected(),
        test_skips_when_different_notetype_selected(),
        test_skips_when_our_notetype_already_selected(),
        test_skips_when_id_is_zero(),
        test_no_monolingual_definition_key(),
    ]
    if not all(results):
        sys.exit(1)
    print(f"\nAll {len(results)} tests passed.")


if __name__ == "__main__":
    main()
