function textToRuby(fragment) {
  fragment = fragment.replace(/\[(\d+)\]/g, '\u2045$1\u2046');
  var re = /([^\[\]]+)\[([^\]]+)\]/g;
  var result = '', lastIndex = 0, match;
  while ((match = re.exec(fragment)) !== null) {
    if (match.index > lastIndex) result += fragment.slice(lastIndex, match.index);
    var reading = match[2];
    if (reading.indexOf('|') !== -1) {
      var front = reading.split('|')[0];
      if (!front) { result += match[1]; lastIndex = re.lastIndex; continue; }
      result += '<ruby>' + match[1] + '<rt data-split>' + front + '</rt></ruby>';
    } else if (/[\u3040-\u309F\u30A0-\u30FFa-zA-Z]/.test(reading)) {
      result += '<ruby>' + match[1] + '<rt>' + reading + '</rt></ruby>';
    } else {
      result += match[1];
    }
    lastIndex = re.lastIndex;
  }
  if (lastIndex < fragment.length) result += fragment.slice(lastIndex);
  return result.replace(/\u2045/g, '[').replace(/\u2046/g, ']')
               .replace(/\[(\d+)\]/g, '<span class="pitch-num">$1</span>');
}

function wordToRuby(word) {
  word = word.replaceAll(DEVOICED_PREFIX, '');
  word = word.replaceAll(LITERAL_PREFIX, '');
  return word.split(' ').map(textToRuby).join('');
}

function makeColoredSentence(sequence) {
  const spans = [];
  for (const section of sequence) {
    if (SENT_HIDDEN.includes(section.word) || /^-+$/.test(section.word) || section.isTape) continue;
    spans.push(`<span class="${section.classname}">${wordToRuby(section.word)}</span>`);
  }
  return spans.join('');
}
