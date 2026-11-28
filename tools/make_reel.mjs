#!/usr/bin/env node
// Make an Instagram Reel (1080x1920 MP4, about 18 s) and its caption from a news article.
//   node tools/make_reel.mjs                      # newest article
//   node tools/make_reel.mjs 2026-11-27-some-id   # a given article
// Output (not committed): _reels/<id>.mp4 and _reels/<id>.txt (caption)
//
// Design: when the article has a photo (content/photos.json), the photo fills the screen
// (the tall version from content/photos/tall/ when there is one) with a slow camera move,
// and the text slides in on a dark panel. Without a photo, the illustrated white design is used.
// Text comes only from the article, so facts stay the same as on the site.
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
const b64 = (f, type) => `data:${type};base64,` + fs.readFileSync(f).toString('base64');

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
const en = readDoc('en'), easy = readDoc('easy'), vi = readDoc('vi'), idn = readDoc('id');
const SITE = 'liveworktoyama.com';
const logo = b64(path.join(ROOT, 'static/img/brand/wordmark.png'), 'image/png');
const logoDark = b64(path.join(ROOT, 'static/img/brand/wordmark-dark.png'), 'image/png');
const photos = fs.existsSync(path.join(ROOT, 'content/photos.json')) ? JSON.parse(fs.readFileSync(path.join(ROOT, 'content/photos.json'), 'utf8')) : {};
const ph = meta.photo && photos[meta.photo];
const photoFile = ph ? (ph.tall && fs.existsSync(path.join(ROOT, ph.tall)) ? path.join(ROOT, ph.tall) : path.join(ROOT, 'static', ph.src)) : null;
const photo = photoFile ? b64(photoFile, 'image/jpeg') : '';
const credit = ph ? `Photo: ${ph.author}${ph.license ? ' / ' + ph.license : ''}` : '';
const date = meta.date.replace(/^(\d+)-(\d+)-(\d+)$/, (_, y, m, d) => `${+m}/${+d}/${y}`);
const tag = { outings: 'DAYS OUT', work: 'WORK', life: 'LIFE', rules: 'RULES' }[meta.category] || 'NEWS';
const pts = en.points.slice(0, 3);
const total = pts.length + 2;

const css = `
@import url('https://fonts.googleapis.com/css2?family=Nunito:wght@800;900&family=Zen+Kaku+Gothic+New:wght@500;700;900&display=block');
*{box-sizing:border-box;margin:0}
html,body{width:1080px;height:1920px;overflow:hidden;background:transparent}
body{font-family:Nunito,'Zen Kaku Gothic New',sans-serif;color:#0f2433}
.bg{position:absolute;inset:0;background:#fff}
.bg img.cover{position:absolute;inset:0;width:100%;height:100%;object-fit:cover}
.bg .shade{position:absolute;inset:0;background:linear-gradient(180deg,rgba(0,20,45,.55) 0%,rgba(0,20,45,0) 22%,rgba(0,20,45,0) 45%,rgba(0,20,45,.82) 100%)}
.bg .dim{position:absolute;inset:0;background:rgba(0,20,45,.35)}
.bg.navy{background:#00255f}
.bg.navy img.cover{filter:blur(28px) brightness(.5);transform:scale(1.15)}
.layer{position:absolute;inset:0;padding:110px 80px 120px;display:flex;flex-direction:column}
.prog{position:absolute;top:56px;left:80px;right:80px;display:flex;gap:10px}
.prog i{flex:1;height:8px;border-radius:4px;background:rgba(255,255,255,.35)}
.prog i.on{background:#fff}
.light .prog i{background:#d6dee6}.light .prog i.on{background:#00255f}
.top{display:flex;justify-content:space-between;align-items:center;margin-top:24px}
.top img{height:74px}
.tag{display:inline-block;background:#037a50;color:#fff;font-weight:900;font-size:36px;padding:10px 28px;border-radius:40px;letter-spacing:1px}
.light .tag{background:#00255f}
.fill{flex:1}
.panel{background:rgba(0,22,50,.58);backdrop-filter:blur(6px);border-radius:36px;padding:44px 50px;color:#fff}
.light .panel{background:none;padding:0;color:#0f2433;backdrop-filter:none}
.date{font-size:36px;font-weight:800;color:#9fe3c4;margin-bottom:18px}
.light .date{color:#037a50}
h1{font-size:78px;line-height:1.08;font-weight:900;letter-spacing:-1px;text-shadow:0 2px 18px rgba(0,0,0,.25)}
.light h1{text-shadow:none;font-size:92px}
.light .pt{font-size:70px}
.ez{font-family:'Zen Kaku Gothic New';font-weight:700;font-size:42px;line-height:1.5;color:#b9f0d6;margin-top:24px}
.light .ez{color:#037a50}
.num{display:inline-flex;align-items:center;justify-content:center;width:100px;height:100px;border-radius:50px;background:#037a50;color:#fff;font-size:60px;font-weight:900;margin-bottom:24px}
.light .num{background:#00255f}
.pt{font-size:62px;line-height:1.2;font-weight:900}
.bar{height:12px;width:200px;border-radius:6px;background:linear-gradient(90deg,#7cc4ef,#2dbe85);margin:34px 0 0}
.light .bar{background:linear-gradient(90deg,#00255f,#037a50)}
.foot{display:flex;justify-content:space-between;align-items:flex-end;font-size:32px;font-weight:800;color:rgba(255,255,255,.85);margin-top:40px}
.light .foot{color:#4a5f6d}
.credit{font-size:24px;font-weight:700;opacity:.8}
.langs{display:flex;flex-wrap:wrap;gap:18px;margin:36px 0}
.langs span{border:4px solid #fff;border-radius:50px;padding:14px 30px;font-size:42px;font-weight:800;color:#fff}
.url{font-size:80px;font-weight:900;color:#fff}
.note{font-family:'Zen Kaku Gothic New';font-size:32px;line-height:1.5;color:rgba(255,255,255,.85);font-weight:500;margin-top:30px}
.scene{position:absolute;left:0;right:0;bottom:0;height:520px;opacity:.95}
`;
const scene = `<svg class="scene" viewBox="0 0 1080 520" preserveAspectRatio="xMidYMax slice"><defs><linearGradient id="s" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#fff"/><stop offset="1" stop-color="#e6f0f8"/></linearGradient></defs>
<rect width="1080" height="520" fill="url(#s)"/><path d="M0 330 L160 200 L260 260 L420 120 L560 240 L690 170 L840 260 L1080 180 L1080 520 L0 520Z" fill="#9fbfd6"/>
<path d="M380 160 L420 120 L462 166 L440 158 L420 172 L400 158Z M650 204 L690 170 L728 210 L708 202 L690 214 L672 202Z" fill="#fff"/>
<path d="M0 380 L260 330 L540 372 L800 320 L1080 360 L1080 520 L0 520Z" fill="#6f98b5"/><rect y="420" width="1080" height="100" fill="#00255f"/>
<path d="M0 470 C 200 430, 420 440, 600 462 S 900 480, 1080 440" stroke="#037a50" stroke-width="10" fill="none"/></svg>`;

const doc = (inner) => `<!doctype html><html><head><meta charset="utf-8"><style>${css}</style></head><body>${inner}</body></html>`;
const light = !photo;
// backgrounds (moved by ffmpeg) and text layers (transparent, animated by ffmpeg)
const bgPhoto = (cls = '') => doc(`<div class="bg ${cls}"><img class="cover" src="${photo}"><div class="${cls ? '' : 'shade'}"></div></div>`);
const bgLight = doc(`<div class="bg">${scene}</div>`);
const bgCta = photo ? bgPhoto('navy') : doc('<div class="bg navy"></div>');
const prog = (n) => `<div class="prog">${Array.from({ length: total }, (_, i) => `<i class="${i < n ? 'on' : ''}"></i>`).join('')}</div>`;
const head = (dark) => `<div class="top"><img src="${dark ? logoDark : logo}"><span class="tag">${tag}</span></div>`;
const foot = (n) => `<div class="foot"><span>${SITE}</span><span>${credit && n < total ? `<span class="credit">${esc(credit)}</span>` : `${n}/${total}`}</span></div>`;
const layer = (n, body, forceDark = false) => {
  const isLight = light && !forceDark;  // white design: text in the middle, above the illustrated mountains
  return doc(`<div class="layer ${isLight ? 'light' : ''}">${prog(n)}${head(!isLight)}<div class="fill"></div>${body}${isLight ? '<div class="fill" style="flex:1.4"></div>' : ''}${foot(n)}</div>`);
};

const slides = [
  { bg: light ? bgLight : bgPhoto(), txt: layer(1, `<div class="panel"><p class="date">${esc(date)}</p><h1>${esc(en.title)}</h1><p class="ez">${esc(easy ? easy.title : '')}</p></div>`), dur: light ? 4.2 : 5.0, delay: light ? 0.15 : 1.1 },
  ...pts.map((p, i) => ({ bg: light ? bgLight : bgPhoto(), txt: layer(i + 2, `<div class="panel"><span class="num">${i + 1}</span><p class="pt">${esc(p)}</p><div class="bar"></div><p class="ez">${esc(easy && easy.points[i] ? easy.points[i] : '')}</p></div>`), dur: 3.8 })),
  { bg: bgCta, txt: layer(total, `<div><p class="pt" style="color:#fff">Read the full article in 5 languages</p><div class="langs"><span>English</span><span>やさしいにほんご</span><span>日本語</span><span>Tiếng Việt</span><span>Bahasa Indonesia</span></div><p class="url">${SITE}</p><p class="ez">プロフィールの リンクから よめます</p><p class="note">Private information site. Not a public office. For visa questions, ask immigration or a gyoseishoshi.</p></div>`, true), dur: 3.6 },
];

fs.mkdirSync(OUT, { recursive: true });
const tmp = fs.mkdtempSync(path.join(OUT, 'tmp-'));
const b = await chromium.launch();
const p = await b.newPage({ viewport: { width: 1080, height: 1920 } });
const shot = async (html, file, transparent) => {
  await p.setContent(html, { waitUntil: 'networkidle' });
  await p.evaluate(() => document.fonts.ready);
  await p.screenshot({ path: file, omitBackground: transparent });
};
for (const [i, s] of slides.entries()) {
  await shot(s.bg, path.join(tmp, `b${i}.png`), false);
  await shot(s.txt, path.join(tmp, `t${i}.png`), true);
}
await b.close();

// Each slide: background with a slow zoom (photo slides drift sideways too), text fades and slides up.
const FPS = 30, XF = 0.5;
const args = ['-y'];
slides.forEach((s, i) => args.push('-i', path.join(tmp, `b${i}.png`)));
slides.forEach((s, i) => args.push('-loop', '1', '-framerate', String(FPS), '-t', s.dur.toFixed(2), '-i', path.join(tmp, `t${i}.png`)));
const totalDur = slides.reduce((a, s) => a + s.dur, 0) - XF * (slides.length - 1);
args.push('-f', 'lavfi', '-t', totalDur.toFixed(2), '-i', 'anullsrc=channel_layout=stereo:sample_rate=44100');
const n = slides.length;
let fc = '';
slides.forEach((s, i) => {
  const d = Math.round(s.dur * FPS);
  const drift = !light && i < n - 1 ? (i % 2 ? `(iw-iw/zoom)*(1-on/${d})` : `(iw-iw/zoom)*(on/${d})`) : `iw/2-(iw/zoom/2)`;
  fc += `[${i}:v]scale=1296:2304,zoompan=z='1+0.10*on/${d}':d=${d}:x='${drift}':y='ih/2-(ih/zoom/2)':s=1080x1920:fps=${FPS},format=yuv420p,setsar=1[bg${i}];`;
  fc += `[${n + i}:v]format=rgba,fade=in:st=${(s.delay || 0.15).toFixed(2)}:d=0.55:alpha=1[tx${i}];`;
  fc += `[bg${i}][tx${i}]overlay=x=0:y='if(lt(t,${((s.delay || 0.15) + 0.55).toFixed(2)}),70*max(0,1-(t-${(s.delay || 0.15).toFixed(2)})/0.55),0)':shortest=1,format=yuv420p[v${i}];`;
});
let last = 'v0', t = slides[0].dur;
for (let i = 1; i < n; i++) {
  fc += `[${last}][v${i}]xfade=transition=${i === n - 1 ? 'fade' : 'smoothleft'}:duration=${XF}:offset=${(t - XF).toFixed(2)}[x${i}];`;
  last = `x${i}`; t = t - XF + slides[i].dur;
}
fc = fc.replace(/;$/, '');
const mp4 = path.join(OUT, `${id}.mp4`);
args.push('-filter_complex', fc, '-map', `[${last}]`, '-map', `${2 * n}:a`, '-shortest', '-c:v', 'libx264', '-preset', 'slow', '-crf', '30',
  '-pix_fmt', 'yuv420p', '-r', String(FPS), '-c:a', 'aac', '-b:a', '96k', '-movflags', '+faststart', mp4);
execFileSync('ffmpeg', args, { stdio: 'ignore' });
fs.rmSync(tmp, { recursive: true, force: true });

const url = `https://${SITE}/en/news/${meta.slug || id}/`;
const caption = [
  `${en.title}`, '', ...en.points.map(x => `・${x}`), '',
  vi ? `🇻🇳 ${vi.title}` : '', idn ? `🇮🇩 ${idn.title}` : '', easy ? `🇯🇵 ${easy.title}` : '', '',
  `Read in 5 languages: link in bio / ${SITE}`,
  credit ? credit : '',
  'Private information site, not a public office. For your own visa, ask immigration or a gyoseishoshi.', '',
  '#Toyama #富山 #LiveInJapan #WorkInJapan #外国人 #NguoiVietTaiNhat #OrangIndonesiaDiJepang #LiveWorkToyama',
].filter((l, i, a) => !(l === '' && a[i - 1] === '')).join('\n');
fs.writeFileSync(path.join(OUT, `${id}.txt`), caption + '\n');
const dur = execFileSync('ffprobe', ['-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', mp4]).toString().trim();
console.log(`made _reels/${id}.mp4 (${Number(dur).toFixed(1)} s, ${(fs.statSync(mp4).size / 1e6).toFixed(1)} MB) and _reels/${id}.txt`);
