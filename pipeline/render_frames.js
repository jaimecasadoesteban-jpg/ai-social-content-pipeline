// Renders an HTML animation to video frames with headless Chrome.
// The page defines window.seek(t). If it also defines window.DUR / audit() / meta(), they are used.
// Usage: node render_frames.js page.html frames_dir [duration|auto] [fps] [width] [height]
// Leaves 00000.jpg... in frames_dir, and audit.json + meta.json next to it.
const { chromium } = require('playwright-core');
const path = require('path');
const fs = require('fs');
const { pathToFileURL } = require('url');

(async () => {
  const [html, outDir, durArg = 'auto', fps = 30, w = 1080, h = 1920] = process.argv.slice(2);
  fs.rmSync(outDir, { recursive: true, force: true });
  fs.mkdirSync(outDir, { recursive: true });
  const browser = await chromium.launch({ channel: process.env.CHROME_CHANNEL || 'chrome', headless: true });
  const page = await browser.newPage({ viewport: { width: +w, height: +h }, deviceScaleFactor: 1 });
  const errors = [];
  page.on('pageerror', e => errors.push(e.message));
  page.on('console', m => { if (m.type() === 'error') errors.push(m.text()); });
  await page.goto(pathToFileURL(path.resolve(html)).href);
  await page.evaluate(() => document.fonts.ready);
  await page.waitForTimeout(300);
  if (errors.length) { console.error('Page errors:', errors); await browser.close(); process.exit(1); }
  const dur = durArg === 'auto' ? await page.evaluate(() => window.DUR) : +durArg;
  const hasAudit = await page.evaluate(() => typeof window.audit === 'function');
  const total = Math.round(dur * +fps);
  const audit = [];
  for (let i = 0; i < total; i++) {
    const t = i / +fps;
    await page.evaluate(t => window.seek(t), t);
    if (hasAudit) audit.push({ t: +t.toFixed(3), items: await page.evaluate(() => window.audit()) });
    await page.screenshot({ path: path.join(outDir, String(i).padStart(5, '0') + '.jpg'), type: 'jpeg', quality: 95 });
  }
  const parent = path.dirname(path.resolve(outDir));
  if (hasAudit) fs.writeFileSync(path.join(parent, 'audit.json'), JSON.stringify(audit));
  const meta = await page.evaluate(() => (typeof window.meta === 'function' ? window.meta() : { DUR: window.DUR }));
  meta.fps = +fps; meta.frames = total;
  fs.writeFileSync(path.join(parent, 'meta.json'), JSON.stringify(meta, null, 1));
  await browser.close();
  console.log(`${total} frames (${dur.toFixed(2)} s) in ${outDir}`);
})();
