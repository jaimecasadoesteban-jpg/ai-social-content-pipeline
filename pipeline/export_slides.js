// Exports every .slide of a page as a PNG and warns about text that overflows its slide.
// Usage: node export_slides.js page.html out_dir
const { chromium } = require('playwright-core');
const path = require('path');
const fs = require('fs');
const { pathToFileURL } = require('url');

(async () => {
  const [html, out] = process.argv.slice(2);
  fs.mkdirSync(out, { recursive: true });
  const browser = await chromium.launch({ channel: process.env.CHROME_CHANNEL || 'chrome' });
  const page = await browser.newPage({ viewport: { width: 1080, height: 1920 }, deviceScaleFactor: 1 });
  const errors = [];
  page.on('pageerror', e => errors.push(e.message));
  await page.goto(pathToFileURL(path.resolve(html)).href);
  await page.evaluate(() => document.fonts.ready);
  await page.waitForTimeout(300);
  if (errors.length) { console.error(errors); await browser.close(); process.exit(1); }
  const slides = await page.$$('.slide');
  for (let i = 0; i < slides.length; i++) {
    const name = await slides[i].getAttribute('data-name');
    await slides[i].screenshot({ path: path.join(out, (name || String(i + 1).padStart(2, '0')) + '.png') });
  }
  const overflow = await page.evaluate(() => [...document.querySelectorAll('.slide')].flatMap((slide, i) => {
    const box = slide.getBoundingClientRect();
    return [...slide.querySelectorAll('.tt,.txt2,.nm,.msg,.bub span,.note,.lbl,.kick,.h1,.h2,.h3,.p1,.p2')].filter(el => {
      const r = el.getBoundingClientRect();
      return r.width && (r.top < box.top + 40 || r.bottom > box.bottom - 30 || r.left < box.left + 30 || r.right > box.right - 30);
    }).map(el => `slide ${i + 1}: "${el.textContent.trim().slice(0, 40)}"`);
  }));
  await browser.close();
  if (overflow.length) { console.error('OUTSIDE MARGINS:', overflow); process.exit(1); }
  console.log(`${slides.length} slides in ${out}`);
})();
