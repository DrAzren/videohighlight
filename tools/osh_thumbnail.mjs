// Render the reel's cover images from reel/thumbnail/cover.html with headless Chromium.
// Usage: node tools/osh_thumbnail.mjs  ->  release/OSH_MegaDay_2026_cover_9x16.jpg + _16x9.jpg
import { createRequire } from "node:module";
import path from "node:path";
import { fileURLToPath } from "node:url";

const require = createRequire(import.meta.url);
const { chromium } = require("playwright");  // global install: run with NODE_PATH set to the global node_modules
const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const page_ = "file://" + path.join(root, "reel/thumbnail/cover.html");
const browser = await chromium.launch();
for (const [f, w, h] of [["9x16", 1080, 1920], ["16x9", 1280, 720]]) {
  const page = await browser.newPage({ viewport: { width: w, height: h } });
  await page.goto(`${page_}?f=${f}`);
  await page.evaluate(() => document.fonts.ready);
  await page.waitForTimeout(300);
  const out = path.join(root, `release/OSH_MegaDay_2026_cover_${f}.png`);
  await page.screenshot({ path: out });
  console.log("wrote", out);
}
await browser.close();
