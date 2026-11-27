#!/usr/bin/env python3
"""Fetch site data from GA4 and Search Console and save a small summary for the automatic review.

Runs in GitHub Actions (.github/workflows/metrics.yml) with a Google service account.
Only aggregated numbers are saved (pages, languages, devices, countries, search queries).
No personal data is collected or stored.

Environment:
  GA_SA_KEY         service account key (JSON text)
  GA4_PROPERTY_ID   numeric GA4 property ID (GA4 > Admin > Property details)
  GSC_SITE          Search Console property, default "sc-domain:liveworktoyama.com"

Output: docs/metrics/latest.json and docs/metrics/history/YYYY-MM-DD.json (Mondays)
"""
import datetime
import json
import os
import sys
from pathlib import Path
from urllib.parse import quote

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "docs/metrics"
LANGS = ["en", "easy", "ja", "vi", "id"]


def session():
    from google.oauth2 import service_account
    from google.auth.transport.requests import AuthorizedSession
    info = json.loads(os.environ["GA_SA_KEY"])
    creds = service_account.Credentials.from_service_account_info(info, scopes=[
        "https://www.googleapis.com/auth/analytics.readonly",
        "https://www.googleapis.com/auth/webmasters.readonly"])
    return AuthorizedSession(creds)


def ga(s, prop, days, dims, mets, limit=50, flt=None, order=None):
    body = {"dateRanges": [{"startDate": f"{days}daysAgo", "endDate": "yesterday"}],
            "dimensions": [{"name": d} for d in dims], "metrics": [{"name": m} for m in mets], "limit": limit}
    if flt:
        body["dimensionFilter"] = flt
    body["orderBys"] = [order or {"metric": {"metricName": mets[0]}, "desc": True}]
    r = s.post(f"https://analyticsdata.googleapis.com/v1beta/properties/{prop}:runReport", json=body, timeout=60)
    if r.status_code != 200:
        return {"error": r.text[:300]}
    rows = []
    for row in r.json().get("rows", []):
        d = {k: v["value"] for k, v in zip(dims, row.get("dimensionValues", []))}
        for k, v in zip(mets, row.get("metricValues", [])):
            x = float(v["value"])
            d[k] = round(x, 4) if not x.is_integer() else int(x)
        rows.append(d)
    return rows


def gsc(s, site, days, dims, limit=100):
    end = datetime.date.today() - datetime.timedelta(days=3)  # Search Console data is 2–3 days late
    start = end - datetime.timedelta(days=days - 1)
    body = {"startDate": start.isoformat(), "endDate": end.isoformat(), "dimensions": dims, "rowLimit": limit}
    r = s.post(f"https://www.googleapis.com/webmasters/v3/sites/{quote(site, safe='')}/searchAnalytics/query", json=body, timeout=60)
    if r.status_code != 200:
        return {"error": r.text[:300]}
    return [{**{d: k for d, k in zip(dims, row["keys"])}, "clicks": row["clicks"], "impressions": row["impressions"],
             "ctr": round(row["ctr"], 4), "position": round(row["position"], 1)} for row in r.json().get("rows", [])]


def lang_of(path):
    seg = (path or "/").strip("/").split("/")[0]
    return seg if seg in LANGS else ("ja-only" if seg in ("business", "partners", "about") else "other")


def main():
    if not os.environ.get("GA_SA_KEY") or not os.environ.get("GA4_PROPERTY_ID"):
        print("GA_SA_KEY / GA4_PROPERTY_ID are not set; nothing to do.")
        return 0
    s = session()
    prop = os.environ["GA4_PROPERTY_ID"].strip()
    site = os.environ.get("GSC_SITE", "sc-domain:liveworktoyama.com")
    out = {"generated": datetime.date.today().isoformat(), "note": "Aggregated numbers only. No personal data."}
    for days in (7, 28):
        k = f"last{days}d"
        r = {}
        r["totals"] = ga(s, prop, days, [], ["activeUsers", "newUsers", "sessions", "screenPageViews", "engagementRate", "averageSessionDuration"], limit=1,
                         order={"metric": {"metricName": "sessions"}, "desc": True})
        pages = ga(s, prop, days, ["pagePath"], ["screenPageViews", "activeUsers", "userEngagementDuration", "engagementRate"], limit=200)
        r["pages"] = pages[:60] if isinstance(pages, list) else pages
        if isinstance(pages, list):
            by = {}
            for p in pages:
                l = lang_of(p["pagePath"])
                by[l] = by.get(l, 0) + p["screenPageViews"]
            r["views_by_language"] = by
        r["landing_pages"] = ga(s, prop, days, ["landingPage"], ["sessions", "engagementRate", "averageSessionDuration"], limit=40)
        r["channels"] = ga(s, prop, days, ["sessionDefaultChannelGroup"], ["sessions", "engagementRate"], limit=20)
        r["devices"] = ga(s, prop, days, ["deviceCategory"], ["sessions", "engagementRate"], limit=5)
        r["countries"] = ga(s, prop, days, ["country"], ["activeUsers"], limit=20)
        r["browser_languages"] = ga(s, prop, days, ["language"], ["activeUsers"], limit=20)
        flt = {"filter": {"fieldName": "eventName", "stringFilter": {"value": "apply_click"}}}
        r["apply_clicks_by_page"] = ga(s, prop, days, ["pagePath"], ["eventCount"], limit=50, flt=flt)
        typ = ga(s, prop, days, ["customEvent:link_type"], ["eventCount"], limit=5, flt=flt)
        r["apply_clicks_by_type"] = typ if isinstance(typ, list) else {"note": "register custom dimension link_type in GA4"}
        r["events"] = ga(s, prop, days, ["eventName"], ["eventCount"], limit=30)
        r["search_queries"] = gsc(s, site, days, ["query"], limit=150)
        r["search_pages"] = gsc(s, site, days, ["page"], limit=150)
        # Simple hints for the review: pages seen in Google but rarely clicked, and pages people leave fast.
        if isinstance(r["search_pages"], list):
            r["hint_low_ctr"] = [p for p in r["search_pages"] if p["impressions"] >= 50 and p["ctr"] < 0.02][:20]
        if isinstance(r["landing_pages"], list):
            r["hint_low_engagement"] = [p for p in r["landing_pages"] if p["sessions"] >= 10 and p["engagementRate"] < 0.4][:20]
        out[k] = r
    # Which sitemaps Search Console knows about (read-only). Empty list = sitemap not submitted yet.
    r = s.get(f"https://www.googleapis.com/webmasters/v3/sites/{quote(site, safe='')}/sitemaps", timeout=60)
    out["sitemaps"] = [{k: m.get(k) for k in ("path", "lastSubmitted", "lastDownloaded", "isPending", "warnings", "errors")}
                       for m in r.json().get("sitemap", [])] if r.status_code == 200 else {"error": r.text[:300]}
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "latest.json").write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    if datetime.date.today().weekday() == 0 or not (OUT / "history").exists():
        (OUT / "history").mkdir(exist_ok=True)
        (OUT / "history" / f"{out['generated']}.json").write_text(json.dumps(out, ensure_ascii=False) + "\n", encoding="utf-8")
    errors = [k for d in ("last7d", "last28d") for k, v in out[d].items() if isinstance(v, dict) and "error" in v]
    print("saved docs/metrics/latest.json", "errors:", errors or "none")
    return 0


if __name__ == "__main__":
    sys.exit(main())
