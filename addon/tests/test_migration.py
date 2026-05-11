"""Regression tests for the comment-syntax → Word-field migration.

Each case below was discovered by inspecting the migration log and pinned
here once the underlying bug was fixed. Run directly:

    python3 addon/tests/test_migration.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pitch_migration import convert_comment_syntax, splice_word_kanji  # noqa: E402


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
        'no splice for multi-group output',
        '豊田[とよた]:1 / 船長[せんちょう]:1',
        '<span class="atamadaka">豊田[とよた]</span><span class="atamadaka">船長[せんちょう]</span>',
        '豊田[とよた]:1 / 船長[せんちょう]:1',
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
    total = len(CONVERT_CASES) + len(SPLICE_CASES)
    print()
    print(f'{total - failed}/{total} passed')
    return 1 if failed else 0


if __name__ == '__main__':
    sys.exit(main())
