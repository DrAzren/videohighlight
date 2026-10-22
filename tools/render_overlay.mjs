// Capture a seekable HTML composition (window.seek(t), window.ready) frame by frame as
// transparent PNGs using the pre-installed Playwright Chromium.
//
// Usage: node render_overlay.mjs URL OUT_DIR [FPS=30] [SECONDS=30] [WORKERS=4] [FRAMES=all|a-b|n,n,n]
import { createRequire } from 'module';
import { mkdirSync } from 'fs';

const require = createRequire(import.meta.url);
const { chromium } = require('/opt/node22/lib/node_modules/playwright');

const [url, outDir, fpsArg = '30', secArg = '30', workersArg = '4', framesArg = 'all'] = process.argv.slice(2);
const fps = +fpsArg, total = Math.round(+secArg * fps), workers = +workersArg;
mkdirSync(outDir, { recursive: true });

let frames = [...Array(total).keys()];
if (framesArg.includes('-')) {
  const [a, b] = framesArg.split('-').map(Number);
  frames = frames.filter(f => f >= a && f <= b);
} else if (framesArg !== 'all') {
  frames = framesArg.split(',').map(Number);
}

const browser = await chromium.launch();
const t0 = Date.now();
let done = 0;
await Promise.all([...Array(workers).keys()].map(async w => {
  const page = await browser.newPage({ viewport: { width: 1080, height: 1920 }, deviceScaleFactor: 1 });
  page.on('pageerror', e => console.error('pageerror:', e.message));
  await page.goto(url);
  await page.evaluate(() => window.ready);
  for (let i = w; i < frames.length; i += workers) {
    const f = frames[i];
    await page.evaluate(t => window.seek(t), f / fps);
    await page.screenshot({ path: `${outDir}/f${String(f).padStart(4, '0')}.png`, omitBackground: true });
    if (++done % 60 === 0) console.log(`${done}/${frames.length} frames (${((Date.now() - t0) / 1000).toFixed(0)}s)`);
  }
}));
await browser.close();
console.log(`rendered ${frames.length} frames in ${((Date.now() - t0) / 1000).toFixed(1)}s`);
