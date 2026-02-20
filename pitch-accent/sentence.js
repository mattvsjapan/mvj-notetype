function wordToRubyFragment(fragment) {
  const re = /([^\[\]]+)\[([^\]]+)\]/g;
  let result = '';
  let lastIndex = 0;
  let match;
  while ((match = re.exec(fragment)) !== null) {
    if (match.index > lastIndex) {
      result += fragment.slice(lastIndex, match.index);
    }
    result += `<ruby>${match[1]}<rt>${match[2]}</rt></ruby>`;
    lastIndex = re.lastIndex;
  }
  if (lastIndex < fragment.length) {
    result += fragment.slice(lastIndex);
  }
  return result;
}

function wordToRuby(word) {
  word = word.replaceAll(DEVOICED_PREFIX, '');
  word = word.replaceAll(LITERAL_PREFIX, '');
  return word.split(' ').map(wordToRubyFragment).join('');
}

function makeColoredSentence(sequence) {
  const spans = [];
  for (const section of sequence) {
    if (SENT_HIDDEN.includes(section.word) || /^-+$/.test(section.word) || section.isTape) continue;
    spans.push(`<span class="${section.classname}">${wordToRuby(section.word)}</span>`);
  }
  return spans.join('');
}
