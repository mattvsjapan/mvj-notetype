"""Regression tests for Kaishi deck migration matching.

Run directly:

    python3 addon/tests/test_kaishi_migration.py
"""

import importlib.util
import sys
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ADDON_DIR = ROOT / "addon"


def _load_kaishi_module():
    """Load addon/kaishi.py without importing the Anki add-on bootstrap."""
    pkg = types.ModuleType("addon")
    pkg.__path__ = [str(ADDON_DIR)]
    sys.modules.setdefault("addon", pkg)

    aqt = types.ModuleType("aqt")
    aqt.mw = None
    aqt_qt = types.ModuleType("aqt.qt")
    aqt_qt.QMessageBox = object
    aqt_utils = types.ModuleType("aqt.utils")
    aqt_utils.showInfo = lambda *args, **kwargs: None
    aqt_utils.showWarning = lambda *args, **kwargs: None
    sys.modules.setdefault("aqt", aqt)
    sys.modules.setdefault("aqt.qt", aqt_qt)
    sys.modules.setdefault("aqt.utils", aqt_utils)

    spec = importlib.util.spec_from_file_location("addon.kaishi", ADDON_DIR / "kaishi.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules["addon.kaishi"] = module
    spec.loader.exec_module(module)
    return module


kaishi = _load_kaishi_module()


def _load_rows():
    return kaishi._parse_cards_tsv((ROOT / "kaishi" / "cards.tsv").read_bytes())


def _check(label, ok):
    if ok:
        print(f"PASS  {label}")
        return 0
    print(f"FAIL  {label}")
    return 1


def test_alias_separator_expands_legacy_keys():
    row = {
        "sentence_key_furigana": "",
        "sentence_key_plain": "",
        "sentence_key_legacy": "alpha ||| beta ||| gamma",
        "Word": "sentinel",
    }
    index = kaishi._build_key_index([row])
    return all(index[key]["Word"] == "sentinel" for key in ("alpha", "beta", "gamma"))


def test_current_and_legacy_dekiru_keys_match_same_row():
    rows = _load_rows()
    index = kaishi._build_key_index(rows)
    keys = [
        "あなたはスキーが<b>出 来ます</b>か？",
        "あなたはスキーが<b>出来ます</b>か？",
        "あなたはスキーが<b>出 来ます</b>か。",
    ]
    return all(index[kaishi._normalize_key(key)]["Word"] == "出[で] 来[き]る:k2" for key in keys)


def test_v24_original_sentence_aliases_match():
    rows = _load_rows()
    index = kaishi._build_key_index(rows)
    cases = [
        ("彼 女は 私の<b>大 事</b>な 人です。", "大[だい] 事[じ]:o0-"),
        ("子 供に<b>構いすぎて</b>はいけない。", "構[かま]う:k2"),
        ("テレビのリモコンが<b>壊れてしまいました</b>。", "壊[こわ]れる:k3"),
        ("麻はきれいに<b>染まります</b>。", "染[そ]まる:0"),
        ("彼は 応 募の 条 件を<b>満たしていない</b>。", "満[み]たす:k2"),
    ]
    return all(index[kaishi._normalize_key(key)]["Word"] == word for key, word in cases)


def main() -> int:
    failed = 0
    failed += _check("alias separator expands legacy keys", test_alias_separator_expands_legacy_keys())
    failed += _check("current + old + v2.4 出来る keys match", test_current_and_legacy_dekiru_keys_match_same_row())
    failed += _check("v2.4 original sentence aliases match", test_v24_original_sentence_aliases_match())
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
