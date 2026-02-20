const GHOST_PARTICLE = '-';
const DEVOICED_PREFIX = '*';
const LITERAL_PREFIX = '\\';
const HIGH_PREFIX = '^';
const SENT_HIDDEN = ['|', GHOST_PARTICLE];
const PITCH_BREAKS = [...SENT_HIDDEN, ',', '、'];

function normalizeForParsing(expr) {
  expr = expr.replace(/\//g, ';');
  expr = expr.replace(/<br>/gi, ' . ');
  expr = expr.replace(/<[^<>]+>/gi, '');
  expr = expr.replace(/([。!?！？])/g, ' $1 .');
  expr = expr.replace(/([「」|、､])/g, ' $1 ');
  expr = expr.replace(/([^ ]), /g, ' $1 , ');
  return expr;
}

function splitToSentences(expr) {
  return expr.split(/[.\n]+/).map(s => s.trim()).filter(Boolean);
}

function splitToSections(sentence) {
  return sentence.split(/[\t\s\u3000]+/).filter(Boolean);
}

function detachGhostParticle(text) {
  return text.replace(/(-+)[\s\n.]*$/, ' $1');
}

function furiganaToReading(word) {
  return word.split(' ').map(part => {
    // Move prefix markers (^, *) from before kanji[reading] into the reading
    part = part.replace(/([\*\^]+)([^\[\]\*\^]*)\[/g, '$2[$1');
    return part.replace(/([^\[\]]*\[|])/g, '');
  }).join('');
}

function filterKana(reading) {
  return reading.replace(/[^\u3040-\u309F\u30A0-\u30FF\*\-\\\^]/g, '');
}

function kanaToMoraes(kana) {
  return kana.match(/(?:[\*\\\^]{1,3})?.[ァィゥェォャュョぁぃぅぇぉゃゅょ]?/g) || [];
}

function splitToMoras(reading) {
  const kana = filterKana(reading);
  const raw = kanaToMoraes(kana);
  return raw.map(m => {
    let devoiced = false, literal = false, high = false;
    while (m.length > 0) {
      if (m.startsWith(DEVOICED_PREFIX)) { devoiced = true; m = m.slice(1); }
      else if (m.startsWith(LITERAL_PREFIX)) { literal = true; m = m.slice(1); }
      else if (m.startsWith(HIGH_PREFIX)) { high = true; m = m.slice(1); }
      else break;
    }
    return { text: m, devoiced, literal, high };
  });
}

function splitSection(raw) {
  const m = raw.match(/^([^:]+)(:)?(.*)$/);
  if (m) return { word: m[1], sep: m[2] || null, accent: m[3] || '' };
  return { word: raw, sep: null, accent: '' };
}

function splitAccent(raw) {
  if (!raw && raw !== '') raw = '';
  let m = raw.match(/^(p)?([a-zA-Z])?(~)?(\d)?(~)?$/);
  if (m) {
    return {
      is_particle: m[1] || null,
      role: m[2] || m[1] || null,
      allLow: !!(m[3] || m[5]),
      pitch: m[4] || null,
    };
  }
  m = raw.match(/^([a-zA-Z]{1,2}):([hlHL]+)$/);
  if (m) {
    return { role: m[1], levels: m[2], keihan: true };
  }
  return { role: null, pitch: null };
}

const SEPARATORS = [';', '|', ',', '、', '-', '「', '」'];

function mergeFragments(sections) {
  const result = [];
  let pending = [];
  for (const raw of sections) {
    if (SEPARATORS.includes(raw)) {
      result.push(...pending);
      pending = [];
      result.push(raw);
      continue;
    }
    const { sep } = splitSection(raw);
    if (sep == null) {
      pending.push(raw);
    } else {
      if (pending.length) {
        const merged = [...pending, raw.replace(/:.*$/, '')].join(' ');
        const accent = raw.replace(/^[^:]*:/, '');
        result.push(merged + ':' + accent);
        pending = [];
      } else {
        result.push(raw);
      }
    }
  }
  result.push(...pending);
  return result;
}

function splitMultiplePitchNotations(sequences) {
  const result = [];
  for (const seq of sequences) {
    // For each element, collect its alternatives (or just itself if no commas)
    const alternatives = seq.map(raw => {
      const sec = splitSection(raw);
      if (sec.sep && sec.accent.includes(',')) {
        return sec.accent.split(',').map(a => `${sec.word}:${a.trim()}`);
      }
      return [raw];
    });
    // Cartesian product of all alternatives
    let combos = [[]];
    for (const alts of alternatives) {
      combos = combos.flatMap(prev => alts.map(a => [...prev, a]));
    }
    result.push(...combos);
  }
  return result;
}
