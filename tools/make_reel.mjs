#!/usr/bin/env node
// Make an Instagram Reel (1080x1920 MP4, about 18 s) and its caption from a news article.
//   node tools/make_reel.mjs                      # newest article
//   node tools/make_reel.mjs 2026-11-27-some-id   # a given article
// Output (not committed): _reels/<id>.mp4 and _reels/<id>.txt (caption)
// The video shows English with easy Japanese under it. The caption has English, Vietnamese,
// Indonesian and easy Japanese. Text comes only from the article, so facts stay the same as on the site.
import { createRequire } from 'node:module';
import { execFileSync } from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const { chromium } = createRequire(import.meta.url)('playwright');
const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const NEWS = path.join(ROOT, 'content/news');
const OUT = path.join(ROOT, '_reels');
const id = process.argv[2] || fs.readdirSync(NEWS).filter(d => fs.existsSync(path.join(NEWS, d, 'meta.json'))).sort().pop();
const dir = path.join(NEWS, id);
const meta = JSON.parse(fs.readFileSync(path.join(dir, 'meta.json'), 'utf8'));
const esc = (s) => String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');

function readDoc(lang) {
  const f = path.join(dir, `${lang}.md`);
  if (!fs.existsSync(f)) return null;
  const raw = fs.readFileSync(f, 'utf8');
  const [head, rest] = raw.split(/\n---\n/);
  const fm = Object.fromEntries(head.split('\n').filter(l => l.includes(':')).map(l => [l.slice(0, l.indexOf(':')).trim(), l.slice(l.indexOf(':') + 1).trim()]));
  const sec = {};
  for (const part of rest.split(/^\+\+\+ /m).slice(1)) { const nl = part.indexOf('\n'); sec[part.slice(0, nl).trim()] = part.slice(nl + 1).trim(); }
  const points = (sec.short || '').split('\n').map(l => l.replace(/^\d+\.\s*/, '').trim()).filter(Boolean);
  return { ...fm, points, meaning: sec.meaning || '' };
}
const en = readDoc('en'), easy = readDoc('easy'), vi = readDoc('vi'), idn = readDoc('id'), ja = readDoc('ja');
const SITE = 'liveworktoyama.com';
const logo = 'data:image/png;base64,' + fs.readFileSync(path.join(ROOT, 'static/img/brand/wordmark.png')).toString('base64');
const photos = fs.existsSync(path.join(ROOT, 'content/photos.json')) ? JSON.parse(fs.readFileSync(path.join(ROOT, 'content/photos.json'), 'utf8')) : {};
const ph = meta.photo && photos[meta.photo];
const photo = ph ? 'data:image/jpeg;base64,' + fs.readFileSync(path.join(ROOT, 'static', ph.src)).toString('base64') : '';
const date = meta.date.replace(/^(\d+)-(\d+)-(\d+)$/, (_, y, m, d) => `${+m}/${+d}/${y}`);

const css = `
@import url('https://fonts.googleapis.com/css2?family=Nunito:wght@800;900&family=Zen+Kaku+Gothic+New:wght@500;700;900&display=block');
*{box-sizing:border-box;margin:0}
body{width:1080px;height:1920px;overflow:hidden;font-family:Nunito,'Zen Kaku Gothic New',sans-serif;color:#0f2433;background:#fff}
.page{position:relative;width:1080px;height:1920px;padding:120px 90px;display:flex;flex-direction:column}
.top{display:flex;justify-content:space-between;align-items:center}
.top img{height:78px}
.tag{display:inline-block;background:#00255f;color:#fff;font-weight:900;font-size:38px;padding:10px 28px;border-radius:40px}
.date{font-size:36px;font-weight:800;color:#037a50}
.mid{flex:1;display:flex;flex-direction:column;justify-content:center;gap:40px}
h1{font-size:92px;line-height:1.08;font-weight:900;letter-spacing:-1px}
.ez{font-family:'Zen Kaku Gothic New';font-weight:700;font-size:48px;line-height:1.5;color:#037a50}
.num{font-size:200px;font-weight:900;color:#00255f;line-height:1}
.pt{font-size:72px;line-height:1.2;font-weight:900}
.bar{height:14px;width:220px;border-radius:7px;background:linear-gradient(90deg,#00255f,#037a50)}
.foot{display:flex;justify-content:space-between;align-items:flex-end;font-size:34px;font-weight:800;color:#4a5f6d}
.scene{position:absolute;left:0;right:0;bottom:0;height:520px;z-index:-1;opacity:.95}
.langs{display:flex;flex-wrap:wrap;gap:18px}
.langs span{border:4px solid #00255f;border-radius:50px;padding:14px 30px;font-size:42px;font-weight:800;color:#00255f;background:#fff}
.url{font-size:76px;font-weight:900;color:#00255f}
.photo{width:100%;height:470px;object-fit:cover;border-radius:28px}
.credit{font-size:24px;color:#4a5f6d;margin-top:-28px}
.note{font-family:'Zen Kaku Gothic New';font-size:34px;line-height:1.5;color:#4a5f6d;font-weight:500}
`;
const scene = `<svg class="scene" viewBox="0 0 1080 520" preserveAspectRatio="xMidYMax slice"><defs><linearGradient id="s" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#fff"/><stop offset="1" stop-color="#e6f0f8"/></linearGradient></defs>
<rect width="1080" height="520" fill="url(#s)"/><path d="M0 330 L160 200 L260 260 L420 120 L560 240 L690 170 L840 260 L1080 180 L1080 520 L0 520Z" fill="#9fbfd6"/>
<path d="M380 160 L420 120 L462 166 L440 158 L420 172 L400 158Z M650 204 L690 170 L728 210 L708 202 L690 214 L672 202Z" fill="#fff"/>
<path d="M0 380 L260 330 L540 372 L800 320 L1080 360 L1080 520 L0 520Z" fill="#6f98b5"/><rect y="420" width="1080" height="100" fill="#00255f"/>
<path d="M0 470 C 200 430, 420 440, 600 462 S 900 480, 1080 440" stroke="#037a50" stroke-width="10" fill="none"/></svg>`;

const page = (inner, withScene = true) => `<!doctype html><html><head><meta charset="utf-8"><style>${css}</style></head><body><div class="page">${inner}</div>${withScene ? scene : ''}</body></html>`;
const top = `<div class="top"><img src="${logo}"><span class="tag">NEWS</span></div>`;
const foot = (n, total) => `<div class="foot"><span>${SITE}</span><span>${n}/${total}</span></div>`;
const pts = en.points.slice(0, 3);
const total = pts.length + 2;
const slides = [
  page(`${top}<div class="mid">${photo ? `<img class="photo" src="${photo}"><p class="credit">Photo: ${esc(ph.author)} / ${esc(ph.license)}</p>` : ''}<p class="date">${esc(date)}</p><h1>${esc(en.title)}</h1><div class="bar"></div><p class="ez">${esc(easy ? easy.title : '')}</p></div>${foot(1, total)}`),
  ...pts.map((p, i) => page(`${top}<div class="mid"><p class="num">${i + 1}</p><p class="pt">${esc(p)}</p><div class="bar"></div><p class="ez">${esc(easy && easy.points[i] ? easy.points[i] : '')}</p></div>${foot(i + 2, total)}`)),
  page(`${top}<div class="mid"><p class="pt">Read the full article in 5 languages</p><div class="langs"><span>English</span><span>やさしいにほんご</span><span>日本語</span><span>Tiếng Việt</span><span>Bahasa Indonesia</span></div><p class="url">${SITE}</p><p class="ez">プロフィールの リンクから よめます</p><p class="note">Private information site. Not a public office. For visa questions, ask immigration or a gyoseishoshi.</p></div>${foot(total, total)}`, false),
];

fs.mkdirSync(OUT, { recursive: true });
const tmp = fs.mkdtempSync(path.join(OUT, 'tmp-'));
const b = await chromium.launch();
const p = await b.newPage({ viewport: { width: 1080, height: 1920 } });
const files = [];
for (const [i, html] of slides.entries()) {
  await p.setContent(html, { waitUntil: 'networkidle' });
  await p.evaluate(() => document.fonts.ready);
  const f = path.join(tmp, `s${i}.png`);
  await p.screenshot({ path: f });
  files.push(f);
}
await b.close();

// Each slide 3.6 s (title 4 s), 0.5 s cross-fade, gentle zoom, silent audio track.
const durs = files.map((_, i) => (i === 0 ? 4.0 : 3.6));
const args = ['-y'];
files.forEach((f) => args.push('-i', f)); // one image each; zoompan makes the frames
const totalDur = durs.reduce((a, d) => a + d, 0) - 0.5 * (durs.length - 1);
args.push('-f', 'lavfi', '-t', totalDur.toFixed(2), '-i', 'anullsrc=channel_layout=stereo:sample_rate=44100');
let fc = '';
files.forEach((_, i) => { fc += `[${i}:v]scale=1188:2112,zoompan=z='min(zoom+0.0006,1.08)':d=${Math.round(durs[i] * 30)}:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s=1080x1920:fps=30,format=yuv420p,setsar=1[v${i}];`; });
let last = 'v0', t = durs[0];
for (let i = 1; i < files.length; i++) {
  const off = (t - 0.5).toFixed(2);
  fc += `[${last}][v${i}]xfade=transition=fade:duration=0.5:offset=${off}[x${i}];`;
  last = `x${i}`; t = t - 0.5 + durs[i];
}
fc = fc.replace(/;$/, '');
const mp4 = path.join(OUT, `${id}.mp4`);
args.push('-filter_complex', fc, '-map', `[${last}]`, '-map', `${files.length}:a`, '-shortest', '-c:v', 'libx264', '-preset', 'slow', '-crf', '32',
  '-pix_fmt', 'yuv420p', '-r', '30', '-c:a', 'aac', '-b:a', '128k', '-movflags', '+faststart', mp4);
execFileSync('ffmpeg', args, { stdio: 'ignore' });
fs.rmSync(tmp, { recursive: true, force: true });

const url = `https://${SITE}/en/news/${meta.slug || id}/`;
const caption = [
  `${en.title}`, '', ...en.points.map(x => `・${x}`), '',
  vi ? `🇻🇳 ${vi.title}` : '', idn ? `🇮🇩 ${idn.title}` : '', easy ? `🇯🇵 ${easy.title}` : '', '',
  `Read in 5 languages: link in bio / ${SITE}`,
  'Private information site, not a public office. For your own visa, ask immigration or a gyoseishoshi.', '',
  '#Toyama #富山 #LiveInJapan #WorkInJapan #外国人 #NguoiVietTaiNhat #OrangIndonesiaDiJepang #LiveWorkToyama',
].filter((l, i, a) => !(l === '' && a[i - 1] === '')).join('\n');
fs.writeFileSync(path.join(OUT, `${id}.txt`), caption + '\n');
const dur = execFileSync('ffprobe', ['-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', mp4]).toString().trim();
console.log(`made _reels/${id}.mp4 (${Number(dur).toFixed(1)} s, ${(fs.statSync(mp4).size / 1e6).toFixed(1)} MB) and _reels/${id}.txt`);
