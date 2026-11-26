#!/usr/bin/env node
// Automatic UI check of the built site (_site/). Run after `python3 build.py`:
//   node tools/ui_check.mjs
// Checks at phone width 375px (and 1280px): no horizontal scroll, tap targets >= 44px,
// header/footer links open, every internal link on the checked pages opens, dark mode text is readable.
// Exit code 1 when something fails, so the daily/weekly tasks do not publish a broken page.
import { createRequire } from 'node:module';
import fs from 'node:fs';
import http from 'node:http';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const { chromium } = createRequire(import.meta.url)('playwright');
const ROOT = path.join(path.dirname(fileURLToPath(import.meta.url)), '..', '_site');
const TYPES = { '.html': 'text/html; charset=utf-8', '.css': 'text/css', '.js': 'text/javascript', '.svg': 'image/svg+xml',
  '.png': 'image/png', '.json': 'application/json', '.xml': 'application/xml', '.txt': 'text/plain' };
const srv = http.createServer((req, res) => {
  let p = path.join(ROOT, decodeURIComponent(req.url.split('?')[0].split('#')[0]));
  if (fs.existsSync(p) && fs.statSync(p).isDirectory()) p = path.join(p, 'index.html');
  if (!fs.existsSync(p)) { res.statusCode = 404; return res.end('404'); }
  res.setHeader('Content-Type', TYPES[path.extname(p)] || 'application/octet-stream');
  res.end(fs.readFileSync(p));
}).listen(0);
const BASE = `http://localhost:${srv.address().port}`;

const LANGS = ['en', 'easy', 'ja', 'vi', 'id'];
const pick = (dir) => { try { const d = fs.readdirSync(path.join(ROOT, dir)).filter(x => fs.existsSync(path.join(ROOT, dir, x, 'index.html'))); return d.sort().reverse()[0]; } catch { return null; } };
const pages = [];
for (const l of LANGS) {
  pages.push(`/${l}/`, `/${l}/news/`, `/${l}/guides/`, `/${l}/jobs/`, `/${l}/jobs/search/`, `/${l}/students/`, `/${l}/employers/`);
  const n = pick(`${l}/news`); if (n) pages.push(`/${l}/news/${n}/`);
  for (const g of ['changing-jobs', 'driving-in-snow', 'help-in-your-language']) pages.push(`/${l}/guides/${g}/`);
}
pages.push('/business/', '/about/', '/partners/');

const problems = [];
const seen = new Set();
const b = await chromium.launch();
for (const [w, scheme] of [[375, 'light'], [375, 'dark'], [1280, 'light']]) {
  const p = await b.newPage({ viewport: { width: w, height: 800 }, colorScheme: scheme });
  for (const u of pages) {
    if (scheme === 'dark' && !u.endsWith('/') ) continue;
    const r = await p.goto(BASE + u);
    if (!r || r.status() !== 200) { problems.push(`${u}: HTTP ${r && r.status()}`); continue; }
    if (u.includes('/search/')) await p.waitForTimeout(800);
    const res = await p.evaluate((scheme) => {
      const out = { over: 0, small: [], links: [], contrast: [] };
      const de = document.documentElement;
      out.over = de.scrollWidth - de.clientWidth;
      const sel = 'a.btn, button, .chip, header nav a, footer nav a, .hlangs a, .tel, input:not([type=checkbox]):not([type=radio]), select, summary, a.gtile, a.jmini, .chk';
      document.querySelectorAll(sel).forEach(el => {
        const rc = el.getBoundingClientRect();
        if (rc.width && rc.height < 44 && !el.closest('.crumbs')) out.small.push(`${el.tagName.toLowerCase()}.${el.className || ''} "${(el.textContent || '').trim().slice(0, 20)}" ${Math.round(rc.height)}px`);
      });
      document.querySelectorAll('a[href^="/"]').forEach(a => out.links.push(a.getAttribute('href')));
      // contrast of main text blocks
      const lum = (c) => { const m = c.match(/\d+(\.\d+)?/g); if (!m) return null; const [r, g, b2] = m.slice(0, 3).map(v => { v = v / 255; return v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4; }); return 0.2126 * r + 0.7152 * g + 0.0722 * b2; };
      const bgOf = (el) => { while (el) { const c = getComputedStyle(el).backgroundColor; if (c && !c.startsWith('rgba(0, 0, 0, 0)') && c !== 'transparent') return c; el = el.parentElement; } return getComputedStyle(document.body).backgroundColor; };
      document.querySelectorAll('main p, main li, main h1, main h2, main h3, main a, header a').forEach(el => {
        if (!el.textContent.trim() || !el.getBoundingClientRect().width) return;
        const fg = lum(getComputedStyle(el).color), bg = lum(bgOf(el));
        if (fg == null || bg == null) return;
        const cr = (Math.max(fg, bg) + 0.05) / (Math.min(fg, bg) + 0.05);
        if (cr < 4.5) out.contrast.push(`"${el.textContent.trim().slice(0, 24)}" ${cr.toFixed(1)}:1`);
      });
      return out;
    }, scheme);
    if (res.over > 0) problems.push(`${u} (${w}px ${scheme}): horizontal scroll +${res.over}px`);
    [...new Set(res.small)].slice(0, 5).forEach(s => problems.push(`${u} (${w}px): small tap target ${s}`));
    [...new Set(res.contrast)].slice(0, 5).forEach(s => problems.push(`${u} (${scheme}): low contrast ${s}`));
    res.links.forEach(h => seen.add(h.split('#')[0]));
  }
  await p.close();
}
// every internal link found on the checked pages must open
for (const h of seen) {
  const f = path.join(ROOT, decodeURIComponent(h.split('?')[0]));
  const ok = fs.existsSync(f) && (fs.statSync(f).isFile() || fs.existsSync(path.join(f, 'index.html')));
  if (!ok) problems.push(`broken internal link: ${h}`);
}
await b.close(); srv.close();
console.log(`UI check: ${pages.length} pages x 3 views, ${seen.size} internal links`);
if (problems.length) { console.log(`NG: ${problems.length} problems`); problems.slice(0, 80).forEach(x => console.log('  ' + x)); process.exit(1); }
console.log('OK');
