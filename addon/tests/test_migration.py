"""Regression tests for the comment-syntax → Word-field migration.

Each case below was discovered by inspecting the migration log and pinned
here once the underlying bug was fixed. Run directly:

    python3 addon/tests/test_migration.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pitch_migration import convert_comment_syntax  # noqa: E402


# (label, image-comment input, expected new Word-field output)
CASES = [
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
]


def main() -> int:
    failed = 0
    for label, src, expected in CASES:
        actual, _ = convert_comment_syntax(src)
        if actual == expected:
            print(f'PASS  {label}')
            print(f'      {src!r} -> {actual!r}')
        else:
            print(f'FAIL  {label}')
            print(f'      input:    {src!r}')
            print(f'      actual:   {actual!r}')
            print(f'      expected: {expected!r}')
            failed += 1
    print()
    print(f'{len(CASES) - failed}/{len(CASES)} passed')
    return 1 if failed else 0


if __name__ == '__main__':
    sys.exit(main())
