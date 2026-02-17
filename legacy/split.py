import re
from typing import List, Dict, Any

RE_FLAGS = re.MULTILINE | re.IGNORECASE
GHOST_PARTICLE = '-'  # A special symbol reserved for drawing empty trailing circles.
DEVOICED_PREFIX = 'd'
SENT_HIDDEN = ['|', GHOST_PARTICLE]
PITCH_BREAKS = SENT_HIDDEN + [',', '、']


def split_multiple_pitch_notations(sequences: List[List[str]]) -> List[List[str]]:
    result = []
    for sequence in sequences:
        first_section = split_section(sequence[0])
        if first_section['sep']:
            for accent in first_section['accent'].split(','):
                result.append([f"{first_section['word']};{accent}"] + sequence[1:])
        else:
            result.append(sequence)

    return result


def normalize_for_parsing(expr: str) -> str:
    # Using spaces to separate everything.
    # Taking advantage of the fact that Japanese doesn't use spaces.
    expr = expr.replace('<br>', ' . ')
    try:
        from anki.utils import html_to_text_line

        expr = html_to_text_line(expr)
    except AttributeError:
        expr = re.sub(r'<[^<>]+>', '', expr, flags=RE_FLAGS)
    expr = re.sub(r'([。!?！？])', r' \g<1> .', expr, flags=RE_FLAGS)
    expr = re.sub(r'([「」|、､])', r' \g<1> ', expr, flags=RE_FLAGS)
    expr = re.sub(r'([^ ]), ', r' \g<1> , ', expr, flags=RE_FLAGS)
    return expr


def split_to_sentences(expr: str) -> List[str]:
    return list(filter(bool, map(str.strip, re.split(r'[.\n]+', expr, flags=RE_FLAGS))))


def split_to_sections(sentence: str) -> List[str]:
    return [s for s in re.split(r'[\n\t\s　]+', sentence, flags=RE_FLAGS) if s]


def detach_ghost_particle(text: str) -> str:
    """
    After a ghost particle there has to be the end of the sentence, which is ensured by adding an extra dot.
    """
    return re.sub(fr'{GHOST_PARTICLE}[\s\n.]*$', f' {GHOST_PARTICLE}', text)


def furigana_to_reading(word: str) -> str:
    return re.sub(r'([^\[\]]*\[|])', '', word, flags=RE_FLAGS)


def filter_kana(reading: str) -> str:
    return re.sub(fr'[^ぁ-ゔゞァ-・ヽヾ゛゜ぁ-んァ-ンー{DEVOICED_PREFIX}{GHOST_PARTICLE}]', '', reading, flags=RE_FLAGS)


def kana_to_moraes(kana: str) -> List[str]:
    return re.findall(fr'{DEVOICED_PREFIX}?.[ァィゥェォャュョぁぃぅぇぉゃゅょ]?', kana, flags=RE_FLAGS)


class DevoicedMora(str):
    pass


def split_to_moras(reading: str) -> List[str]:
    kana = filter_kana(reading)
    moraes = kana_to_moraes(kana)
    return [
        mora
        if not mora.startswith(DEVOICED_PREFIX)
        else DevoicedMora(mora[len(DEVOICED_PREFIX):])
        for mora in moraes
    ]


def split_section(raw_section: str) -> Dict[str, Any]:
    m = re.match(r"^(?P<word>[^；;:]+)(?P<sep>[；;:])?(?P<accent>.*)$", raw_section, flags=RE_FLAGS)
    if m:
        return {
            'word': m.group('word'),
            'sep': m.group('sep'),
            'accent': m.group('accent')
        }
    else:
        return {
            'word': raw_section,
            'sep': None,
        }


def split_accent(raw_accent: str) -> Dict[str, Any]:
    # any group can be none
    m = re.match(r'^(?P<is_particle>p)?(?P<role>[a-zA-Z])?(?P<pitch>-?\d)?$', raw_accent, flags=RE_FLAGS)
    if m:
        return {
            'is_particle': m.group('is_particle'),
            'role': m.group('role') or m.group('is_particle'),  # p1 would really mean pp1, etc.
            'pitch': m.group('pitch'),
        }

    m = re.match(r'^(?P<role>[a-zA-Z]{1,2})[；;](?P<levels>[hlHL]+)$', raw_accent, flags=RE_FLAGS)
    if m:
        return {
            'role': m.group('role'),
            'levels': m.group('levels'),
            'keihan': True,
        }

    return {
        'role': None,
        'pitch': None,
    }
