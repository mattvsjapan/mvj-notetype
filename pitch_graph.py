import math
from enum import Enum
from math import sqrt
from typing import Optional, Iterable

try:
    from .katakana_conversion import literal_pronunciation
    from .config import config
    from .kana_conv import to_hiragana, to_katakana
    from .split import *
    from .split import split_accent
except ImportError:
    from config import config
    from kana_conv import to_hiragana, to_katakana
    from split import *
    from split import split_accent
    from katakana_conversion import literal_pronunciation


class Role(Enum):
    heiban = 'h'
    atamadaka = 'a'
    nakadaka = 'n'
    odaka = 'o'
    kifuku = 'k'

    black = 'b'
    white = 'w'
    setsubigo = 's'
    empty = 'e'
    particle = 'p'

    keihan_heiban = 'H'
    keihan_atamadaka = 'A'
    keihan_nakadaka = 'N'
    keihan_low_heiban = 'L'
    keihan_low_nakadaka = 'M'
    keihan_low_odaka = 'O'
    keihan_kifuku = 'K'


class Level(Enum):
    high = 'h'
    low = 'l'


class Line:
    def __init__(self):
        self.x1 = self.y1 = self.x2 = self.y2 = None
        self._tape = False

    def start(self, x1: int, y1: int, tape: bool = False):
        self.x1 = x1
        self.y1 = y1
        self._tape = tape
        return self

    def end(self, x2: int, y2: int):
        self.x2 = x2
        self.y2 = y2
        return self

    @property
    def is_unfinished(self) -> bool:
        return self.x1 is not None and self.y1 is not None

    @property
    def is_completed(self) -> bool:
        return self.x2 is not None and self.y2 is not None

    def draw(self) -> str:
        rendered = f'''
        <line
            stroke="black"
            stroke-width="{config['stroke_width']}"
            x1="{self.x1:.3f}" y1="{self.y1:.3f}"
            x2="{self.x2:.3f}" y2="{self.y2:.3f}"
        />
        '''
        if self._tape:
            rendered = rendered.replace('<line', f'<line stroke-dasharray="{config["stroke_dasharray"]}"')
        rendered = rendered.replace('\n', ' ')
        rendered = re.sub(r'[\n ]+', ' ', rendered, flags=RE_FLAGS)
        return rendered.strip()

    def adjust_to_radius(self, r: int):
        tan = config['graph_height'] / config['x_step']
        sin = tan / sqrt(1 + tan * tan)
        cos = 1 / sqrt(1 + tan * tan)

        offset_y = r * sin
        offset_x = r * cos

        if self.y1 == self.y2:
            self.x1 += r
            self.x2 -= r
        elif self.y1 > self.y2:
            self.x1 += offset_x
            self.y1 -= offset_y
            self.x2 -= offset_x
            self.y2 += offset_y
        elif self.y1 < self.y2:
            self.x1 += offset_x
            self.y1 += offset_y
            self.x2 -= offset_x
            self.y2 -= offset_y
        return self


class Path:
    def __init__(self):
        self.lines: List[Line] = []

    @property
    def last(self) -> Line:
        return self.lines[-1]

    def start_at(self, x: int, y: int) -> None:
        return self.lines.append(Line().start(x, y))

    def go_to(self, x: int, y: int) -> Line:
        return self.last.end(x, y)

    def push(self, x: int, y: int) -> None:
        if len(self.lines) == 0:
            self.start_at(x, y)
        elif self.last.is_completed:
            self.start_at(self.last.x2, self.last.y2)
            self.go_to(x, y)
        else:
            self.go_to(x, y)

    def draw(self) -> str:
        drawn = []
        for line in filter(lambda _line: _line.is_completed, self.lines):
            line.adjust_to_radius(config['circle_radius'])
            drawn.append(line.draw())
        return ''.join(drawn)


def is_empty_particle(word: str):
    return re.match(r'^[|,、]$', word, flags=RE_FLAGS)


def determine_role_keihan(raw_role) -> Role:
    # Upper case letters are used for keihan.
    role = str(raw_role or Role.keihan_heiban.value)
    try:
        return Role(role.upper())
    except ValueError:
        return Role(role.lower())


def determine_levels_keihan(levels, moraes) -> List[Level]:
    levels = list(str(levels).lower())
    levels += [levels[-1], ] * (len(moraes) - len(levels))
    return [Level(c) for c in levels]


def guess_role_from_pitch_num(moraes: List[str], pitch_n) -> Role:
    if not pitch_n:
        return Role.heiban
    pitch_n = int(pitch_n)
    if pitch_n == 0:
        return Role.heiban
    if pitch_n < 0:
        return Role.particle
    if pitch_n == 1:
        return Role.atamadaka
    if pitch_n == len(moraes):
        return Role.odaka
    if pitch_n < len(moraes):
        return Role.nakadaka
    return Role.heiban


def determine_role_tokyo(section_dict: dict) -> Role:
    # if nothing at all => particle.
    # if `;` but no letter or number, then it defaults to heiban
    if len(section_dict['moraes']) == 0 or is_empty_particle(section_dict['word']):
        return Role.empty
    if section_dict['sep'] is None:
        return Role.particle
    if section_dict['accent']['role'] is None:
        return guess_role_from_pitch_num(section_dict['moraes'], section_dict['accent']['pitch'])

    return Role(str(section_dict['accent']['role']).lower())


def determine_pitch_tokyo(section_dict: dict) -> Optional[int]:
    if section_dict['sep'] and (pitch := section_dict['accent']['pitch']):
        return int(pitch)

    role = section_dict['accent']['role']

    if role == Role.heiban or role == Role.setsubigo:
        return 0
    if role == Role.atamadaka:
        return 1
    if role == Role.nakadaka or role == Role.kifuku:
        return 2
    if role == Role.odaka:
        return len(section_dict['moraes'])
    if role == Role.particle:
        return None
    if role == Role.empty:
        return -1

    return 0


def adjust_kana(text: str):
    if config['convert_reading'] == 'katakana':
        return literal_pronunciation(text)
    if config['convert_reading'] == 'hiragana':
        return to_hiragana(text)
    return text


def prepare_moras(word: str) -> List[str]:
    reading = furigana_to_reading(word)
    reading = adjust_kana(reading)
    reading = split_to_moras(reading)
    return reading


class Section:
    def __init__(self, raw_section: str):
        self._raw = raw_section
        self._dict = split_section(raw_section)
        self._dict['moraes'] = prepare_moras(self._dict.get('word', ''))
        self._dict['accent'] = split_accent(self._dict.get('accent', ''))
        self._init_accent()

    def _init_accent(self):
        if (accent := self._dict['accent']).get('keihan') is True:
            accent['keihan'] = True
            accent['role'] = determine_role_keihan(accent['role'])
            accent['levels'] = determine_levels_keihan(self.levels, self.moraes)
        else:
            accent['keihan'] = False
            accent['role'] = determine_role_tokyo(self._dict)
            accent['pitch'] = determine_pitch_tokyo(self._dict)

    def __repr__(self):
        return str(self._dict)

    @property
    def is_tape(self):
        """
        when two words are linked with a solid line (like everything is right now), that means they're welded.
        But, if there's a dotted line, that means they're taped.
        """
        return self._raw == ';'

    @property
    def is_particle(self) -> bool:
        """
        'p' marks a particle.

        For example, まで is an atamadaka particle, so rather than just representing it as gray dots with no fill,
        I would like to represent it as red dots with no fill.
        """
        return bool(self._dict['accent'].get('is_particle'))

    @property
    def raw(self) -> str:
        return self._raw

    @property
    def word(self) -> str:
        return self._dict['word'].replace(DEVOICED_PREFIX, '')

    @property
    def moraes(self) -> List[str]:
        moras = self._dict['moraes']
        if self.is_particle and moras == ['ハ', ]:
            return ['ワ', ]
        return moras

    @property
    def role(self) -> Role:
        return self._dict['accent']['role']

    @property
    def classname(self) -> str:
        return (
            ' '.join({Role.particle.name: None, self.role.name: None, }.keys())
            if self.is_particle
            else self.role.name
        )

    @property
    def pitch(self) -> int:
        return self._dict['accent']['pitch']

    @property
    def levels(self):
        return self._dict['accent']['levels']

    @levels.setter
    def levels(self, value: List[Level]):
        self._dict['accent']['levels'] = value

    @property
    def is_keihan(self) -> bool:
        return self._dict['accent']['keihan']

    @pitch.setter
    def pitch(self, value: int):
        """
        -1 == always low.
        -2 == always high.
        0 == heiban.
        >=1 == nakadaka/odaka.
        """
        self._dict['accent']['pitch'] = value


def build_levels_tokyo(section: Section, last_word_ended_low: bool) -> List[Level]:
    if section.pitch is None:
        section.pitch = -1 if last_word_ended_low else -2

    if section.pitch == -1:
        return [Level.low] * len(section.moraes)
    if section.pitch == -2:
        return [Level.high] * len(section.moraes)
    if section.pitch == 1:
        return [Level.high, ] + [Level.low for _ in section.moraes[1:]]

    result = []
    for index, morae in enumerate(section.moraes):
        if index == 0:
            result.append(Level.low if last_word_ended_low else Level.high)
        else:
            result.append(Level.high if index < section.pitch or section.pitch == 0 else Level.low)

    return result


def calc_last_word_ended_low(section: Section, last_word_ended_low: bool) -> bool:
    if section.role == Role.empty and section.word not in PITCH_BREAKS:
        return last_word_ended_low

    if section.pitch == 1:
        return True

    if section.pitch == 0 or section.pitch == -2:
        return False

    return len(section.moraes) >= section.pitch


def build_high_low(sequence: List[Section]) -> List[Section]:
    last_word_ended_low = True

    for section in sequence:
        if section.is_keihan:
            last_word_ended_low = section.levels[-1] == Level.low
        else:
            section.levels = build_levels_tokyo(section, last_word_ended_low)
            last_word_ended_low = calc_last_word_ended_low(section, last_word_ended_low)

    return sequence


def parse_sections(sequence: List[str]) -> List[Section]:
    return [Section(word) for word in sequence]


def filter_empty_moraes(sequence: List[Section]) -> List[Section]:
    return [
        section for section in sequence
        if (
                len(section.moraes)
                or section.word in PITCH_BREAKS
                or section.is_tape  # allow tape in, but filter it out later.
        )
    ]


def should_connect(section: Section, prev_section: Section) -> bool:
    # by default all dots should be connected by lines.
    # everything is connected unless you specifically add , or |.
    if prev_section.is_tape:
        # if section is a tape, it is not printed on the svg
        # but connects two moras around itself with a dotted line.
        # Tape is skipped, so you only need to test prev_section.
        return True
    if section.role == Role.empty or prev_section.role == Role.empty:
        return False
    return True


def make_circle(x_pos: int, y_pos: int) -> str:
    return f'<circle fill="black" stroke="black" stroke-width="{config["stroke_width"]}" cx="{x_pos}" cy="{y_pos}" r="{config["circle_radius"]}"></circle>'


def make_devoiced_circle(mora: str, x_pos: int, y_pos: int):
    if len(mora) == 1:
        x_pos = x_pos + config['font_size'] / 2 + config['text_dx']
        y_pos = y_pos + config['text_dx'] + math.ceil(config['stroke_width'])
        return f'<circle class="devoiced" fill="none" stroke="black" cx="{x_pos}" cy="{y_pos}" stroke-width="{config["devoiced_circle_width"]}" r="{config["devoiced_circle_radius"]}" stroke-dasharray="{config["devoiced_stroke_disarray"]}" />'
    else:
        f_s = config['font_size']
        r = config["devoiced_circle_radius"]
        y_pos = y_pos - config['font_size'] - math.floor(config['stroke_width'])
        pad = config['devoiced_rectangle_padding']
        return f'<rect fill="none" stroke="black" x="{x_pos - f_s - pad}" y="{y_pos}" width="{f_s * 2 + pad * 2}" height="{r * 2}" rx="{r}" stroke-width="{config["devoiced_circle_width"]}" stroke-dasharray="{config["devoiced_stroke_disarray"]}" />'


def make_group(elements: Iterable, classname: str) -> str:
    return f'<g class="{classname}">{"".join(elements)}</g>'


def make_svg(contents: str, width: int, height: int, visible_height: int) -> str:
    return f'<svg style="font-family: {config["graph_font"]}" viewBox="0 0 {width} {height}" height="{visible_height}px" xmlns="http://www.w3.org/2000/svg">{contents}</svg>'


def make_text(text: str, x: int, y: int, dx: int) -> str:
    class_name = ' class="devoiced"' if isinstance(text, DevoicedMora) else ''
    return f'<text{class_name} font-size="{config["font_size"]}px" fill="black" x="{x}" y="{y}" dx="{dx}">{text}</text>'


def calc_svg_width(sequence: List[Section], morae_width: int) -> int:
    return (
            sum(len(section.moraes) if section.role != Role.empty else 0 for section in sequence) * morae_width
            + config['graph_horizontal_padding'] * 2
    )


def make_graph(sequence: List[Section]) -> Optional[str]:
    sequence = filter_empty_moraes(sequence)
    if not sequence:
        return None

    x_pos = y_pos = height_high = config['size_unit']
    x_pos += config['graph_horizontal_padding']
    x_step = config['x_step']
    height_low = height_high + config['graph_height']
    height_kana = height_low + x_step

    circles, paths, text = [], [], []

    for i, section in enumerate(sequence):
        # each section is a word, a list of moras
        if section.role == Role.empty or section.is_tape:
            continue

        word_circles, text_moraes = [], []
        path = Path()
        connector = Line()  # single connector per section

        if 0 < i < len(sequence) and should_connect(section, sequence[i - 1]):
            connector.start(x_pos - x_step, y_pos, tape=sequence[i - 1].is_tape)

        for j, mora in enumerate(section.moraes):
            mora_level = (
                section.levels[j - 1]
                if mora in ('っ', 'ッ') and j == 1 and section.levels[j - 1] == Level.low
                else section.levels[j]
            )
            y_pos = height_high if mora_level == Level.high else height_low
            word_circles.append(make_circle(x_pos, y_pos))
            path.push(x_pos, y_pos)

            if j == 0 and connector.is_unfinished:
                # first mora of a word
                connector.end(x_pos, y_pos)

            if mora != GHOST_PARTICLE:
                if isinstance(mora, DevoicedMora):
                    # added some magic numbers here because it's unclear how the position is calculated.
                    # possibly, it's font-dependent which would suck.
                    text_moraes.append(make_devoiced_circle(
                        mora,
                        x_pos,
                        height_kana
                    ))
                text_moraes.append(make_text(
                    mora,
                    x_pos,
                    height_kana,
                    int(config['text_dx']) * len(mora)
                ))

            x_pos += x_step

        circles.append(make_group(word_circles, section.classname))
        paths.append(make_group([path.draw()], section.classname))
        text.append(make_group(text_moraes, section.classname))

        if connector.is_completed > 0:
            paths.append(make_group([connector.adjust_to_radius(config['circle_radius']).draw()], 'connector'))

    content = [
        make_group(paths, 'paths'),
        make_group(circles, 'circles'),
    ]
    svg_width = calc_svg_width(sequence, x_step)

    svg_height_with_text = height_kana + config['size_unit']
    svg_height_no_text = height_low + config['size_unit']

    if config['no_text']:
        svg_height = svg_height_no_text
        ratio = svg_height_no_text / svg_height_with_text
        visible_height = int(ratio * config['graph_visible_height'])
    else:
        svg_height = svg_height_with_text
        visible_height = config['graph_visible_height']
        content.append(make_group(text, 'text'))

    svg = make_svg(''.join(content), svg_width, svg_height, visible_height)
    notation = f'<!-- generated using syntax: "{" ".join(s.raw for s in sequence)}" -->'

    return f'{notation}\n{svg}'


def apply_kanji_colors(seq_sequences: List[List[Section]]) -> List[str]:
    def do(sentence: List[Section]):
        result = []
        for section in sentence:
            if section.word in SENT_HIDDEN or section.is_tape:
                continue
            result.append(f'<span class="{section.role.name}">{section.word}</span>')

        return ''.join(result)

    return [do(s) for s in seq_sequences]


def make_sequences(expr: str) -> List[List[Section]]:
    expr = normalize_for_parsing(expr)
    sentences = split_to_sentences(expr)

    sentences = [detach_ghost_particle(sentence) for sentence in sentences]

    sentences_by_sections = list(map(split_to_sections, sentences))
    sentences_by_sections = split_multiple_pitch_notations(sentences_by_sections)

    sequences = [parse_sections(section) for section in sentences_by_sections]
    sequences = [build_high_low(sequence) for sequence in sequences]
    return sequences


def make_graphs(sequences: List[List[Section]]) -> Iterable[str]:
    return [graph for sequence in sequences if (graph := make_graph(sequence))]
