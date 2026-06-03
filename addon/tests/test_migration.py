"""Regression tests for the comment-syntax → Word-field migration.

Each case below was discovered by inspecting the migration log and pinned
here once the underlying bug was fixed. Run directly:

    python3 addon/tests/test_migration.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pitch_migration import (  # noqa: E402
    convert_comment_syntax,
    mark_front_visible,
    splice_word_kanji,
)


# (label, image-comment input, expected converter output)
CONVERT_CASES = [
    (
        'odaka with d-prefix devoicing',
        '岸[dきし];o -',
        '岸[*きし]:o-',
    ),
    (
        'bare-kana empty pitch (heiban)',
        'おあいこ; -',
        'おあいこ:0-',
    ),
    (
        'inline d devoicing with empty pitch',
        '学者[がdくしゃ]; -',
        '学者[が*くしゃ]:0-',
    ),
    (
        'bare-kana token with inline devoicing',
        'いdきき;2 -',
        'い*きき:2-',
    ),
    (
        'k-1 legacy linker → k~ in 4-group compound',
        '手[て];1 取[と]り;k-1 ; 足[あdし];o ; 取[と]り;k1',
        '手[て]:1 取[と]り:k~ / 足[あ*し]:o / 取[と]り:k1',
    ),
    (
        'k-1 linker on both halves of a 2-group compound',
        '手[て];1 取[と]り;k-1 ; 足[あdし];o 取[と]り;k-1',
        '手[て]:1 取[と]り:k~ / 足[あ*し]:o 取[と]り:k~',
    ),
    (
        'no ghost dash on accented noun followed by a real particle',
        '今[いま]まで;n0 以上[いじょう];1 に',
        '今[いま]まで:n0 以上[いじょう]:1 に',
    ),
    (
        'group-separator ghost particle as its own group',
        '透[dす]かさず; ; -',
        '透[*す]かさず:0 / -',
    ),
]

# (label, converter output, Word-field-before, expected spliced output)
SPLICE_CASES = [
    (
        'splice in kanji from Word field when comment was kana-only',
        'あたりはずれ:0-',
        '<span class="heiban">当[あ]たり 外[はず]れ</span>',
        '当[あ]たり 外[はず]れ:0-',
    ),
    (
        'no splice when Word field is also kana-only',
        'ピーナッツバター:6-',
        '<span class="nakadaka">ピーナッツバター</span>',
        'ピーナッツバター:6-',
    ),
    (
        'no splice when converter already produced kanji',
        '岸[*きし]:o-',
        '<span class="odaka">岸[きし]</span>',
        '岸[*きし]:o-',
    ),
    (
        'multi-group: no splice when converter already produced kanji',
        '豊田[とよた]:1 / 船長[せんちょう]:1',
        '<span class="atamadaka">豊田[とよた]</span><span class="atamadaka">船長[せんちょう]</span>',
        '豊田[とよた]:1 / 船長[せんちょう]:1',
    ),
    (
        'multi-group: splice kanji into each group from per-span surfaces',
        'おやすい:0 / ごよう:2',
        '<span class="heiban">御[お]安[やす]い</span><span class="nakadaka">御[ご]用[よう]</span>',
        '御[お]安[やす]い:0 / 御[ご]用[よう]:2',
    ),
    (
        'multi-group: ghost-particle group has no span and passes through',
        'すかさず:0 / -',
        '<span class="heiban">透[す]かさず</span>',
        '透[す]かさず:0 / -',
    ),
    (
        'multi-group: re-inject * marker per group during splice',
        'まっ*ぷたつ:3 / ごよう:2',
        '<span class="nakadaka">真[ま]っ 二[ぷた]つ</span><span class="nakadaka">御[ご]用[よう]</span>',
        '真[ま]っ 二[*ぷた]つ:3 / 御[ご]用[よう]:2',
    ),
    (
        'multi-group: span count != real-group count → keep kana (no half-splice)',
        'おやすい:0 / ごよう:2',
        '<span class="heiban">御[お]安[やす]い</span>',
        'おやすい:0 / ごよう:2',
    ),
    (
        'multi-group: one group mismatches → whole field stays kana',
        'おやすい:0 / ちがう:2',
        '<span class="heiban">御[お]安[やす]い</span><span class="nakadaka">御[ご]用[よう]</span>',
        'おやすい:0 / ちがう:2',
    ),
    (
        'multi-group: no spans + no kanji → unchanged, no warning',
        'おやすい:0 / ごよう:2',
        'おやすい ごよう',
        'おやすい:0 / ごよう:2',
    ),
    (
        'splice re-injects * marker into the matching bracket',
        'まっ*ぷたつ:3-',
        '<span class="nakadaka">真[ま]っ 二[ぷた]つ</span>',
        '真[ま]っ 二[*ぷた]つ:3-',
    ),
    (
        'splice re-injects * marker on bare kana outside brackets',
        'い*きたい:2-',
        '<span class="atamadaka">行[い]きたい</span>',
        '行[い]*きたい:2-',
    ),
]

# (label, converted, Word-field-before, expected warning token)
SPLICE_WARNING_CASES = [
    (
        'span/group count mismatch warns when kanji present',
        'おやすい:0 / ごよう:2',
        '<span class="heiban">御[お]安[やす]い</span>',
        'multigroup_span_mismatch',
    ),
    (
        'per-group kana mismatch is reported with the group index',
        'おやすい:0 / ちがう:2',
        '<span class="heiban">御[お]安[やす]い</span><span class="nakadaka">御[ご]用[よう]</span>',
        'word_kana_mismatch[group1]',
    ),
    (
        'no spans + no kanji → no warning (nothing was lost)',
        'おやすい:0 / ごよう:2',
        'おやすい ごよう',
        None,
    ),
]


# (label, converter output, Word-field-before, expected output)
FRONT_VISIBLE_CASES = [
    (
        'inject ! into kanji-furigana when front_visible class present',
        '後々[あとあと]:0-',
        '<span class="front_visible"><span class="heiban">後々[あとあと]</span></span>',
        '後々[!あとあと]:0-',
    ),
    (
        'multi-word: ! injected into every furigana bracket',
        '当[あ]たり 外[はず]れ:0-',
        '<span class="front_visible"><span class="heiban">当[あ]たり 外[はず]れ</span></span>',
        '当[!あ]たり 外[!はず]れ:0-',
    ),
    (
        'no front_visible class → no change',
        '後々[あとあと]:0-',
        '<span class="heiban">後々[あとあと]</span>',
        '後々[あとあと]:0-',
    ),
    (
        'idempotent: existing ! not doubled',
        '後々[!あとあと]:0-',
        '<span class="front_visible"><span class="heiban">後々[あとあと]</span></span>',
        '後々[!あとあと]:0-',
    ),
    (
        'front_visible with devoiced marker keeps * inside the !',
        '岸[*きし]:o-',
        '<span class="front_visible"><span class="odaka">岸[きし]</span></span>',
        '岸[!*きし]:o-',
    ),
]


def _check(label, actual, expected):
    if actual == expected:
        print(f'PASS  {label}')
        print(f'      -> {actual!r}')
        return 0
    print(f'FAIL  {label}')
    print(f'      actual:   {actual!r}')
    print(f'      expected: {expected!r}')
    return 1


def main() -> int:
    failed = 0
    for label, src, expected in CONVERT_CASES:
        actual, _ = convert_comment_syntax(src)
        failed += _check(label, actual, expected)
    for label, converted, word_field, expected in SPLICE_CASES:
        actual, _ = splice_word_kanji(converted, word_field)
        failed += _check(label, actual, expected)
    for label, converted, word_field, expected_token in SPLICE_WARNING_CASES:
        _, warnings = splice_word_kanji(converted, word_field)
        if expected_token is None:
            failed += _check(label, warnings, [])
        else:
            actual = expected_token if expected_token in warnings else warnings
            failed += _check(label, actual, expected_token)
    for label, converted, word_field, expected in FRONT_VISIBLE_CASES:
        actual = mark_front_visible(converted, word_field)
        failed += _check(label, actual, expected)
    total = (
        len(CONVERT_CASES) + len(SPLICE_CASES)
        + len(SPLICE_WARNING_CASES) + len(FRONT_VISIBLE_CASES)
    )
    print()
    print(f'{total - failed}/{total} passed')
    return 1 if failed else 0


if __name__ == '__main__':
    sys.exit(main())
