class Line {
  constructor() { this.x1 = this.y1 = this.x2 = this.y2 = null; this._tape = false; }
  start(x, y, tape = false) { this.x1 = x; this.y1 = y; this._tape = tape; return this; }
  end(x, y) { this.x2 = x; this.y2 = y; return this; }
  get isUnfinished() { return this.x1 != null && this.y1 != null; }
  get isCompleted() { return this.x2 != null && this.y2 != null; }

  adjustToRadius(r) {
    const tan = config.graph_height / config.x_step;
    const denom = Math.sqrt(1 + tan * tan);
    const sin = tan / denom, cos = 1 / denom;
    const oy = r * sin, ox = r * cos;
    if (this.y1 === this.y2) { this.x1 += r; this.x2 -= r; }
    else if (this.y1 > this.y2) { this.x1 += ox; this.y1 -= oy; this.x2 -= ox; this.y2 += oy; }
    else { this.x1 += ox; this.y1 += oy; this.x2 -= ox; this.y2 -= oy; }
    return this;
  }

  draw() {
    let s = `<line stroke="black" stroke-width="${config.stroke_width}" x1="${this.x1.toFixed(3)}" y1="${this.y1.toFixed(3)}" x2="${this.x2.toFixed(3)}" y2="${this.y2.toFixed(3)}" />`;
    if (this._tape) s = s.replace('<line', `<line stroke-dasharray="${config.stroke_dasharray}"`);
    return s;
  }
}

class Path {
  constructor() { this.lines = []; }
  get last() { return this.lines[this.lines.length - 1]; }
  startAt(x, y) { this.lines.push(new Line().start(x, y)); }
  goTo(x, y) { this.last.end(x, y); }
  push(x, y) {
    if (this.lines.length === 0) { this.startAt(x, y); }
    else if (this.last.isCompleted) { this.startAt(this.last.x2, this.last.y2); this.goTo(x, y); }
    else { this.goTo(x, y); }
  }
  draw() {
    return this.lines
      .filter(l => l.isCompleted)
      .map(l => { l.adjustToRadius(config.circle_radius); return l.draw(); })
      .join('');
  }
}

function shouldConnect(section, prev) {
  if (prev.isTape) return true;
  if (section.role === 'empty' || prev.role === 'empty') return false;
  return true;
}

function makeCircle(x, y) {
  return `<circle fill="black" stroke="black" stroke-width="${config.stroke_width}" cx="${x}" cy="${y}" r="${config.circle_radius}"></circle>`;
}

function makeDevoicedCircle(mora, x, y) {
  if (mora.text.length === 1) {
    const cx = x + config.font_size / 2 + config.text_dx;
    const cy = y + config.text_dx + Math.ceil(config.stroke_width);
    return `<circle class="devoiced" cx="${cx}" cy="${cy}" stroke-width="${config.devoiced_circle_width}" r="${config.devoiced_circle_radius}" stroke-dasharray="${config.devoiced_stroke_disarray}" />`;
  }
  const fs = config.font_size, r = config.devoiced_circle_radius;
  const ry = y - config.font_size - Math.floor(config.stroke_width);
  const pad = config.devoiced_rectangle_padding;
  return `<rect class="devoiced" x="${x - fs - pad}" y="${ry}" width="${fs * 2 + pad * 2}" height="${r * 2}" rx="${r}" stroke-width="${config.devoiced_circle_width}" stroke-dasharray="${config.devoiced_stroke_disarray}" />`;
}

function makeGroup(elements, cls) { return `<g class="${cls}">${elements.join('')}</g>`; }
function makeSvg(contents, w, h, vh) {
  return `<svg style="font-family: ${config.graph_font}" viewBox="0 0 ${w} ${h}" height="${vh}px" xmlns="http://www.w3.org/2000/svg">${contents}</svg>`;
}
function makeText(mora, x, y, dx) {
  const cls = mora.devoiced ? ' class="devoiced"' : '';
  return `<text${cls} font-size="${config.font_size}px" fill="black" x="${x}" y="${y}" dx="${dx}">${mora.text}</text>`;
}

function calcSvgWidth(sequence, step) {
  return sequence.reduce((sum, s) => sum + (s.role !== 'empty' ? s.moraes.length : 0), 0) * step
    + config.graph_horizontal_padding * 2;
}

function makeGraph(sequence) {
  sequence = filterEmptyMoraes(sequence);
  if (!sequence.length) return null;

  let xPos = config.size_unit + config.graph_horizontal_padding;
  let yPos = config.size_unit;
  const heightHigh = config.size_unit;
  const heightLow = heightHigh + config.graph_height;
  const xStep = config.x_step;
  const heightKana = heightLow + xStep;

  const circles = [], paths = [], text = [];

  for (let i = 0; i < sequence.length; i++) {
    const section = sequence[i];
    if (section.role === 'empty' || section.isTape) continue;

    const wordCircles = [], textMoraes = [];
    const path = new Path();
    const connector = new Line();

    if (i > 0 && shouldConnect(section, sequence[i - 1])) {
      connector.start(xPos - xStep, yPos, sequence[i - 1].isTape);
    }

    const moraes = section.moraes;
    for (let j = 0; j < moraes.length; j++) {
      const mora = moraes[j];
      let moraLevel;
      if (mora.text === 'っ' || mora.text === 'ッ') {
        moraLevel = (j === 1 && section.levels[j - 1] === L) ? section.levels[j - 1] : section.levels[j];
      } else {
        moraLevel = section.levels[j];
      }
      yPos = moraLevel === H ? heightHigh : heightLow;
      wordCircles.push(makeCircle(xPos, yPos));
      path.push(xPos, yPos);

      if (j === 0 && connector.isUnfinished) {
        connector.end(xPos, yPos);
      }

      if (mora.text !== GHOST_PARTICLE) {
        if (mora.devoiced) {
          textMoraes.push(makeDevoicedCircle(mora, xPos, heightKana));
        }
        textMoraes.push(makeText(mora, xPos, heightKana, config.text_dx * mora.text.length));
      }

      xPos += xStep;
    }

    circles.push(makeGroup(wordCircles, section.classname));
    paths.push(makeGroup([path.draw()], section.classname));
    text.push(makeGroup(textMoraes, section.classname));

    if (connector.isCompleted) {
      paths.push(makeGroup([connector.adjustToRadius(config.circle_radius).draw()], 'connector'));
    }
  }

  const content = [makeGroup(paths, 'paths'), makeGroup(circles, 'circles')];
  const svgWidth = calcSvgWidth(sequence, xStep);
  const svgHeightText = heightKana + config.size_unit;
  const svgHeightNoText = heightLow + config.size_unit;

  let svgHeight, visibleHeight;
  if (config.no_text) {
    svgHeight = svgHeightNoText;
    visibleHeight = Math.round((svgHeightNoText / svgHeightText) * config.graph_visible_height);
  } else {
    svgHeight = svgHeightText;
    visibleHeight = config.graph_visible_height;
    content.push(makeGroup(text, 'text'));
  }

  return makeSvg(content.join(''), svgWidth, svgHeight, visibleHeight);
}
