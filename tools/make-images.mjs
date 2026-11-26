// Make template images (1200x630 PNG) for news articles, OGP and the logo.
// Style follows source/post-uozu.svg. Free, no photos of other people.
//
//   node tools/make-images.mjs          # only images that do not exist yet
//   node tools/make-images.mjs --force  # remake all
//
// For a news article, set in content/news/<id>/meta.json:
//   "image": "/img/news/<id>.png", "scene": "school" | "document" | "snow" | "town" | "work",
//   "og_title": ["line 1", "line 2"], "og_sub": "やさしい にほんごの 一行"
import { createRequire } from 'node:module';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const { chromium } = createRequire(import.meta.url)('playwright'); // pre-installed globally or via npm i playwright
const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const FORCE = process.argv.includes('--force');
const esc = (s) => String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');

const base = `
  <rect width="560" height="630" fill="#dcebf5"/>
  <circle cx="440" cy="110" r="52" fill="#fbe3b8"/>
  <path d="M0 330 L90 230 L150 270 L240 150 L320 240 L390 190 L470 260 L560 210 L560 400 L0 400 Z" fill="#8fb3cc"/>
  <path d="M205 196 L240 150 L276 198 L256 190 L240 202 L222 190 Z M362 222 L390 190 L420 226 L404 218 L390 228 L376 218 Z" fill="#fff"/>
  <path d="M0 370 L140 320 L290 365 L430 315 L560 350 L560 440 L0 440 Z" fill="#5f8fae"/>
  <rect x="0" y="420" width="560" height="130" fill="#1d5d86"/>
  <path d="M20 455 Q70 445 120 455 T220 455 T320 455" stroke="#7fb0d0" stroke-width="4" fill="none" opacity=".6"/>
  <rect x="0" y="550" width="560" height="80" fill="#e9e2d3"/>`;

const people = `
  <circle cx="190" cy="512" r="14" fill="#6b4a3a"/><rect x="178" y="526" width="24" height="38" rx="9" fill="#e07a3f"/>
  <circle cx="232" cy="514" r="14" fill="#3b2a22"/><rect x="220" y="528" width="24" height="36" rx="9" fill="#2f7d6d"/>
  <circle cx="330" cy="512" r="14" fill="#8a5a3c"/><rect x="318" y="526" width="24" height="38" rx="9" fill="#7a5bb0"/>
  <circle cx="372" cy="514" r="14" fill="#2c1e18"/><rect x="360" y="528" width="24" height="36" rx="9" fill="#c9372e"/>`;

const house = (x, y, s = 1) => `<g transform="translate(${x} ${y}) scale(${s})"><rect x="0" y="22" width="70" height="48" fill="#f2eee6"/><rect x="0" y="44" width="70" height="26" fill="#d9d2c4"/><path d="M-8 26 L35 0 L78 26 Z" fill="#fff"/><path d="M35 0 L78 26 L58 26 Z" fill="#dfe9ef"/><rect x="26" y="40" width="18" height="18" fill="#f6c86b"/></g>`;

const SCENES = {
  school: `${base}
    <rect x="150" y="330" width="260" height="170" rx="6" fill="#fff"/>
    <rect x="135" y="312" width="290" height="30" rx="4" fill="#c9372e"/>
    <g fill="#bcd6e8"><rect x="172" y="362" width="44" height="40" rx="4"/><rect x="236" y="362" width="44" height="40" rx="4"/><rect x="300" y="362" width="44" height="40" rx="4"/><rect x="362" y="362" width="30" height="40" rx="4"/></g>
    <rect x="256" y="430" width="48" height="70" rx="4" fill="#1d5d86"/>
    <rect x="80" y="420" width="8" height="90" fill="#8a6a52"/><circle cx="84" cy="410" r="38" fill="#f3c6cf"/><circle cx="58" cy="430" r="28" fill="#f6d3da"/><circle cx="110" cy="432" r="28" fill="#efb8c3"/>
    <rect x="472" y="420" width="8" height="90" fill="#8a6a52"/><circle cx="476" cy="410" r="38" fill="#f3c6cf"/><circle cx="450" cy="432" r="28" fill="#efb8c3"/><circle cx="502" cy="432" r="28" fill="#f6d3da"/>
    ${people}`,
  document: `${base}
    <g transform="rotate(-6 280 420)">
      <rect x="150" y="300" width="250" height="300" rx="10" fill="#fff" stroke="#c9d7e2" stroke-width="3"/>
      <rect x="180" y="335" width="190" height="16" rx="8" fill="#1d5d86"/>
      <g fill="#d5e3ec"><rect x="180" y="375" width="190" height="10" rx="5"/><rect x="180" y="400" width="160" height="10" rx="5"/><rect x="180" y="425" width="175" height="10" rx="5"/><rect x="180" y="450" width="120" height="10" rx="5"/><rect x="180" y="500" width="190" height="10" rx="5"/><rect x="180" y="525" width="140" height="10" rx="5"/></g>
      <circle cx="335" cy="535" r="30" fill="none" stroke="#c9372e" stroke-width="5"/><circle cx="335" cy="535" r="18" fill="#c9372e" opacity=".25"/>
    </g>
    <g transform="rotate(5 380 470)">
      <rect x="290" y="390" width="220" height="140" rx="14" fill="#eaf3f9" stroke="#1d5d86" stroke-width="3"/>
      <rect x="308" y="410" width="62" height="78" rx="6" fill="#bcd6e8"/><circle cx="339" cy="438" r="15" fill="#5f8fae"/><path d="M314 486 Q339 452 364 486 Z" fill="#5f8fae"/>
      <g fill="#1d5d86"><rect x="384" y="414" width="110" height="10" rx="5"/></g>
      <g fill="#9fb7c8"><rect x="384" y="436" width="96" height="8" rx="4"/><rect x="384" y="454" width="80" height="8" rx="4"/><rect x="384" y="472" width="100" height="8" rx="4"/></g>
      <rect x="308" y="500" width="186" height="12" rx="6" fill="#c9372e" opacity=".85"/>
    </g>`,
  snow: `${base}
    <path d="M0 492 Q280 478 560 490 L560 630 L0 630 Z" fill="#fff"/>
    ${house(40, 440, 1)}${house(150, 456, .8)}${house(390, 440, 1)}${house(480, 460, .75)}
    <path d="M0 560 Q280 535 560 556" stroke="#3b4a55" stroke-width="22" fill="none"/>
    <path d="M0 560 Q280 535 560 556" stroke="#fff" stroke-width="3" stroke-dasharray="26 20" fill="none"/>
    <g transform="translate(230 505)"><rect x="0" y="12" width="96" height="30" rx="9" fill="#d9433a"/><path d="M18 12 L34 -6 L66 -6 L82 12 Z" fill="#c13a31"/><path d="M38 -2 h26 v12 h-32 Z" fill="#cfe6f3"/><circle cx="22" cy="46" r="10" fill="#1b2730"/><circle cx="74" cy="46" r="10" fill="#1b2730"/></g>
    <g fill="#fff"><circle cx="60" cy="60" r="5"/><circle cx="150" cy="120" r="4"/><circle cx="260" cy="70" r="5"/><circle cx="330" cy="140" r="4"/><circle cx="520" cy="60" r="5"/><circle cx="90" cy="200" r="4"/><circle cx="500" cy="190" r="4"/></g>`,
  town: `${base}
    ${house(40, 446, .9)}${house(130, 452, .75)}
    <rect x="250" y="370" width="150" height="130" fill="#f4f0e8"/><rect x="250" y="362" width="150" height="14" fill="#fff"/>
    <g fill="#f6c86b"><rect x="268" y="392" width="20" height="18"/><rect x="306" y="392" width="20" height="18"/><rect x="344" y="392" width="20" height="18"/><rect x="268" y="430" width="20" height="18"/><rect x="306" y="430" width="20" height="18"/><rect x="344" y="430" width="20" height="18"/></g>
    ${house(430, 448, .85)}
    ${people}`,
  work: `${base}
    <rect x="120" y="350" width="320" height="160" fill="#f4f0e8"/><path d="M120 350 L200 310 L200 350 L280 310 L280 350 L360 310 L360 350 L440 310 L440 350 Z" fill="#c9d7e2"/>
    <rect x="390" y="270" width="26" height="80" fill="#b8b1a3"/><rect x="190" y="420" width="70" height="90" fill="#1d5d86"/>
    <g fill="#bcd6e8"><rect x="290" y="390" width="40" height="30" rx="3"/><rect x="345" y="390" width="40" height="30" rx="3"/></g>
    ${people}`,
};

function cardHtml({ scene, label, title, sub }) {
  return `<!doctype html><html><head><meta charset="utf-8">
<link href="https://fonts.googleapis.com/css2?family=Zen+Kaku+Gothic+New:wght@500;700;900&display=swap" rel="stylesheet">
<style>
*{margin:0;box-sizing:border-box}
body{width:1200px;height:630px;display:grid;grid-template-columns:640px 560px;background:#f4f1ea;font-family:"Zen Kaku Gothic New",sans-serif;color:#1a2a36}
.txt{padding:48px 44px 40px 56px;display:flex;flex-direction:column}
.brand{align-self:flex-start;background:#fff;color:#1d5d86;font-weight:900;font-size:24px;padding:8px 22px;border-radius:30px;border:2px solid #dcebf5}
.brand b{color:#c9372e}
.label{align-self:flex-start;margin-top:auto;background:#c9372e;color:#fff;font-weight:700;font-size:22px;letter-spacing:.04em;padding:6px 22px;border-radius:24px}
h1{font-weight:900;font-size:50px;white-space:nowrap;line-height:1.18;margin-top:18px;letter-spacing:-.01em}
.sub{margin-top:16px;font-size:27px;font-weight:700;color:#1d5d86}
.foot{margin-top:auto;padding-top:18px;border-top:2px solid #d8d0c0;display:flex;justify-content:space-between;font-size:21px;font-weight:500;color:#5a6670}
.foot + * {display:none}
.txt.nolabel .label{display:none}
svg{display:block}
</style></head><body>
<div class="txt${label ? '' : ' nolabel'}">
  <div class="brand">Live &amp; Work <b>Toyama</b></div>
  <div class="label">${esc(label || '')}</div>
  <h1>${title.map(esc).join('<br>')}</h1>
  <div class="sub">${esc(sub || '')}</div>
  <div class="foot"><span>Jobs and daily life in Toyama</span><span>by Oiyo</span></div>
</div>
<svg width="560" height="630" viewBox="0 0 560 630">${SCENES[scene] || SCENES.town}</svg>
</body></html>`;
}

const logoHtml = `<!doctype html><html><body style="margin:0;width:512px;height:512px">
${fs.readFileSync(path.join(ROOT, 'static/favicon.svg'), 'utf8').replace('<svg ', '<svg width="512" height="512" ')}
</body></html>`;

const jobs = [
  { out: 'static/img/og-default.png', scene: 'town', label: '', title: ['Live and work', 'in Toyama'], sub: 'とやまで はたらく・くらす' },
  { out: 'static/img/og-guides.png', scene: 'snow', label: 'LIFE GUIDES', title: ['Simple guides for', 'life in Toyama'], sub: 'とやまの くらしの ガイド' },
];
const newsDir = path.join(ROOT, 'content/news');
for (const id of fs.readdirSync(newsDir)) {
  const metaPath = path.join(newsDir, id, 'meta.json');
  if (!fs.existsSync(metaPath)) continue;
  const m = JSON.parse(fs.readFileSync(metaPath, 'utf8'));
  if (!m.image || !m.og_title) continue;
  jobs.push({ out: path.join('static', m.image), scene: m.scene, label: 'NEWS', title: m.og_title, sub: m.og_sub });
}

const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1200, height: 630 }, deviceScaleFactor: 1 });
for (const j of jobs) {
  const out = path.join(ROOT, j.out);
  if (fs.existsSync(out) && !FORCE) continue;
  fs.mkdirSync(path.dirname(out), { recursive: true });
  await page.setContent(cardHtml(j), { waitUntil: 'networkidle' });
  await page.evaluate(async () => {
    await document.fonts.ready;
    const h = document.querySelector('h1'), box = document.querySelector('.txt');
    let size = 50;
    while (h.scrollWidth > box.clientWidth - 100 && size > 30) { size -= 2; h.style.fontSize = size + 'px'; }
  });
  await page.screenshot({ path: out });
  console.log('made', j.out);
}
const logo = path.join(ROOT, 'static/img/logo.png');
if (!fs.existsSync(logo) || FORCE) {
  await page.setViewportSize({ width: 512, height: 512 });
  await page.setContent(logoHtml);
  await page.screenshot({ path: logo, omitBackground: true });
  console.log('made static/img/logo.png');
}
await browser.close();
