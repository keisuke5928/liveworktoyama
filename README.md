# Live & Work Toyama

Jobs and daily life in Toyama — https://liveworktoyama.com (by Oiyo)

Static site in 5 languages: English `/en/`, やさしいにほんご `/easy/`, 日本語 `/ja/`, Tiếng Việt `/vi/`, Bahasa Indonesia `/id/`.
Japanese-only pages: `/business/`, `/partners/`, `/about/`.

## Build

```bash
python3 build.py          # writes everything to _site/ (no packages needed)
cd _site && python3 -m http.server 8000   # preview at http://localhost:8000
```

Pushing to `main` builds and publishes to GitHub Pages (`.github/workflows/pages.yml`).

## Where things are

| What | File |
|---|---|
| Domain, GA4 ID, Search Console token, featured guides | `content/site.json` |
| Menu and page text for each language | `content/ui.json` |
| News article | `content/news/<date>-<slug>/meta.json` + `en.md` `easy.md` `ja.md` `vi.md` `id.md` |
| Life guide | `content/guides/<slug>/meta.json` + one `.md` per language |
| Business / partners / about (Japanese) | `content/pages-ja/*.html` |
| Design (CSS, JS, icons, images) | `static/` |
| Template images (news, OGP, logo) | `node tools/make-images.mjs` |

### Adding a news article

1. Copy a folder in `content/news/` and rename it `YYYY-MM-DD-short-slug`.
2. Edit `meta.json`: `date`, `category` (rules / news / life / work / outings), `region` (japan / toyama / uozu — add new ones to `ui.json` as `region_<name>`), `sources`, `related` guides, `easy_summary`, `scene`, `og_title`, `og_sub`.
3. Write each language file: front matter (`title`, `description`, `image_alt`), then `+++ short` (3 lines), `+++ body`, `+++ meaning`.
4. Run `node tools/make-images.mjs` to make the image, then `python3 build.py && python3 tools/check.py`.

Markdown supported: `## heading`, `1.` lists, `-` lists, paragraphs, `**bold**`, `[text](url)`.
Guide headings should be questions (they become FAQ structured data).

Generated automatically: title/description, canonical, hreflang, OGP, JSON-LD (NewsArticle, Article, FAQPage, Organization, WebSite, BreadcrumbList), `sitemap.xml`, `robots.txt`, `llms.txt`, `CNAME`, `404.html`.
