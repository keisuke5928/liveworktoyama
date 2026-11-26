#!/usr/bin/env python3
"""Live & Work Toyama: build the static site from content/ into _site/.

Usage: python3 build.py
No external packages are needed (Python 3.9+).

Content layout
  content/site.json                 site settings (domain, GA4 ID, Search Console token)
  content/ui.json                   interface text for each language
  content/news/<id>/meta.json       date, category, region, image, sources, related guides
  content/news/<id>/<lang>.md       title, description, +++ short / +++ body / +++ meaning
  content/guides/<slug>/meta.json   order, last checked, pillar
  content/guides/<slug>/<lang>.md   title, description, body, +++ links
  content/pages-ja/<name>.html      Japanese-only pages (business, partners, about)
"""
import hashlib
import html
import json
import math
import re
import shutil
from pathlib import Path
from urllib.parse import quote

ROOT = Path(__file__).resolve().parent
C = ROOT / "content"
OUT = ROOT / "_site"
SITE = json.loads((C / "site.json").read_text(encoding="utf-8"))
UI = json.loads((C / "ui.json").read_text(encoding="utf-8"))
LANGS = SITE["langs"]
BASE = SITE["base_url"].rstrip("/")
CHAIN = {"en": ["en"], "easy": ["easy", "ja", "en"], "ja": ["ja", "en"], "vi": ["vi", "en"], "id": ["id", "en"]}
SCENE = (C / "scene.svg").read_text(encoding="utf-8")
esc = lambda s: html.escape(str(s), quote=True)


def t(lang, key, **kw):
    for l in CHAIN.get(lang, [lang, "en"]):
        if key in UI.get(l, {}):
            s = UI[l][key]
            return s.format(**kw) if kw else s
    raise KeyError(f"ui.json: missing '{key}'")


def pick(value, lang):
    """A value can be a plain string or {lang: string}."""
    if isinstance(value, dict):
        for l in CHAIN.get(lang, [lang, "en"]):
            if value.get(l):
                return value[l]
        return next(iter(value.values()))
    return value


# ---------------------------------------------------------------- markdown
def inline(s):
    s = html.escape(s, quote=False)
    s = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", s)

    def link(m):
        text, url = m.group(1), m.group(2)
        ext = ' target="_blank" rel="noopener"' if url.startswith("http") else ""
        return f'<a href="{url}"{ext}>{text}</a>'

    return re.sub(r"\[([^\]]+)\]\(([^)\s]+)\)", link, s)


def parse_blocks(text):
    """Very small Markdown subset: ## / ### headings, 1. lists, - lists, paragraphs."""
    blocks, para, lst = [], [], None

    def flush():
        nonlocal para, lst
        if para:
            blocks.append(("p", " ".join(para)))
            para = []
        if lst:
            blocks.append(lst)
            lst = None

    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            flush()
            continue
        m_ol, m_ul = re.match(r"^\d+\.\s+(.*)", line), re.match(r"^[-*]\s+(.*)", line)
        if line.startswith("### "):
            flush(); blocks.append(("h3", line[4:]))
        elif line.startswith("## "):
            flush(); blocks.append(("h2", line[3:]))
        elif m_ol or m_ul:
            kind = "ol" if m_ol else "ul"
            if para:
                blocks.append(("p", " ".join(para))); para = []
            if not lst or lst[0] != kind:
                if lst:
                    blocks.append(lst)
                lst = (kind, [])
            lst[1].append((m_ol or m_ul).group(1))
        else:
            if lst:
                blocks.append(lst); lst = None
            para.append(line)
    flush()
    return blocks


def render_blocks(blocks, h2_ids=False):
    out = []
    for i, (kind, val) in enumerate(blocks):
        if kind in ("ol", "ul"):
            out.append(f"<{kind}>" + "".join(f"<li>{inline(x)}</li>" for x in val) + f"</{kind}>")
        elif kind == "h2" and h2_ids:
            out.append(f'<h2 id="q{i}">{inline(val)}</h2>')
        else:
            out.append(f"<{kind}>{inline(val)}</{kind}>")
    return "\n".join(out)


def md(text):
    return render_blocks(parse_blocks(text))


def plain(s):
    s = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", s)
    return s.replace("**", "")


def faq_from_blocks(blocks):
    """Question headings (##) and the text under them, for FAQPage data."""
    faq, cur = [], None
    for kind, val in blocks:
        if kind == "h2":
            cur = {"q": plain(val), "a": []}
            faq.append(cur)
        elif cur is not None:
            cur["a"].extend(plain(x) for x in (val if kind in ("ol", "ul") else [val]))
    return [f for f in faq if f["a"] and f["q"].rstrip().endswith(("?", "？", "か"))]


def read_doc(path):
    """Front matter (key: value lines until ---), then sections split by '+++ name'."""
    text = path.read_text(encoding="utf-8")
    head, _, body = text.partition("\n---\n")
    meta = {}
    for line in head.splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            meta[k.strip()] = v.strip()
    sections, name, buf = {}, "body", []
    for line in body.splitlines():
        m = re.match(r"^\+\+\+\s*(\w+)\s*$", line)
        if m:
            sections[name] = "\n".join(buf).strip()
            name, buf = m.group(1), []
        else:
            buf.append(line)
    sections[name] = "\n".join(buf).strip()
    return meta, sections


def reading_minutes(text, lang):
    text = re.sub(r"<[^>]+>", "", text)
    if lang in ("ja", "easy"):
        n = len(re.sub(r"\s", "", text)) / 450
    else:
        n = len(text.split()) / 200
    return max(1, math.ceil(n))


def fmt_date(iso, lang):
    y, m, *rest = [int(x) for x in iso.split("-")]
    d = rest[0] if rest else None
    month = t(lang, "months")[m - 1]
    key = "date_format" if d else "month_format"
    return t(lang, key, y=y, m=m, d=d, month=month)


# ---------------------------------------------------------------- content
def load_guides():
    guides = []
    for d in sorted((C / "guides").iterdir()):
        if not d.is_dir():
            continue
        meta = json.loads((d / "meta.json").read_text(encoding="utf-8"))
        g = {"slug": d.name, **meta, "lang": {}}
        for lang in LANGS:
            f = d / f"{lang}.md"
            if f.exists():
                fm, sec = read_doc(f)
                g["lang"][lang] = {**fm, **sec}
        guides.append(g)
    return sorted(guides, key=lambda g: g.get("order", 99))


def load_news():
    news = []
    for d in sorted((C / "news").iterdir()):
        if not d.is_dir():
            continue
        meta = json.loads((d / "meta.json").read_text(encoding="utf-8"))
        n = {"slug": d.name, **meta, "lang": {}}
        for lang in LANGS:
            f = d / f"{lang}.md"
            if f.exists():
                fm, sec = read_doc(f)
                n["lang"][lang] = {**fm, **sec}
        news.append(n)
    return sorted(news, key=lambda n: (n["date"], n["slug"]), reverse=True)


GUIDES = load_guides()
NEWS = load_news()
GUIDE_BY_SLUG = {g["slug"]: g for g in GUIDES}

# ---------------------------------------------------------------- layout
GLOBE = '<svg viewBox="0 0 24 24" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="1.8"><circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3c2.5 2.6 3.8 5.6 3.8 9s-1.3 6.4-3.8 9c-2.5-2.6-3.8-5.6-3.8-9S9.5 5.6 12 3z"/></svg>'
CSS_V = hashlib.md5((ROOT / "static/assets/style.css").read_bytes()).hexdigest()[:8]
JS_V = hashlib.md5((ROOT / "static/assets/site.js").read_bytes()).hexdigest()[:8]
PAGES = []  # collected for the sitemap


def org_ld():
    return {
        "@type": "Organization",
        "@id": BASE + "/#org",
        "name": "Oiyo",
        "alternateName": "おいよ",
        "url": BASE + "/",
        "logo": {"@type": "ImageObject", "url": BASE + "/img/logo.png", "width": 512, "height": 512},
        "address": {"@type": "PostalAddress", "addressLocality": "Namerikawa", "addressRegion": "Toyama", "addressCountry": "JP"},
        "brand": {"@type": "Brand", "name": SITE["name"]},
    }


def crumbs_ld(items):
    return {
        "@context": "https://schema.org",
        "@type": "BreadcrumbList",
        "itemListElement": [
            {"@type": "ListItem", "position": i + 1, "name": name, "item": BASE + path}
            for i, (name, path) in enumerate(items)
        ],
    }


def crumbs_html(items, lang):
    lis = []
    for i, (name, path) in enumerate(items):
        if i == len(items) - 1:
            lis.append(f'<li aria-current="page">{esc(name)}</li>')
        else:
            lis.append(f'<li><a href="{path}">{esc(name)}</a></li>')
    return f'<nav class="crumbs" aria-label="{esc(t(lang, "breadcrumb"))}"><ol>{"".join(lis)}</ol></nav>'


def lang_switch(lang, alternates, ja_only=False):
    cur = "ja" if ja_only else lang
    items = []
    for l in LANGS:
        href = alternates.get(l) or f"/{l}/"
        current = ' aria-current="true"' if (l == cur and not ja_only) or (ja_only and l == "ja" and alternates.get("ja")) else ""
        items.append(
            f'<li><a href="{href}" lang="{UI[l]["html_lang"]}" hreflang="{UI[l]["hreflang"]}" data-lang="{l}"{current}>{esc(UI[l]["lang_name"])}</a></li>'
        )
    note = f'<li><p class="only">{esc(t("ja", "ja_only_note"))}</p></li>' if ja_only else ""
    label = UI[cur]["lang_name"]
    return (
        f'<details class="lang"><summary aria-label="{esc(t(cur, "language"))}: {esc(label)}">{GLOBE}<span class="full">{esc(label)}</span><span class="short">{esc(UI[cur]["lang_short"])}</span></summary>'
        f'<ul>{note}{"".join(items)}</ul></details>'
    )


def header(lang, section, alternates, ja_only=False):
    nl = "ja" if ja_only else lang
    links = [
        ("home", f"/{nl}/", t(nl, "nav_home")),
        ("news", f"/{nl}/news/", t(nl, "nav_news")),
        ("guides", f"/{nl}/guides/", t(nl, "nav_guides")),
        ("jobs", f"/{nl}/jobs/", t(nl, "nav_jobs")),
        ("students", f"/{nl}/students/", t(nl, "nav_students")),
    ]
    cur_attr = ' aria-current="page"'
    nav = "".join(
        f'<a href="{href}"{cur_attr if key == section else ""}>{esc(label)}</a>' for key, href, label in links
    )
    biz_cur = ' aria-current="page"' if section == "business" else ""
    nav += f'<a href="/business/" class="biz" lang="ja"{biz_cur}>企業のみなさまへ</a>'
    return (
        f'<a class="skip" href="#main">{esc(t(nl, "skip"))}</a>\n<header>\n  <div class="bar">\n'
        f'    <a class="logo" href="/{nl}/" lang="en">Live &amp; Work <b>Toyama</b><small lang="{UI[nl]["html_lang"]}">{esc(t(nl, "tagline"))}</small></a>\n'
        f'    <nav aria-label="{esc(t(nl, "nav_label"))}">{nav}</nav>\n'
        f"    {lang_switch(lang, alternates, ja_only)}\n  </div>\n</header>\n"
    )


def scene(lang, slim=False):
    s = SCENE.replace(
        'aria-label="Winter in Toyama: the Tateyama mountains over Toyama Bay and a snowy town"',
        f'aria-label="{esc(t(lang, "scene_alt"))}"',
    )
    return s.replace('class="scene"', 'class="scene slim"') if slim else s


def footer(lang):
    nl = "ja" if lang not in LANGS else lang
    return (
        '<footer class="band"><div class="wrap">\n'
        f'  <span>© Live &amp; Work Toyama by Oiyo · Toyama, Japan</span>\n'
        f'  <nav aria-label="Footer"><a href="/about/" lang="ja">About / 掲載方針</a><a href="/business/" lang="ja">企業のみなさまへ</a>'
        f'<a href="/partners/" lang="ja">学校・自治体のみなさまへ</a></nav>\n'
        f'  <p class="note" style="margin:0;flex-basis:100%">{esc(t(nl, "footer_note"))}</p>\n'
        "</div></footer>\n"
    )


def head(lang, title, desc, path, alternates, og_image=None, og_type="website", jsonld=(), xdefault=None, extra=""):
    html_lang = UI[lang]["html_lang"]
    url = BASE + path
    lines = [
        "<!DOCTYPE html>",
        f'<html lang="{html_lang}"{" class=\"easy\"" if lang == "easy" else ""}>',
        "<head>",
        '<meta charset="utf-8">',
        '<meta name="viewport" content="width=device-width, initial-scale=1">',
        f"<title>{esc(title)}</title>",
        f'<meta name="description" content="{esc(desc)}">',
        f'<link rel="canonical" href="{url}">',
    ]
    if len(alternates) > 1:
        for l in LANGS:
            if l in alternates:
                lines.append(f'<link rel="alternate" hreflang="{UI[l]["hreflang"]}" href="{BASE + alternates[l]}">')
        lines.append(f'<link rel="alternate" hreflang="x-default" href="{BASE + (xdefault or alternates.get("en", path))}">')
    img = BASE + (og_image or "/img/og-default.png")
    lines += [
        f'<meta property="og:site_name" content="{esc(SITE["name"])}">',
        f'<meta property="og:type" content="{og_type}">',
        f'<meta property="og:title" content="{esc(title)}">',
        f'<meta property="og:description" content="{esc(desc)}">',
        f'<meta property="og:url" content="{url}">',
        f'<meta property="og:image" content="{img}">',
        '<meta property="og:image:width" content="1200">',
        '<meta property="og:image:height" content="630">',
        f'<meta property="og:locale" content="{UI[lang]["og_locale"]}">',
    ]
    for l in alternates:
        if l != lang and UI[l]["og_locale"] != UI[lang]["og_locale"]:
            lines.append(f'<meta property="og:locale:alternate" content="{UI[l]["og_locale"]}">')
    lines += [
        '<meta name="twitter:card" content="summary_large_image">',
        '<meta name="theme-color" content="#1d5d86">',
        '<link rel="icon" href="/favicon.svg" type="image/svg+xml">',
        '<link rel="apple-touch-icon" href="/img/logo.png">',
        '<link rel="preconnect" href="https://fonts.googleapis.com">',
        '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>',
        '<link href="https://fonts.googleapis.com/css2?family=Zen+Kaku+Gothic+New:wght@400;500;700;900&display=swap" rel="stylesheet">',
    ]
    if lang == "vi":
        lines.append('<link href="https://fonts.googleapis.com/css2?family=Noto+Sans:wght@400;500;700;900&subset=vietnamese&display=swap" rel="stylesheet">')
    lines.append(f'<link rel="stylesheet" href="/assets/style.css?v={CSS_V}">')
    if SITE.get("gsc_verification"):
        lines.append(f'<meta name="google-site-verification" content="{esc(SITE["gsc_verification"])}">')
    if SITE.get("ga4_id"):
        gid = esc(SITE["ga4_id"])
        # Google tag as given by GA4 (GTM-... container id or G-... measurement id)
        loader = "gtm.js" if gid.startswith("GTM-") else "gtag/js"
        config = "" if gid.startswith("GTM-") else f"gtag('config','{gid}');"
        lines.append(
            f'<script async src="https://www.googletagmanager.com/{loader}?id={gid}"></script>\n'
            f"<script>window.dataLayer=window.dataLayer||[];function gtag(){{dataLayer.push(arguments);}}gtag('js',new Date());{config}</script>"
        )
    for ld in jsonld:
        data = json.dumps(ld, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
        lines.append(f'<script type="application/ld+json">{data}</script>')
    if extra:
        lines.append(extra)
    lines.append("</head>")
    return "\n".join(lines) + "\n"


def write(path, content):
    f = OUT / path.lstrip("/")
    if path.endswith("/"):
        f = f / "index.html"
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(content, encoding="utf-8")


def page(lang, path, title, desc, body, *, section=None, alternates=None, og_image=None, og_type="website",
         jsonld=(), slim=True, ja_only=False, xdefault=None, lastmod=None, sitemap=True):
    alternates = alternates or {lang: path}
    full_title = title if title.endswith(SITE["name"]) else f"{title} | {SITE['name']}"
    doc = head(lang, full_title, desc, path, alternates, og_image, og_type, jsonld, xdefault)
    doc += "<body>\n" + header(lang, section, alternates, ja_only)
    doc += scene(lang if not ja_only else "ja", slim) + "\n"
    doc += f'<main id="main">\n{body}\n</main>\n\n' + footer(lang)
    doc += f'<script src="/assets/site.js?v={JS_V}" defer></script>\n</body>\n</html>\n'
    write(path, doc)
    if sitemap:
        PAGES.append({"path": path, "alternates": alternates if len(alternates) > 1 else {}, "lastmod": lastmod or SITE["updated"],
                      "xdefault": xdefault})


def band(inner, cls="", narrow=False, top0=False):
    style = ' style="padding-top:0"' if top0 else ""
    c = f"band {cls}".strip()
    return f'<div class="{c}"{style}><div class="wrap{" narrow" if narrow else ""}">\n{inner}\n</div></div>'


def alts(fn):
    return {l: fn(l) for l in LANGS}


def bizlink(lang):
    return f'<p class="bizlink"><a href="/business/" lang="ja">{esc(t(lang, "bizlink"))}</a></p>'


# ---------------------------------------------------------------- pages
def news_title(n, lang):
    return pick({l: n["lang"][l]["title"] for l in n["lang"]}, lang)


def build_home(lang):
    path = f"/{lang}/"
    latest = "".join(
        f'<li><a href="/{lang}/news/{n["slug"]}/">{esc(news_title(n, lang))}</a></li>' for n in NEWS[:3]
    )
    featured = [GUIDE_BY_SLUG[s] for s in SITE["featured_guides"] if s in GUIDE_BY_SLUG]
    guides = "".join(
        f'<li><a href="/{lang}/guides/{g["slug"]}/">{esc(pick({l: g["lang"][l]["title"] for l in g["lang"]}, lang))}</a></li>'
        for g in featured
    )
    body = band(
        f'<h1>{esc(t(lang, "home_h1"))}</h1>\n<p class="lead">{esc(t(lang, "home_lead"))}</p>\n'
        f'<div class="btns"><a class="btn" href="/{lang}/guides/">{esc(t(lang, "nav_guides"))}</a>'
        f'<a class="btn" href="/{lang}/jobs/">{esc(t(lang, "nav_jobs"))}</a>'
        f'<a class="btn ghost" href="/{lang}/students/">{esc(t(lang, "btn_students"))}</a></div>'
    )
    if JOBS:
        items = "".join(f'<li><a href="/{lang}/jobs/#{esc(x["id"])}">{esc(pick(x["title"], lang))}</a> <span class="note">({esc(t(lang, "region_" + x["region"]))})</span></li>' for x in JOBS[:3])
        jobs_card = f'<div class="card"><h2>{esc(t(lang, "jobs_latest"))}</h2><ul>{items}</ul><a class="more" href="/{lang}/jobs/">{esc(t(lang, "jobs_count", n=len(JOBS)))}</a></div>\n'
    else:
        jobs_card = f'<div class="card"><h2>{esc(t(lang, "nav_jobs"))}</h2><p>{esc(t(lang, "home_jobs"))}</p><a class="more" href="/{lang}/jobs/">{esc(t(lang, "home_jobs_link"))}</a></div>\n'
    body += "\n" + band(
        f'<div class="card"><h2>{esc(t(lang, "home_news"))}</h2><ul>{latest}</ul><a class="more" href="/{lang}/news/">{esc(t(lang, "all_news"))}</a></div>\n'
        f'<div class="card"><h2>{esc(t(lang, "nav_guides"))}</h2><ul>{guides}</ul><a class="more" href="/{lang}/guides/">{esc(t(lang, "all_guides"))}</a></div>\n'
        f'{jobs_card}'
        f'<div class="card"><h2>{esc(t(lang, "home_help_h"))}</h2><p>{esc(t(lang, "home_help"))}</p><a class="more" href="/{lang}/guides/help-in-your-language/">{esc(t(lang, "home_help_link"))}</a></div>',
        cls="tint",
    ).replace('class="wrap"', 'class="wrap grid"', 1)
    body += "\n" + band(f'<div class="rule"><p>{esc(t(lang, "disclaimer"))}</p></div>')
    ld = [
        {"@context": "https://schema.org", **org_ld()},
        {
            "@context": "https://schema.org",
            "@type": "WebSite",
            "@id": BASE + "/#website",
            "name": SITE["name"],
            "alternateName": "liveworktoyama.com",
            "url": BASE + "/",
            "inLanguage": UI[lang]["hreflang"],
            "description": t(lang, "home_desc"),
            "publisher": {"@id": BASE + "/#org"},
        },
    ]
    page(lang, path, f'{SITE["name"]} | {t(lang, "tagline_short")}', t(lang, "home_desc"), body, section="home",
         alternates=alts(lambda l: f"/{l}/"), jsonld=ld, slim=False, xdefault="/")


def build_news_list(lang):
    path = f"/{lang}/news/"
    items = []
    for n in NEWS:
        d = n["lang"].get(lang) or n["lang"].get(CHAIN[lang][1] if len(CHAIN[lang]) > 1 else "en")
        url = f"/{lang}/news/{n['slug']}/"
        items.append(
            f'<article class="card newsitem"><a href="{url}" tabindex="-1" aria-hidden="true"><img class="thumb" src="{n["image"]}" width="1200" height="630" alt="" loading="lazy"></a>'
            f'<div><span class="tag">{esc(t(lang, "cat_" + n["category"]))}</span><span class="tag">{esc(t(lang, "region_" + n["region"]))}</span>'
            f'<h2><a href="{url}">{esc(d["title"])}</a></h2><p class="note"><time datetime="{n["date"]}">{fmt_date(n["date"], lang)}</time></p>'
            f'<p>{esc(d["description"])}</p></div></article>'
        )
    body = band(f'<h1>{esc(t(lang, "news_h1"))}</h1>\n<p class="lead">{esc(t(lang, "news_lead"))}</p>')
    body += "\n" + band(f'<div class="newslist">{"".join(items)}</div>', top0=True)
    crumbs = [(t(lang, "nav_home"), f"/{lang}/"), (t(lang, "nav_news"), path)]
    ld = [crumbs_ld(crumbs), {
        "@context": "https://schema.org", "@type": "CollectionPage", "name": t(lang, "news_h1"), "url": BASE + path,
        "inLanguage": UI[lang]["hreflang"],
        "hasPart": [{"@type": "NewsArticle", "headline": news_title(n, lang), "url": f"{BASE}/{lang}/news/{n['slug']}/", "datePublished": n["date"]} for n in NEWS],
    }]
    page(lang, path, t(lang, "news_h1"), t(lang, "news_lead"), body, section="news",
         alternates=alts(lambda l: f"/{l}/news/"), jsonld=ld, slim=False, lastmod=NEWS[0]["date"] if NEWS else None)


def build_news_article(n, lang):
    d = n["lang"][lang]
    path = f"/{lang}/news/{n['slug']}/"
    title = d["title"]
    crumbs = [(t(lang, "nav_home"), f"/{lang}/"), (t(lang, "nav_news"), f"/{lang}/news/"), (title, path)]
    body_html = md(d.get("body", ""))
    meaning_html = md(d.get("meaning", ""))
    minutes = reading_minutes(d.get("short", "") + body_html + meaning_html, lang)
    tags = (f'<a class="tag" href="/{lang}/news/">{esc(t(lang, "cat_" + n["category"]))}</a>'
            f'<span class="tag">{esc(t(lang, "region_" + n["region"]))}</span>')
    parts = [
        crumbs_html(crumbs, lang),
        f"<div>{tags}</div>",
        f"<h1>{esc(title)}</h1>",
        f'<p class="meta"><time datetime="{n["date"]}">{fmt_date(n["date"], lang)}</time> · {esc(t(lang, "read_time", n=minutes))}</p>',
        f'<figure class="hero"><img src="{n["image"]}" width="1200" height="630" alt="{esc(d.get("image_alt", title))}"></figure>',
        f'<section class="box short" aria-labelledby="h-short"><h2 id="h-short">{esc(t(lang, "in_short"))}</h2>{md(d.get("short", ""))}</section>',
        f'<div class="prose">{body_html}</div>',
        f'<section class="box meaning" aria-labelledby="h-mean"><h2 id="h-mean">{esc(t(lang, "meaning"))}</h2>{meaning_html}</section>',
    ]
    if lang != "easy" and n.get("easy_summary"):
        parts.append(
            f'<section class="box easysum" lang="ja" aria-labelledby="h-easy"><h2 id="h-easy">やさしい にほんごの まとめ</h2><p>{esc(n["easy_summary"])}</p>'
            f'<p class="note"><a href="/easy/news/{n["slug"]}/">やさしい にほんごで ぜんぶ よむ</a></p></section>'
        )
    src_items = []
    for s in n.get("sources", []):
        name = esc(pick(s["name"], lang))
        date = fmt_date(s["date"], lang) if s.get("date") else ""
        note = esc(pick(s["note"], lang)) if s.get("note") else ""
        bits = ", ".join(x for x in (name, date, note) if x)
        link = f' <a href="{esc(s["url"])}" target="_blank" rel="noopener">{esc(t(lang, "source_link"))}</a>' if s.get("url") else ""
        src_items.append(f"<li>{bits}{link}</li>")
    parts.append(f'<section class="src" aria-labelledby="h-src"><h2 id="h-src">{esc(t(lang, "sources"))}</h2><ul>{"".join(src_items)}</ul></section>')
    url = BASE + path
    share_text = quote(f"{title} {url}")
    parts.append(
        f'<section class="sect share" aria-labelledby="h-share"><h2 id="h-share">{esc(t(lang, "share"))}</h2><div class="btns">'
        f'<a class="btn sm" href="https://www.facebook.com/sharer/sharer.php?u={quote(url, safe="")}" target="_blank" rel="noopener">Facebook</a>'
        f'<a class="btn sm" href="https://wa.me/?text={share_text}" target="_blank" rel="noopener">WhatsApp</a>'
        f'<button class="btn sm ghost" type="button" data-copy="{url}" data-done="{esc(t(lang, "copied"))}" hidden>{esc(t(lang, "copy_link"))}</button>'
        "</div></section>"
    )
    rel = [GUIDE_BY_SLUG[s] for s in n.get("related", []) if s in GUIDE_BY_SLUG]
    rel_items = "".join(
        f'<li><a href="/{lang}/guides/{g["slug"]}/">{esc(pick({l: g["lang"][l]["title"] for l in g["lang"]}, lang))}</a></li>' for g in rel
    )
    for p in n.get("related_pages", []):
        rel_items += f'<li><a href="/{lang}/{p}/">{esc(t(lang, p + "_h1"))}</a></li>'
    if rel_items:
        parts.append(f'<section class="sect" aria-labelledby="h-rel"><h2 id="h-rel">{esc(t(lang, "related"))}</h2><ul>{rel_items}</ul></section>')
    parts.append(bizlink(lang))
    body = band("\n".join(parts), narrow=True)
    img = BASE + n["image"]
    ld = [
        {
            "@context": "https://schema.org",
            "@type": "NewsArticle",
            "headline": title[:110],
            "description": d["description"],
            "image": [img],
            "datePublished": n["date"] + "T09:00:00+09:00",
            "dateModified": n.get("updated", n["date"]) + "T09:00:00+09:00",
            "inLanguage": UI[lang]["hreflang"],
            "mainEntityOfPage": url,
            "url": url,
            "author": {"@type": "Organization", "name": "Oiyo", "url": BASE + "/about/"},
            "publisher": org_ld(),
            "articleSection": t(lang, "cat_" + n["category"]),
            "isBasedOn": [s["url"] for s in n.get("sources", []) if s.get("url")] or None,
        },
        crumbs_ld(crumbs),
    ]
    if not ld[0]["isBasedOn"]:
        del ld[0]["isBasedOn"]
    page(lang, path, title, d["description"], body, section="news",
         alternates={l: f"/{l}/news/{n['slug']}/" for l in n["lang"]}, og_image=n["image"], og_type="article",
         jsonld=ld, lastmod=n.get("updated", n["date"]))


def build_guides_list(lang):
    path = f"/{lang}/guides/"
    cards = []
    for g in GUIDES:
        d = g["lang"].get(lang)
        if not d:
            continue
        cards.append(
            f'<article class="card"><span class="tag">{esc(t(lang, "pillar_" + g["pillar"]))}</span><h2><a href="/{lang}/guides/{g["slug"]}/">{esc(d["title"])}</a></h2>'
            f'<p>{esc(d["description"])}</p><p class="note" style="margin:0">{esc(t(lang, "last_checked"))}: {fmt_date(g["checked"], lang)}</p></article>'
        )
    body = band(f'<h1>{esc(t(lang, "guides_h1"))}</h1>\n<p class="lead">{esc(t(lang, "guides_lead"))}</p>')
    body += "\n" + band("\n".join(cards), top0=True).replace('class="wrap"', 'class="wrap grid"', 1)
    crumbs = [(t(lang, "nav_home"), f"/{lang}/"), (t(lang, "nav_guides"), path)]
    ld = [crumbs_ld(crumbs), {
        "@context": "https://schema.org", "@type": "CollectionPage", "name": t(lang, "guides_h1"), "url": BASE + path,
        "inLanguage": UI[lang]["hreflang"],
        "hasPart": [{"@type": "Article", "headline": g["lang"][lang]["title"], "url": f"{BASE}/{lang}/guides/{g['slug']}/"} for g in GUIDES if lang in g["lang"]],
    }]
    page(lang, path, t(lang, "guides_h1"), t(lang, "guides_lead"), body, section="guides",
         alternates=alts(lambda l: f"/{l}/guides/"), jsonld=ld, slim=False)


def build_guide(g, lang):
    d = g["lang"][lang]
    path = f"/{lang}/guides/{g['slug']}/"
    title = d["title"]
    blocks = parse_blocks(d.get("body", ""))
    body_html = render_blocks(blocks, h2_ids=True)
    minutes = reading_minutes(body_html, lang)
    crumbs = [(t(lang, "nav_home"), f"/{lang}/"), (t(lang, "nav_guides"), f"/{lang}/guides/"), (title, path)]
    checked = fmt_date(g["checked"], lang)
    parts = [
        crumbs_html(crumbs, lang),
        f'<div><a class="tag" href="/{lang}/guides/">{esc(t(lang, "pillar_" + g["pillar"]))}</a></div>',
        f"<h1>{esc(title)}</h1>",
        f'<p class="meta">{esc(t(lang, "last_checked"))}: {checked} · {esc(t(lang, "read_time", n=minutes))}</p>',
        f'<div class="prose">{body_html}</div>',
    ]
    if d.get("links"):
        parts.append(f'<section class="src" aria-labelledby="h-links"><h2 id="h-links">{esc(t(lang, "official_links"))}</h2>{md(d["links"])}</section>')
    parts.append(f'<p class="upd">{esc(t(lang, "last_checked"))}: {checked}. {esc(t(lang, "rules_change"))}</p>')
    others = [x for x in GUIDES if x["slug"] != g["slug"] and lang in x["lang"]]
    idx = GUIDES.index(g)
    others = sorted(others, key=lambda x: (x["pillar"] != g["pillar"], (GUIDES.index(x) - idx) % len(GUIDES)))[:3]
    rel = "".join(f'<li><a href="/{lang}/guides/{x["slug"]}/">{esc(x["lang"][lang]["title"])}</a></li>' for x in others)
    parts.append(f'<section class="sect" aria-labelledby="h-rel"><h2 id="h-rel">{esc(t(lang, "more_guides"))}</h2><ul>{rel}</ul></section>')
    parts.append(bizlink(lang))
    body = band("\n".join(parts), narrow=True)
    url = BASE + path
    ld = [
        {
            "@context": "https://schema.org",
            "@type": "Article",
            "headline": title[:110],
            "description": d["description"],
            "inLanguage": UI[lang]["hreflang"],
            "url": url,
            "mainEntityOfPage": url,
            "dateModified": g["checked"] if len(g["checked"]) > 7 else g["checked"] + "-01",
            "image": [BASE + "/img/og-guides.png"],
            "author": {"@type": "Organization", "name": "Oiyo", "url": BASE + "/about/"},
            "publisher": org_ld(),
        },
        crumbs_ld(crumbs),
    ]
    faq = faq_from_blocks(blocks)
    if faq:
        ld.append({
            "@context": "https://schema.org",
            "@type": "FAQPage",
            "inLanguage": UI[lang]["hreflang"],
            "mainEntity": [{"@type": "Question", "name": f["q"], "acceptedAnswer": {"@type": "Answer", "text": " ".join(f["a"])}} for f in faq],
        })
    page(lang, path, title, d["description"], body, section="guides",
         alternates={l: f"/{l}/guides/{g['slug']}/" for l in g["lang"]}, og_image="/img/og-guides.png", og_type="article",
         jsonld=ld, lastmod=g["checked"] if len(g["checked"]) > 7 else None)


JOB_MAX_AGE_DAYS = 14  # a listing not re-checked for this many days is hidden automatically


def load_jobs():
    import datetime
    today = datetime.date.fromisoformat(SITE["updated"]) if SITE.get("updated") else datetime.date.today()
    today = max(today, datetime.date.today())
    jobs = []
    d = C / "jobs"
    if not d.exists():
        return jobs
    for f in sorted(d.glob("*.json")):
        j = json.loads(f.read_text(encoding="utf-8"))
        j["id"] = f.stem
        if j.get("status") != "open":
            continue
        age = (today - datetime.date.fromisoformat(j["checked"])).days
        if age > JOB_MAX_AGE_DAYS:
            continue
        jobs.append(j)
    return sorted(jobs, key=lambda j: (j.get("first_listed", j["checked"]), j["id"]), reverse=True)


JOBS = load_jobs()


def fmt_yen(n):
    return "¥{:,}".format(int(n))


def job_pay(j, lang):
    p = j.get("pay") or {}
    if not p.get("min") and not p.get("max"):
        return t(lang, "pay_unknown")
    if p.get("min") and p.get("max"):
        x = t(lang, "pay_range", a=fmt_yen(p["min"]), b=fmt_yen(p["max"]))
    else:
        x = t(lang, "pay_from", a=fmt_yen(p.get("min") or p.get("max")))
    return t(lang, "pay_" + p.get("per", "month"), x=x)


def job_card(j, lang):
    title = pick(j["title"], lang)
    tags = [t(lang, "job_cat_" + j.get("category", "other")), t(lang, "region_" + j["region"])]
    tags.append(t(lang, "emp_" + j.get("employment", "full_time")))
    if j.get("housing") == "dorm":
        tags.append(t(lang, "housing_dorm"))
    if j.get("students_ok"):
        tags.append(t(lang, "job_students"))
    tag_html = "".join(f'<span class="tag">{esc(x)}</span>' for x in tags)
    paid = f'<span class="sample">{esc(t(lang, "job_paid"))}</span>' if j.get("paid") else ""
    rows = [
        (t(lang, "job_employer"), esc(pick(j["employer"], lang))),
        (t(lang, "job_pay"), esc(job_pay(j, lang))),
    ]
    if j.get("hours"):
        rows.append((t(lang, "job_hours"), esc(pick(j["hours"], lang))))
    rows.append((t(lang, "job_japanese"), esc(t(lang, "jp_" + j.get("japanese", "unknown")))))
    rows.append((t(lang, "job_housing"), esc(t(lang, "housing_" + j.get("housing", "unknown")))))
    if j.get("visa"):
        rows.append((t(lang, "job_visa"), esc(pick(j["visa"], lang))))
    rows.append((t(lang, "job_welcome"), esc(pick(j["foreign_welcome"], lang))))
    src = esc(pick(j["source_name"], lang))
    rows.append((t(lang, "job_checked"), f'{fmt_date(j["checked"], lang)} · {esc(t(lang, "job_source"))}: {src}'))
    dl = "".join(f"<dt>{esc(k)}</dt><dd>{v}</dd>" for k, v in rows)
    summary = f'<p>{esc(pick(j["summary"], lang))}</p>' if j.get("summary") else ""
    return (
        f'<article class="card job" id="{esc(j["id"])}">{tag_html}<h2>{esc(title)}</h2>{paid}{summary}<dl>{dl}</dl>'
        f'<div class="btns"><a class="btn sm" href="{esc(j["source_url"])}" target="_blank" rel="noopener nofollow">{esc(t(lang, "job_apply"))}</a></div></article>'
    )


def build_jobs(lang):
    path = f"/{lang}/jobs/"
    body = band(f'<h1>{esc(t(lang, "jobs_h1"))}</h1>\n<p class="lead">{esc(t(lang, "jobs_lead"))}</p>')
    if JOBS:
        inner = f'<p class="note">{esc(t(lang, "jobs_count", n=len(JOBS)))}</p><div class="newslist">' + "".join(job_card(j, lang) for j in JOBS) + "</div>"
    else:
        inner = f'<div class="card"><p style="margin:0">{esc(t(lang, "jobs_none"))}</p></div>'
    body += "\n" + band(inner, cls="tint")
    body += "\n" + band(
        f'<div class="rule"><p><b>{esc(t(lang, "jobs_note_h"))}</b> {esc(t(lang, "jobs_note"))}</p></div>'
        f'<div class="sect"><h2>{esc(t(lang, "jobs_how_h"))}</h2><ol>' + "".join(f"<li>{esc(x)}</li>" for x in t(lang, "jobs_how")) + "</ol></div>"
    )
    crumbs = [(t(lang, "nav_home"), f"/{lang}/"), (t(lang, "nav_jobs"), path)]
    last = max([j["checked"] for j in JOBS], default=None)
    page(lang, path, t(lang, "jobs_h1"), t(lang, "jobs_desc"), body, section="jobs",
         alternates=alts(lambda l: f"/{l}/jobs/"), jsonld=[crumbs_ld(crumbs)], slim=False, lastmod=last)


def build_students(lang):
    path = f"/{lang}/students/"
    cards, faq = [], []
    for c in t(lang, "students_cards"):
        lst = "".join(f"<li>{inline(x)}</li>" for x in c.get("items", []))
        lst = f"<ol>{lst}</ol>" if lst else ""
        p = f"<p>{inline(c['text'])}</p>" if c.get("text") else ""
        note = f'<p class="note">{esc(c["note"])}</p>' if c.get("note") else ""
        link = f'<a href="/{lang}/{c["link"]}/">{esc(c["link_text"])}</a>' if c.get("link") else ""
        cards.append(f'<div class="card"><h2>{esc(c["h"])}</h2>{p}{lst}{note}{link}</div>')
        faq.append({"@type": "Question", "name": c["h"], "acceptedAnswer": {"@type": "Answer", "text": " ".join(
            [plain(c.get("text", ""))] + [plain(x) for x in c.get("items", [])] + [c.get("note", "")]).strip()}})
    body = band(f'<h1>{esc(t(lang, "students_h1"))}</h1>\n<p class="lead">{esc(t(lang, "students_lead"))}</p>')
    body += "\n" + band("\n".join(cards), top0=True).replace('class="wrap"', 'class="wrap grid"', 1)
    body += "\n" + band(f'<div class="rule"><p>{esc(t(lang, "students_rule"))}</p></div>')
    crumbs = [(t(lang, "nav_home"), f"/{lang}/"), (t(lang, "nav_students"), path)]
    ld = [crumbs_ld(crumbs), {"@context": "https://schema.org", "@type": "FAQPage", "inLanguage": UI[lang]["hreflang"], "mainEntity": faq}]
    page(lang, path, t(lang, "students_h1"), t(lang, "students_desc"), body, section="students",
         alternates=alts(lambda l: f"/{l}/students/"), jsonld=ld, slim=False)


def build_ja_page(name, section):
    meta, sec = read_doc(C / "pages-ja" / f"{name}.html")
    path = f"/{name}/"
    body = sec["body"]
    crumbs = [("ホーム", "/ja/"), (meta["crumb"], path)]
    ld = [crumbs_ld(crumbs)]
    qa = re.findall(r"<details><summary>(.+?)</summary><div>(.+?)</div></details>", body, re.S)
    if qa:
        ld.append({"@context": "https://schema.org", "@type": "FAQPage", "inLanguage": "ja",
                   "mainEntity": [{"@type": "Question", "name": q, "acceptedAnswer": {"@type": "Answer", "text": re.sub(r"<[^>]+>", "", a).strip()}} for q, a in qa]})
    if name in ("about", "business"):
        ld.append({"@context": "https://schema.org", **org_ld(), "founder": {"@type": "Person", "name": "吉田 圭佑", "alternateName": "Keisuke Yoshida"}})
    body = body.replace("<!--CRUMBS-->", crumbs_html(crumbs, "ja"))
    page("ja", path, meta["title"], meta["description"], body, section=section, ja_only=True, jsonld=ld, slim=False,
         alternates={"ja": path})


def build_root():
    links = "".join(
        f'<li><a class="btn{" ghost" if l != "en" else ""}" href="/{l}/" lang="{UI[l]["html_lang"]}" hreflang="{UI[l]["hreflang"]}" data-lang="{l}">{esc(UI[l]["lang_name"])}</a></li>'
        for l in LANGS
    )
    redirect = (
        "<script>(function(){var L=" + json.dumps(LANGS) + ",l=null;try{l=localStorage.getItem('lwt-lang')}catch(e){}"
        "if(L.indexOf(l)<0){l='en';var n=navigator.languages||[navigator.language||''];"
        "for(var i=0;i<n.length;i++){var c=String(n[i]).toLowerCase().slice(0,2);"
        "if(c==='en'){l='en';break}if(c==='ja'){l='ja';break}if(c==='vi'){l='vi';break}if(c==='id'||c==='ms'){l='id';break}}}"
        "location.replace('/'+l+'/'+location.search);})();</script>"
    )
    alternates = alts(lambda l: f"/{l}/")
    doc = head("en", f'{SITE["name"]} | Jobs and daily life in Toyama', t("en", "home_desc"), "/", alternates,
               jsonld=[{"@context": "https://schema.org", **org_ld()}], xdefault="/", extra=redirect)
    doc += "<body>\n" + header("en", "home", alternates) + scene("en") + "\n"
    doc += '<main id="main">' + band(
        '<h1>Live and work in Toyama</h1><p class="lead">Choose your language. / ことばを えらんで ください。 / 言語を選んでください。 / Chọn ngôn ngữ. / Pilih bahasa.</p>'
        f'<ul class="langs">{links}</ul>'
    ) + "</main>\n" + footer("en")
    doc += f'<script src="/assets/site.js?v={JS_V}" defer></script>\n</body>\n</html>\n'
    write("/", doc)
    PAGES.append({"path": "/", "alternates": alternates, "lastmod": SITE["updated"], "xdefault": "/"})


def build_404():
    links = "".join(f'<li><a href="/{l}/" lang="{UI[l]["html_lang"]}">{esc(UI[l]["lang_name"])}</a> — {esc(t(l, "not_found"))}</li>' for l in LANGS)
    doc = head("en", f"404 | {SITE['name']}", "Page not found.", "/404.html", {"en": "/404.html"})
    doc = doc.replace("</head>", '<meta name="robots" content="noindex">\n</head>')
    doc += "<body>\n" + header("en", None, {}) + scene("en", slim=True)
    doc += '<main id="main">' + band(f"<h1>404</h1><ul>{links}</ul>") + "</main>\n" + footer("en")
    doc += f'<script src="/assets/site.js?v={JS_V}" defer></script>\n</body>\n</html>\n'
    (OUT / "404.html").write_text(doc, encoding="utf-8")


def build_sitemap():
    lines = ['<?xml version="1.0" encoding="UTF-8"?>',
             '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" xmlns:xhtml="http://www.w3.org/1999/xhtml">']
    for p in PAGES:
        lines.append(f"  <url><loc>{BASE + p['path']}</loc><lastmod>{p['lastmod']}</lastmod>")
        if p["alternates"]:
            for l in LANGS:
                if l in p["alternates"]:
                    lines.append(f'    <xhtml:link rel="alternate" hreflang="{UI[l]["hreflang"]}" href="{BASE + p["alternates"][l]}"/>')
            xd = p.get("xdefault") or p["alternates"].get("en")
            lines.append(f'    <xhtml:link rel="alternate" hreflang="x-default" href="{BASE + xd}"/>')
        lines.append("  </url>")
    lines.append("</urlset>")
    (OUT / "sitemap.xml").write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_robots():
    bots = ["GPTBot", "OAI-SearchBot", "ChatGPT-User", "ClaudeBot", "Claude-User", "Claude-SearchBot", "anthropic-ai",
            "PerplexityBot", "Perplexity-User", "Google-Extended", "Applebot-Extended", "Bingbot", "Googlebot",
            "CCBot", "Meta-ExternalAgent", "DuckAssistBot", "MistralAI-User", "cohere-ai"]
    lines = ["# Live & Work Toyama — search engines and AI assistants are welcome.", "User-agent: *", "Allow: /", ""]
    for b in bots:
        lines += [f"User-agent: {b}", "Allow: /", ""]
    lines += [f"Sitemap: {BASE}/sitemap.xml"]
    (OUT / "robots.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_llms():
    L = [
        f"# {SITE['name']}",
        "",
        "> Practical news and guides for foreign residents who live and work in Toyama Prefecture, Japan, and for people who want to move there. "
        "Written in plain English, easy Japanese (yasashii nihongo), Japanese, Vietnamese and Indonesian. Run by Oiyo, a small business in Namerikawa, Toyama.",
        "",
        "Important notes:",
        "- This is a private media site. It is not an official website of Toyama Prefecture or any public office.",
        "- It lists job postings (job listings) but does not introduce job seekers to employers or handle applications. Readers apply on the employer's own page.",
        "- It does not give individual visa advice. Readers should ask the Immigration Services Agency or a gyoseishoshi (licensed administrative scrivener).",
        "- Each news article cites its sources with date and link. Each guide shows official links and the date it was last checked.",
        "",
        "Languages: English /en/, Easy Japanese /easy/, Japanese /ja/, Vietnamese /vi/, Indonesian /id/. The same slug is used in every language.",
        "",
        "## Main pages (English)",
        f"- [Home]({BASE}/en/): latest news, guides, job listings, where to get help",
        f"- [News]({BASE}/en/news/): short news for residents of Toyama",
        f"- [Life guides]({BASE}/en/guides/): daily life and work in Toyama",
        f"- [Job listings]({BASE}/en/jobs/): how job listings work",
        f"- [International students]({BASE}/en/students/): part-time work rules (28 hours a week, 8 hours a day in long holidays)",
        "",
        "## Life guides (English)",
    ]
    for g in GUIDES:
        if "en" in g["lang"]:
            L.append(f"- [{g['lang']['en']['title']}]({BASE}/en/guides/{g['slug']}/): {g['lang']['en']['description']}")
    L += ["", "## Latest news (English)"]
    for n in NEWS[:20]:
        if "en" in n["lang"]:
            L.append(f"- [{n['lang']['en']['title']}]({BASE}/en/news/{n['slug']}/) ({n['date']}): {n['lang']['en']['description']}")
    L += [
        "",
        "## For employers and partners (Japanese)",
        f"- [企業のみなさまへ]({BASE}/business/): recruitment support for employers in Toyama who want to hire foreign staff (job pages in several languages, ads, interpreting). Not a job placement agency.",
        f"- [学校・自治体のみなさまへ]({BASE}/partners/): for Japanese language schools and local governments",
        f"- [About / 掲載方針]({BASE}/about/): operator and listing policy",
        "",
        f"Sitemap: {BASE}/sitemap.xml",
    ]
    (OUT / "llms.txt").write_text("\n".join(L) + "\n", encoding="utf-8")


def main():
    if OUT.exists():
        shutil.rmtree(OUT)
    shutil.copytree(ROOT / "static", OUT)
    for lang in LANGS:
        build_home(lang)
        build_news_list(lang)
        for n in NEWS:
            if lang in n["lang"]:
                build_news_article(n, lang)
        build_guides_list(lang)
        for g in GUIDES:
            if lang in g["lang"]:
                build_guide(g, lang)
        build_jobs(lang)
        build_students(lang)
    build_ja_page("business", "business")
    build_ja_page("partners", "business")
    build_ja_page("about", None)
    build_root()
    build_404()
    build_sitemap()
    build_robots()
    build_llms()
    (OUT / "CNAME").write_text(SITE["domain"] + "\n", encoding="utf-8")
    (OUT / ".nojekyll").write_text("", encoding="utf-8")
    print(f"Built {len(PAGES)} pages into {OUT.relative_to(ROOT)}/")


if __name__ == "__main__":
    main()
