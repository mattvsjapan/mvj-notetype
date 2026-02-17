function wordToRuby(word) {
  word = word.replaceAll(DEVOICED_PREFIX, '');
  const re = /([^\[\]]+)\[([^\]]+)\]/g;
  let result = '';
  let lastIndex = 0;
  let match;
  while ((match = re.exec(word)) !== null) {
    if (match.index > lastIndex) {
      result += word.slice(lastIndex, match.index);
    }
    result += `<ruby>${match[1]}<rt>${match[2]}</rt></ruby>`;
    lastIndex = re.lastIndex;
  }
  if (lastIndex < word.length) {
    result += word.slice(lastIndex);
  }
  return result;
}

function makeColoredSentence(sequence) {
  const spans = [];
  for (const section of sequence) {
    if (SENT_HIDDEN.includes(section.word) || /^\++$/.test(section.word) || section.isTape) continue;
    spans.push(`<span class="${section.classname}">${wordToRuby(section.word)}</span>`);
  }
  return spans.join('');
}
