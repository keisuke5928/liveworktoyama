#!/usr/bin/env python3
"""Make the data files for the owner's dashboard (claude.ai artifact "LWT ダッシュボード").

  python3 tools/dashboard_data.py        # writes _dashboard/*.json (not committed)

Each file is {"rows": [...], "meta": [...]} for one dataset of the dashboard. Sources:
docs/metrics/latest.json (GA4 + Search Console, aggregated numbers only), content/ (articles,
guides, jobs, companies) and content/social/ (posts). Instagram links are read from the Graph API
(the token is added by the network proxy). No personal data.
"""
import collections
import json
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "_dashboard"
C = ROOT / "content"


def save(name, rows, note):
    OUT.mkdir(exist_ok=True)
    (OUT / f"{name}.json").write_text(json.dumps({"rows": rows, "meta": [{"label": "Made by", "value": "tools/dashboard_data.py"},
                                                                          {"label": "Note", "value": note}]},
                                                 ensure_ascii=False, indent=0) + "\n", encoding="utf-8")


def main():
    m = json.loads((ROOT / "docs/metrics/latest.json").read_text(encoding="utf-8"))
    gen = m["generated"]
    src = f"docs/metrics/latest.json ({gen}), GA4 and Search Console"
    # 1. totals for 7 and 28 days
    rows = []
    for key, label in (("last7d", "7日"), ("last28d", "28日")):
        t = m[key]["totals"][0] if isinstance(m[key]["totals"], list) and m[key]["totals"] else {}
        rows.append({"period": label, "users": t.get("activeUsers", 0), "new_users": t.get("newUsers", 0), "sessions": t.get("sessions", 0),
                     "pageviews": t.get("screenPageViews", 0), "engagement_rate": t.get("engagementRate", 0),
                     "avg_session_sec": round(t.get("averageSessionDuration", 0))})
    save("traffic", rows, src)
    # 2. daily trend
    daily = m.get("daily") if isinstance(m.get("daily"), list) else []
    save("daily", [{"date": r["date"], "users": r["activeUsers"], "sessions": r["sessions"], "pageviews": r["screenPageViews"]} for r in daily], src)
    r28 = m["last28d"]
    # 3. pages
    save("pages", [{"page": p["pagePath"], "views": p["screenPageViews"], "users": p["activeUsers"], "engagement_rate": p["engagementRate"]}
                   for p in (r28["pages"] if isinstance(r28["pages"], list) else [])[:20]], src + " (last 28 days)")
    # 4. language, channels, devices, countries
    save("languages", sorted([{"language": k, "views": v} for k, v in r28.get("views_by_language", {}).items()], key=lambda x: -x["views"]), src + " (last 28 days, by URL)")
    save("channels", [{"channel": c["sessionDefaultChannelGroup"], "sessions": c["sessions"], "engagement_rate": c["engagementRate"]}
                      for c in r28["channels"]] if isinstance(r28["channels"], list) else [], src + " (last 28 days)")
    save("devices", [{"device": c["deviceCategory"], "sessions": c["sessions"]} for c in r28["devices"]] if isinstance(r28["devices"], list) else [], src + " (last 28 days)")
    save("countries", [{"country": c["country"], "users": c["activeUsers"]} for c in r28["countries"][:10]] if isinstance(r28["countries"], list) else [], src + " (last 28 days)")
    # 5. events that matter for the business
    ev = {e["eventName"]: e["eventCount"] for e in r28["events"]} if isinstance(r28["events"], list) else {}
    ev7 = {e["eventName"]: e["eventCount"] for e in m["last7d"]["events"]} if isinstance(m["last7d"]["events"], list) else {}
    names = [("apply_click", "求人の応募ボタン"), ("cta_click", "企業向け・SNS などのボタン"), ("page_view", "ページの表示")]
    save("events", [{"event": n, "label": l, "count_7d": ev7.get(n, 0), "count_28d": ev.get(n, 0)} for n, l in names], src)
    # 6. search
    q = r28["search_queries"] if isinstance(r28["search_queries"], list) else []
    save("search", [{"query": x["query"], "clicks": x["clicks"], "impressions": x["impressions"], "ctr": x["ctr"], "position": x["position"]} for x in q[:30]],
         "Search Console via " + src + " (28 days, 2-3 days late)")
    # 7. content and jobs
    cats = collections.Counter()
    for d in (C / "news").iterdir():
        if (d / "meta.json").exists():
            cats[json.loads((d / "meta.json").read_text(encoding="utf-8")).get("category", "news")] += 1
    jg = json.loads((C / "jobs_auto/jobsgo.json").read_text(encoding="utf-8"))
    jobs = jg["jobs"] if isinstance(jg, dict) else jg
    comps = json.loads((C / "jobs_auto/companies.json").read_text(encoding="utf-8"))
    label = {"outings": "記事：おでかけ", "rules": "記事：制度", "work": "記事：仕事", "life": "記事：生活", "news": "記事：ニュース"}
    rows = [{"item": label.get(k, "記事：" + k), "count": v} for k, v in sorted(cats.items())]
    rows += [{"item": "ガイド", "count": sum(1 for d in (C / "guides").iterdir() if d.is_dir())},
             {"item": "求人（自動収集）", "count": len(jobs)},
             {"item": "求人：企業の採用ページあり", "count": sum(1 for j in jobs if j.get("official_url"))},
             {"item": "企業", "count": len(comps)},
             {"item": "注目の求人", "count": sum(1 for f in (C / "jobs").glob("2*.json") if json.loads(f.read_text(encoding="utf-8")).get("status") == "open")}]
    save("content", rows, "content/ in the site repository")
    # 8. social posts
    posts = []
    fb = json.loads((C / "social/facebook.json").read_text(encoding="utf-8"))
    ig = json.loads((C / "social/instagram.json").read_text(encoding="utf-8"))
    for art, pid in fb.items():
        if not str(pid).startswith("skipped"):
            posts.append({"article": art[11:], "date": art[:10], "platform": "Facebook", "url": f"https://www.facebook.com/{pid}"})
    for art, mid in ig.items():
        if str(mid).startswith("skipped"):
            continue
        url = ""
        try:
            req = urllib.request.Request(f"https://graph.facebook.com/v27.0/{mid}?fields=permalink", headers={"Authorization": "Bearer placeholder"})
            url = json.loads(urllib.request.urlopen(req, timeout=30).read()).get("permalink", "")
        except Exception:
            pass
        posts.append({"article": art[11:], "date": art[:10], "platform": "Instagram", "url": url})
    save("social", sorted(posts, key=lambda p: (p["date"], p["platform"]), reverse=True), "content/social/ (posted by the site's tools)")
    # one file with every dataset, for upload to the dashboard (each dataset's loader picks its part)
    allf = {"generated": gen}
    for f in sorted(OUT.glob("*.json")):
        if f.name != "lwt-dashboard.json":
            allf[f.stem] = json.loads(f.read_text(encoding="utf-8"))["rows"]
    (OUT / "lwt-dashboard.json").write_text(json.dumps(allf, ensure_ascii=False) + "\n", encoding="utf-8")
    print("wrote", ", ".join(sorted(f.name for f in OUT.glob("*.json"))), "| metrics", gen)


if __name__ == "__main__":
    main()
