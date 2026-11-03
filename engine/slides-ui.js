// Building blocks for carousel slides. Each function returns HTML. Content is authored by the pipeline, not by end users.
// Set window.BRAND = { name, accent } before loading this file.
const BRAND = window.BRAND || { name: 'Brand', accent: '' };
const brandMark = () => `<span class="brand">${BRAND.name}<span class="g">${BRAND.accent}</span></span>`;
const slideTop = (n, total) => `<div class="glow1"></div><div class="glow2"></div><div class="top">${brandMark()}<span class="n">${n}/${total}</span></div>`;
const head = (kick, title, big, extra) => `<div class="head">${kick ? `<div class="kick">${kick}</div>` : ''}<div class="tt${big ? ' big' : ''}">${title}</div>${extra}</div>`;

const UI = {
  slide({ n, total, kick = '', title = '', big = false, vis = '', vt, extra = '' }) {
    return `<div class="slide">${slideTop(n, total)}${head(kick, title, big, extra)}<div class="vis"${vt ? ` style="--vt:${vt}px"` : ''}>${vis}</div></div>`;
  },
  // A phone that bleeds off the bottom edge of the slide.
  bleed({ n, total, kick = '', title = '', vis = '', vt = 560, extra = '' }) {
    return `<div class="slide">${slideTop(n, total)}${head(kick, title, false, extra)}<div class="vis" style="--vt:${vt}px;bottom:0;align-items:flex-end">${vis}</div></div>`;
  },
  closing({ n, total, line, verb, keyword, offer }) {
    return `<div class="slide">${slideTop(n, total)}<div class="endc"><div class="h2">${line}</div><div class="ul" style="width:520px"></div>
      <div class="p1" style="margin-top:50px">${verb}</div>
      <div class="g" style="font-weight:800;font-size:230px;line-height:1;letter-spacing:-6px">${keyword}</div>
      <div class="p1">${offer}</div></div></div>`;
  },
  records(list) {
    return `<div class="records">${list.map(([initial, name, status, last]) => `<div class="card record"><div class="av">${initial}</div><div style="text-align:left;flex:1">
      <div style="display:flex;align-items:center;gap:16px"><span class="nm">${name}</span><span class="pill">${status}</span></div>
      <div class="lv">${last}</div></div></div>`).join('')}</div>`;
  },
  bubble(dir, text, time = '', by = '') {
    return `<div class="bub ${dir}">${by ? `<span class="by">${by}</span>` : ''}<span>${text}</span>${time ? `<span class="tm">${time}</span>` : ''}</div>`;
  },
  chat(name, status, bubbles, height = 760) {
    return `<div class="mphone" style="height:${height}px"><div class="island"></div>
      <div class="wa-head"><div class="av">${name[0]}</div><div><div class="nm">${name}</div><div class="st">${status}</div></div></div>
      <div class="wa-body">${bubbles.join('')}</div></div>`;
  },
  calendar(title, range, days, hours, events, stamp = '') {
    const rows = hours.map(h => `<div class="hr">${h}</div>` + '<div class="cell"></div>'.repeat(days.length)).join('');
    const items = events.map(([col, row, text, cls = '']) => `<div class="ev ${cls}" style="left:calc(110px + (100% - 110px) / ${days.length} * ${col} + 6px);width:calc((100% - 110px) / ${days.length} - 12px);top:calc(56px + 92px * ${row} + 6px);height:80px">${text}</div>`).join('');
    return `<div style="position:relative;width:100%"><div class="card agenda static"><div class="ttl"><span>${title}</span><span class="p2 mut">${range}</span></div>
      <div class="grid"><div></div>${days.map(d => `<div class="dh">${d}</div>`).join('')}${rows}${items}</div></div>
      ${stamp ? `<div class="stamp" style="right:40px;bottom:-40px">${stamp}</div>` : ''}</div>`;
  },
  versus(oldLabel, oldText, oldIcon, newLabel, newText, newIcon) {
    return `<div class="vs"><div class="old"><div class="lbl">${oldLabel}</div><div class="txt2">${oldText}</div><div class="ic">${oldIcon}</div></div>
      <div class="new"><div class="lbl">${newLabel}</div><div class="txt2">${newText}</div><div class="ic">${newIcon}</div></div></div>`;
  },
  bars() { return `<div class="bars">${[30, 48, 66, 84, 100].map(h => `<i style="height:${h}%"></i>`).join('')}</div>`; },
  miniPhone(badge = '') { return `<div class="mini">${badge ? `<div class="badge">${badge}</div>` : ''}</div>`; },
};
function render(slides) { document.body.innerHTML = slides.join(''); }
