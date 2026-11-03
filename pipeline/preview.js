// Quick composition check without a full render. Joins a few moments into one strip, with the safe-area lines in red.
// Usage: node preview.js page.html out.jpg t1 t2 t3 ...
const { chromium } = require('playwright-core');
const path = require('path');
const fs = require('fs');
const os = require('os');
const { execFileSync } = require('child_process');
const { pathToFileURL } = require('url');

(async () => {
  const [html, out, ...times] = process.argv.slice(2);
  const browser = await chromium.launch({ channel: process.env.CHROME_CHANNEL || 'chrome' });
  const page = await browser.newPage({ viewport: { width: 1080, height: 1920 } });
  const errors = [];
  page.on('pageerror', e => errors.push(e.message));
  await page.goto(pathToFileURL(path.resolve(html)).href);
  await page.evaluate(() => document.fonts.ready);
  if (errors.length) { console.error(errors); await browser.close(); process.exit(1); }
  const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'preview-'));
  const files = [];
  for (const t of times) {
    await page.evaluate(t => window.seek(t), +t);
    const file = path.join(tmp, `${files.length}.png`);
    await page.screenshot({ path: file });
    files.push(file);
  }
  await browser.close();
  // At the 0.4 scale used here, y=100 and y=600 are the 250 px and 1500 px safe-area limits.
  const scaled = files.map((_, i) => `[${i}]scale=432:768,drawbox=y=100:w=iw:h=1:color=red@0.8,drawbox=y=600:w=iw:h=1:color=red@0.8[v${i}]`).join(';');
  const stack = files.map((_, i) => `[v${i}]`).join('') + `hstack=inputs=${files.length}`;
  const graph = files.length > 1 ? `${scaled};${stack}` : scaled.replace('[v0]', '');
  execFileSync('ffmpeg', ['-y', '-v', 'error', ...files.flatMap(f => ['-i', f]), '-filter_complex', graph, out]);
  fs.rmSync(tmp, { recursive: true, force: true });
  console.log('ok', out);
})();
