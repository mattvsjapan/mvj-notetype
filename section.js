const RoleFromValue = {
  'h':'heiban','a':'atamadaka','n':'nakadaka','o':'odaka','k':'kifuku',
  'b':'black','w':'white','s':'setsubigo','e':'empty','p':'particle',
  'H':'keihan_heiban','A':'keihan_atamadaka','N':'keihan_nakadaka',
  'L':'keihan_low_heiban','M':'keihan_low_nakadaka','O':'keihan_low_odaka',
  'K':'keihan_kifuku',
};

function isEmptyParticle(word) { return /^[|,、]$/.test(word); }

function determineRoleKeihan(rawRole) {
  const val = String(rawRole || 'H');
  return RoleFromValue[val.toUpperCase()] || RoleFromValue[val.toLowerCase()] || 'keihan_heiban';
}

function determineLevelsKeihan(levels, moraes) {
  const arr = [...String(levels).toLowerCase()];
  while (arr.length < moraes.length) arr.push(arr[arr.length - 1]);
  return arr;
}

function guessRoleFromPitchNum(moraes, pitchN) {
  if (pitchN == null) return 'heiban';
  const n = parseInt(pitchN);
  if (n === 0) return 'heiban';
  if (n < 0) return 'particle';
  if (n === 1) return 'atamadaka';
  if (n === moraes.length) return 'odaka';
  if (n < moraes.length) return 'nakadaka';
  return 'heiban';
}

function determineRoleTokyo(sd) {
  if (sd.moraes.length === 0 || isEmptyParticle(sd.word)) return 'empty';
  if (sd.sep == null) return 'particle';
  if (sd.accent.role == null && sd.accent.pitch == null) return 'particle';
  if (sd.accent.role == null) return guessRoleFromPitchNum(sd.moraes, sd.accent.pitch);
  return RoleFromValue[sd.accent.role.toLowerCase()] || 'heiban';
}

function determinePitchTokyo(sd) {
  if (sd.sep && sd.accent.pitch != null) return parseInt(sd.accent.pitch);
  const role = sd.accent.role;
  if (role === 'heiban' || role === 'setsubigo') return 0;
  if (role === 'atamadaka') return 1;
  if (role === 'nakadaka' || role === 'kifuku') return 2;
  if (role === 'odaka') return sd.moraes.length;
  if (role === 'particle') return null;
  if (role === 'empty') return -1;
  return 0;
}

function adjustKana(text) {
  if (config.convert_reading === 'katakana') return literalPronunciation(text);
  if (config.convert_reading === 'hiragana') return toHiragana(text);
  return text;
}

function prepareMoras(word) {
  let reading = furiganaToReading(word);
  reading = adjustKana(reading);
  return splitToMoras(reading);
}

class Section {
  constructor(rawSection) {
    this.raw = rawSection;
    this._d = splitSection(rawSection);
    this._d.moraes = prepareMoras(this._d.word || '');
    this._d.accent = splitAccent(this._d.accent || '');
    this._initAccent();
  }

  _initAccent() {
    const a = this._d.accent;
    if (a.keihan) {
      a.role = determineRoleKeihan(a.role);
      a.levels = determineLevelsKeihan(a.levels, this._d.moraes);
    } else {
      a.keihan = false;
      a.role = determineRoleTokyo(this._d);
      a.pitch = determinePitchTokyo(this._d);
    }
  }

  get isTape() { return this.raw === ';'; }

  get isParticle() { return !!this._d.accent.is_particle; }

  get word() { return this._d.word.replaceAll(DEVOICED_PREFIX, ''); }

  get moraes() {
    const m = this._d.moraes;
    if ((this.role === 'particle' || this.isParticle) && m.length === 1) {
      if (m[0].text === 'ハ') return [{ text: 'ワ', devoiced: m[0].devoiced }];
      if (m[0].text === 'ヘ') return [{ text: 'エ', devoiced: m[0].devoiced }];
    }
    return m;
  }

  get role() { return this._d.accent.role; }

  get classname() {
    if (this.isParticle) {
      return [...new Set(['particle', this.role])].join(' ');
    }
    return this.role;
  }

  get pitch() { return this._d.accent.pitch; }
  set pitch(v) { this._d.accent.pitch = v; }

  get levels() { return this._d.accent.levels; }
  set levels(v) { this._d.accent.levels = v; }

  get isKeihan() { return !!this._d.accent.keihan; }
}

const H = 'h', L = 'l';

function buildLevelsTokyo(section, lastLow) {
  if (section.pitch == null) section.pitch = lastLow ? -1 : -2;
  if (section.pitch === -1) return section.moraes.map(() => L);
  if (section.pitch === -2) return section.moraes.map(() => H);
  if (section.pitch === 1) return [H, ...section.moraes.slice(1).map(() => L)];

  return section.moraes.map((_, i) => {
    if (i === 0) return lastLow ? L : H;
    return (i < section.pitch || section.pitch === 0) ? H : L;
  });
}

function calcLastWordEndedLow(section, lastLow) {
  if (section.role === 'empty' && !PITCH_BREAKS.includes(section.word)) return lastLow;
  if (section.pitch === 1) return true;
  if (section.pitch === 0 || section.pitch === -2) return false;
  return section.moraes.length >= section.pitch;
}

function buildHighLow(sequence) {
  let lastLow = true;
  for (const section of sequence) {
    if (section.isKeihan) {
      lastLow = section.levels[section.levels.length - 1] === L;
    } else {
      section.levels = buildLevelsTokyo(section, lastLow);
      lastLow = calcLastWordEndedLow(section, lastLow);
    }
  }
  return sequence;
}

function parseSections(seq) { return seq.map(s => new Section(s)); }

function filterEmptyMoraes(sequence) {
  return sequence.filter(s =>
    s.moraes.length || PITCH_BREAKS.includes(s.word) || s.isTape
  );
}
