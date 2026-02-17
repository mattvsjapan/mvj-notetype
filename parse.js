const GHOST_PARTICLE = '+';
const DEVOICED_PREFIX = '*';
const SENT_HIDDEN = ['|', GHOST_PARTICLE];
const PITCH_BREAKS = [...SENT_HIDDEN, ',', '、'];

function normalizeForParsing(expr) {
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
  return text.replace(/(\++)[\s\n.]*$/, ' $1');
}

function furiganaToReading(word) {
  return word.replace(/([^\[\]]*\[|])/g, '');
}

function filterKana(reading) {
  return reading.replace(/[^\u3040-\u309F\u30A0-\u30FF\*\+]/g, '');
}

function kanaToMoraes(kana) {
  return kana.match(/\*?.[ァィゥェォャュョぁぃぅぇぉゃゅょ]?/g) || [];
}

function splitToMoras(reading) {
  const kana = filterKana(reading);
  const raw = kanaToMoraes(kana);
  return raw.map(m => {
    if (m.startsWith(DEVOICED_PREFIX)) {
      return { text: m.slice(1), devoiced: true };
    }
    return { text: m, devoiced: false };
  });
}

function splitSection(raw) {
  const m = raw.match(/^([^:]+)(:)?(.*)$/);
  if (m) return { word: m[1], sep: m[2] || null, accent: m[3] || '' };
  return { word: raw, sep: null, accent: '' };
}

function splitAccent(raw) {
  if (!raw && raw !== '') raw = '';
  let m = raw.match(/^(p)?([a-zA-Z])?(-?\d)?$/);
  if (m) {
    return {
      is_particle: m[1] || null,
      role: m[2] || m[1] || null,
      pitch: m[3] || null,
    };
  }
  m = raw.match(/^([a-zA-Z]{1,2}):([hlHL]+)$/);
  if (m) {
    return { role: m[1], levels: m[2], keihan: true };
  }
  return { role: null, pitch: null };
}

function splitMultiplePitchNotations(sequences) {
  const result = [];
  for (const seq of sequences) {
    const first = splitSection(seq[0]);
    if (first.sep) {
      for (const accent of first.accent.split(',')) {
        result.push([`${first.word}:${accent.trim()}`, ...seq.slice(1)]);
      }
    } else {
      result.push(seq);
    }
  }
  return result;
}
