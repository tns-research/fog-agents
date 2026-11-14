#!/usr/bin/env python3
"""
make_fixtures.py

Writes the frozen test fixtures of growth-pulse: six weeks (2026-08-31 to 2026-10-11)
of FICTIONAL data for the example brand swanbase, in every format the connectors read.
Every number here is invented by a seeded generator; none comes from a real account.

    python3 scripts/fixtures/make_fixtures.py            # rewrite the fixtures in place
    python3 scripts/fixtures/make_fixtures.py --check    # exit 1 when a file would change

The same underlying days feed the API responses and the CSV exports of a source, so
the selftest can check that both providers give identical source files.
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import io
import json
import random
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SINCE, UNTIL = dt.date(2026, 8, 31), dt.date(2026, 10, 11)
HISTORY_SINCE = dt.date(2026, 6, 1)
DAYS = [SINCE + dt.timedelta(days=i) for i in range((UNTIL - SINCE).days + 1)]
SITE = "https://swanbase.example"

WEB_DOW = [1.15, 1.2, 1.15, 1.1, 0.95, 0.6, 0.65]  # Monday first: weekday traffic of a B2B site
LI_DOW = [1.2, 1.3, 1.2, 1.1, 0.9, 0.4, 0.4]
GSC_DOW = [1.1, 1.15, 1.1, 1.05, 0.95, 0.8, 0.85]

QUERIES = [  # query, share of impressions, position offset, page
    ("startup accelerator paris", 0.22, -3.0, "/program/"),
    ("pre-seed accelerator", 0.14, -1.0, "/program/"),
    ("how to pitch investors", 0.12, 1.5, "/blog/first-pitch/"),
    ("swanbase", 0.06, -8.0, "/"),
    ("pre seed checklist", 0.09, 0.5, "/blog/pre-seed-checklist/"),
    ("startup events paris", 0.07, 2.0, "/events/"),
    ("fundraising mistakes", 0.05, 3.0, "/blog/first-pitch/"),
]
ANON_SHARE = 0.25  # share of impressions on anonymized queries (absent from query rows)
EVENTS = [("apply_click", 0.085), ("newsletter_signup", 0.018), ("invite_link_copied", 0.004)]
CUSTOMERS = [f"cus_FICT{i:02d}" for i in range(1, 15)]
PRICES = [60, 120, 240, 480]  # fictional meeting-room booking prices, EUR


def binom(rng: random.Random, n: int, p: float) -> int:
    return sum(1 for _ in range(max(0, n)) if rng.random() < p)


def ctr_at(pos: float) -> float:
    """Fictional click curve of the generator (not a benchmark)."""
    return max(0.004, 0.11 - 0.0075 * pos)


def generate():
    rng = random.Random(20261014)
    li, ig_posts, web, gsc, qrows, prow = {}, [], {}, {}, [], {}
    for d in DAYS:
        wd = d.weekday()
        imp = 600 * LI_DOW[wd] * rng.uniform(0.88, 1.12)
        li[d] = {"impressions": imp}
    def bump(day, amount):
        if day in li:
            li[day]["impressions"] += amount * rng.uniform(0.92, 1.08)
    for d in DAYS:
        if d.weekday() == 1 and d < dt.date(2026, 10, 5):  # one post a week, Tuesday
            bump(d, 1800); bump(d + dt.timedelta(days=1), 700)
    bump(dt.date(2026, 10, 6), 5200); bump(dt.date(2026, 10, 7), 2400); bump(dt.date(2026, 10, 8), 900)  # carousel
    bump(dt.date(2026, 10, 8), 1600); bump(dt.date(2026, 10, 9), 600)
    for d in DAYS:
        i = round(li[d]["impressions"])
        li[d] = {"impressions": i, "clicks": binom(rng, i, 0.012), "reactions": binom(rng, i, 0.018),
                 "comments": binom(rng, i, 0.002), "reposts": binom(rng, i, 0.0012)}
        if d.weekday() in (0, 3):
            ig_posts.append({"day": d, "impressions": round(420 * rng.uniform(0.75, 1.3)), "likes": rng.randint(18, 42),
                             "comments": rng.randint(1, 6), "shares": rng.randint(0, 4), "saves": rng.randint(1, 8),
                             "follows": rng.randint(0, 3)})
    for d in DAYS:
        wd = d.weekday()
        if d < dt.date(2026, 10, 1):
            pos = 9.4 + rng.uniform(-0.3, 0.3)
        elif d < dt.date(2026, 10, 3):
            pos = 9.6 + rng.uniform(-0.2, 0.2)
        elif d < dt.date(2026, 10, 5):
            pos = 10.5 + rng.uniform(-0.2, 0.2)
        else:
            pos = 11.9 + rng.uniform(-0.3, 0.3)
        impr_total = round(430 * GSC_DOW[wd] * rng.uniform(0.92, 1.08) * (0.94 if d >= dt.date(2026, 10, 5) else 1.0))
        tot_c, tot_i, tot_pw = 0, 0, 0.0
        for q, share, off, page in QUERIES:
            extra = 2.0 if q == "startup accelerator paris" and d >= dt.date(2026, 10, 3) else 0.0
            qp = round(max(1.1, pos + off + extra + rng.uniform(-0.4, 0.4)), 2)
            qi = round(impr_total * share * rng.uniform(0.85, 1.15))
            qc = binom(rng, qi, ctr_at(qp) * (3.0 if q == "swanbase" else 1.0))
            qrows.append({"date": d, "query": q, "page": SITE + page, "clicks": qc, "impressions": qi, "position": qp})
            tot_c += qc; tot_i += qi; tot_pw += qp * qi
        ai = round(impr_total * ANON_SHARE)
        ap = round(pos + 2.5, 2)
        ac = binom(rng, ai, ctr_at(ap))
        prow[d] = (ac, ai, ap)
        tot_c += ac; tot_i += ai; tot_pw += ap * ai
        gsc[d] = {"clicks": tot_c, "impressions": tot_i, "position": round(tot_pw / tot_i, 2) if tot_i else 0.0}
    for d in DAYS:
        wd = d.weekday()
        v = round((62 * WEB_DOW[wd] + 0.006 * li[d]["impressions"] + 0.6 * gsc[d]["clicks"]) * rng.uniform(0.9, 1.1))
        ev = {}
        for name, p in EVENTS:
            if name == "newsletter_signup" and d >= dt.date(2026, 10, 5):
                p = 0.026
            ev[name] = binom(rng, v, p)
        web[d] = {"visitors": v, "visits": round(v * rng.uniform(1.1, 1.2)), "pageviews": round(v * rng.uniform(1.7, 2.1)),
                  "new_users": round(v * rng.uniform(0.74, 0.82)), "events": ev}
    pays = []
    d = HISTORY_SINCE
    while d <= UNTIL:
        p = 0.3 if d < SINCE else (0.42 if d < dt.date(2026, 10, 5) else 0.7)
        if d.weekday() < 5 and rng.random() < p:
            pays.append({"day": d, "hour": rng.randint(8, 19), "minute": rng.randint(0, 59),
                         "customer": rng.choice(CUSTOMERS[:9] if d < SINCE else CUSTOMERS), "amount": rng.choice(PRICES),
                         "status": "succeeded", "refunded": 0})
        d += dt.timedelta(days=1)
    for p in pays:
        if p["day"] == dt.date(2026, 9, 23) or (p["day"].isocalendar()[1] == 39 and p["amount"] == 120):
            p["refunded"] = p["amount"]
            break
    pays.append({"day": dt.date(2026, 9, 16), "hour": 10, "minute": 5, "customer": "cus_FICT03", "amount": 240,
                 "status": "failed", "refunded": 0})
    pays.sort(key=lambda p: (p["day"], p["hour"], p["minute"]))
    for i, p in enumerate(pays):
        p["id"] = f"ch_FICT{i + 1:04d}"
    return li, ig_posts, web, gsc, qrows, prow, pays


def zernio_files(li, ig_posts):
    """Fictional Zernio answers, fed by the same LinkedIn and Instagram days as the CSV exports
    so the selftest can compare both, plus a small X account that loses followers. The ids,
    handles and emails are invented: the selftest checks that none reaches a source file."""
    rng = random.Random(20261030)
    ig = {p["day"]: p for p in ig_posts}
    li_posts = {d: 1 for d in DAYS if d.weekday() == 1 and d < dt.date(2026, 10, 5)}
    li_posts.update({dt.date(2026, 10, 6): 1, dt.date(2026, 10, 8): 1})
    x_days = {d: {"impressions": rng.randint(40, 160), "likes": rng.randint(0, 6), "comments": rng.randint(0, 2),
                  "shares": rng.randint(0, 2), "clicks": rng.randint(0, 4)} for d in DAYS}
    x_posts = {d: 1 for d in DAYS if d.weekday() == 2}

    def metrics(**kw):
        return {"impressions": 0, "reach": 0, "likes": 0, "comments": 0, "shares": 0, "saves": 0, "clicks": 0, "views": 0, **kw}

    received = {
        "linkedin": {d: metrics(impressions=li[d]["impressions"], reach=round(li[d]["impressions"] * 0.7), likes=li[d]["reactions"],
                                comments=li[d]["comments"], shares=li[d]["reposts"], clicks=li[d]["clicks"]) for d in DAYS},
        "instagram": {d: (metrics(views=ig[d]["impressions"], likes=ig[d]["likes"], comments=ig[d]["comments"], shares=ig[d]["shares"],
                                  saves=ig[d]["saves"]) if d in ig else metrics()) for d in DAYS},
        "twitter": {d: metrics(**x_days[d]) for d in DAYS},
    }
    counts = {"linkedin": li_posts, "instagram": {d: 1 for d in ig}, "twitter": x_posts}

    def breakdown():
        rows = []
        for name in sorted(received):
            row = {"platform": name, "postCount": sum(counts[name].values())}
            for key in metrics():
                row[key] = sum(m[key] for m in received[name].values())
            rows.append(row)
        return rows

    published = []
    for d in DAYS:
        day_counts = {name: counts[name][d] for name in sorted(counts) if d in counts[name]}
        if day_counts:
            total = {k: sum(received[name][d][k] for name in day_counts) for k in metrics()}
            published.append({"date": d.isoformat(), "postCount": sum(day_counts.values()), "platforms": day_counts, "metrics": total})
    out = {"zernio/api/daily-metrics-published.json": {"dailyData": published, "platformBreakdown": breakdown()}}
    for name in sorted(received):
        rows = [{"date": d.isoformat(), "postCount": counts[name].get(d, 0), "platforms": {name: counts[name].get(d, 0)}, "metrics": received[name][d]}
                for d in DAYS]
        out[f"zernio/api/daily-metrics-received-{name}.json"] = {
            "dailyData": rows, "platformBreakdown": [b for b in breakdown() if b["platform"] == name]}
    day_before = SINCE - dt.timedelta(days=1)
    li_count, ig_count, x_count = 2140, 860, 310
    li_stats, ig_stats, x_stats = [], [], []
    for d in [day_before, *DAYS]:
        if d != day_before:
            li_count += rng.randint(0, 7)
            ig_count += ig[d]["follows"] if d in ig else 0
            x_count -= rng.randint(0, 2)
        if d != dt.date(2026, 9, 20):  # a day the follower sync missed
            li_stats.append({"date": d.isoformat(), "followers": li_count})
        ig_stats.append({"date": d.isoformat(), "followers": ig_count})
        x_stats.append({"date": d.isoformat(), "followers": x_count})
    account = lambda i, name, handle, stats: {"_id": i, "profileId": "fict-profile-1", "isActive": True, "platform": name, "username": handle,
                                              "displayName": "Swanbase Fictional", "currentFollowers": stats[-1]["followers"],
                                              "growth": stats[-1]["followers"] - stats[0]["followers"], "dataPoints": len(stats),
                                              "accountStats": {"email": "fictional@swanbase.example"}}
    out["zernio/api/follower-stats.json"] = {
        "accounts": [account("fict-account-li", "linkedin", "@swanbase-fict-li", li_stats), account("fict-account-ig", "instagram", "@swanbase-fict-ig", ig_stats),
                     account("fict-account-x", "twitter", "@swanbase-fict-x", x_stats)],
        "stats": {"fict-account-li": li_stats, "fict-account-ig": ig_stats, "fict-account-x": x_stats},
        "dateRange": {"from": f"{day_before.isoformat()}T00:00:00.000Z", "to": f"{UNTIL.isoformat()}T23:59:59.999Z"}, "granularity": "daily"}
    return out


def csv_text(header, rows, delim=","):
    buf = io.StringIO()
    w = csv.writer(buf, delimiter=delim, lineterminator="\n")
    w.writerow(header)
    w.writerows(rows)
    return buf.getvalue()


def files():
    li, ig_posts, web, gsc, qrows, prow, pays = generate()
    out = {}
    ts = lambda d: f"{d.isoformat()} 00:00:00"
    # Umami
    out["umami/api/pageviews.json"] = {"pageviews": [{"x": ts(d), "y": web[d]["pageviews"]} for d in DAYS],
                                       "sessions": [{"x": ts(d), "y": web[d]["visitors"]} for d in DAYS]}
    out["umami/api/events-series.json"] = [{"x": n, "t": ts(d), "y": web[d]["events"][n]}
                                           for d in DAYS for n, _ in EVENTS if web[d]["events"][n]]
    out["umami/api-error/pageviews.json"] = {"_http_error": 429}
    out["umami/csv/umami-daily.csv"] = csv_text(["date", "visitors", "pageviews"],
                                                [[d.isoformat(), web[d]["visitors"], web[d]["pageviews"]] for d in DAYS])
    out["umami/csv/umami-events.csv"] = csv_text(["date", "event", "count"],
                                                 [[d.isoformat(), n, web[d]["events"][n]] for d in DAYS for n, _ in EVENTS if web[d]["events"][n]])
    # Plausible
    out["plausible/api/query-timeseries.json"] = {"results": [{"dimensions": [d.isoformat()], "metrics": [web[d]["visitors"], web[d]["visits"], web[d]["pageviews"]]} for d in DAYS]}
    out["plausible/api/query-goals.json"] = {"results": [{"dimensions": [d.isoformat(), n], "metrics": [web[d]["events"][n]]}
                                                         for d in DAYS for n, _ in EVENTS if web[d]["events"][n]]}
    out["plausible/csv/visitors.csv"] = csv_text(["date", "visitors", "pageviews", "visits", "views_per_visit", "bounce_rate", "visit_duration"],
                                                 [[d.isoformat(), web[d]["visitors"], web[d]["pageviews"], web[d]["visits"],
                                                   round(web[d]["pageviews"] / web[d]["visits"], 2), 58, 74] for d in DAYS])
    out["plausible/csv/goals.csv"] = csv_text(["date", "event", "count"],
                                              [[d.isoformat(), n, web[d]["events"][n]] for d in DAYS for n, _ in EVENTS if web[d]["events"][n]])
    # GA4
    ymd = lambda d: d.strftime("%Y%m%d")
    out["ga4/api/run-report-totals.json"] = {"rows": [{"dimensionValues": [{"value": ymd(d)}],
                                                       "metricValues": [{"value": str(web[d][k])} for k in ("visitors", "visits", "pageviews", "new_users")]} for d in DAYS]}
    out["ga4/api/run-report-events.json"] = {"rows": [{"dimensionValues": [{"value": ymd(d)}, {"value": n}], "metricValues": [{"value": str(web[d]["events"][n])}]}
                                                      for d in DAYS for n, _ in EVENTS if web[d]["events"][n]]}
    head = "# ----------------------------------------\n# Traffic acquisition (fictional fixture)\n# Start date: 20260831\n# End date: 20261011\n# ----------------------------------------\n\n"
    out["ga4/csv/ga4-traffic.csv"] = head + csv_text(["Date", "Active users", "Sessions", "Views", "New users"],
                                                     [[ymd(d), web[d]["visitors"], web[d]["visits"], web[d]["pageviews"], web[d]["new_users"]] for d in DAYS])
    out["ga4/csv/ga4-events.csv"] = head + csv_text(["Date", "Event name", "Event count"],
                                                    [[ymd(d), n, web[d]["events"][n]] for d in DAYS for n, _ in EVENTS if web[d]["events"][n]])
    # Search Console
    def api_rows(dims, rows):
        return {"_comment": "Fictional Search Console rows for the growth-pulse tests. Invented numbers.", "dimensions": dims, "rows": rows}
    out["gsc/api/query-date.json"] = api_rows(["date"], [{"keys": [d.isoformat()], "clicks": gsc[d]["clicks"], "impressions": gsc[d]["impressions"],
                                                           "ctr": round(gsc[d]["clicks"] / gsc[d]["impressions"], 4), "position": gsc[d]["position"]} for d in DAYS])
    out["gsc/api/query-date-query.json"] = api_rows(["date", "query"], [{"keys": [r["date"].isoformat(), r["query"]], "clicks": r["clicks"], "impressions": r["impressions"],
                                                                          "ctr": round(r["clicks"] / r["impressions"], 4) if r["impressions"] else 0, "position": r["position"]} for r in qrows])
    pages = {}
    for r in qrows:
        a = pages.setdefault((r["date"], r["page"]), [0, 0, 0.0])
        a[0] += r["clicks"]; a[1] += r["impressions"]; a[2] += r["position"] * r["impressions"]
    for d, (ac, ai, ap) in prow.items():
        for page, part in ((SITE + "/", 0.5), (SITE + "/blog/pre-seed-checklist/", 0.5)):
            a = pages.setdefault((d, page), [0, 0, 0.0])
            c, i = round(ac * part), round(ai * part)
            a[0] += c; a[1] += i; a[2] += ap * i
    out["gsc/api/query-date-page.json"] = api_rows(["date", "page"], [{"keys": [d.isoformat(), pg], "clicks": v[0], "impressions": v[1],
                                                                        "ctr": round(v[0] / v[1], 4) if v[1] else 0, "position": round(v[2] / v[1], 2) if v[1] else 0}
                                                                       for (d, pg), v in sorted(pages.items())])
    dates_rows = [[d.isoformat(), gsc[d]["clicks"], gsc[d]["impressions"], f"{gsc[d]['clicks'] * 100 / gsc[d]['impressions']:.2f}%", gsc[d]["position"]] for d in reversed(DAYS)]
    out["gsc/csv/Dates.csv"] = csv_text(["Date", "Clicks", "Impressions", "CTR", "Position"], dates_rows)
    out["gsc/csv/Dates-lag.csv"] = csv_text(["Date", "Clicks", "Impressions", "CTR", "Position"], dates_rows[3:])
    # Social
    li_head = ["Date", "Impressions (organic)", "Impressions (sponsored)", "Impressions (total)", "Clicks (organic)", "Clicks (sponsored)", "Clicks (total)",
               "Reactions (organic)", "Reactions (sponsored)", "Reactions (total)", "Comments (organic)", "Comments (sponsored)", "Comments (total)",
               "Reposts (organic)", "Reposts (sponsored)", "Reposts (total)"]
    out["social/linkedin.csv"] = csv_text(li_head, [[d.strftime("%m/%d/%Y"), li[d]["impressions"], 0, li[d]["impressions"], li[d]["clicks"], 0, li[d]["clicks"],
                                                     li[d]["reactions"], 0, li[d]["reactions"], li[d]["comments"], 0, li[d]["comments"],
                                                     li[d]["reposts"], 0, li[d]["reposts"]] for d in DAYS])
    out["social/instagram-posts.csv"] = csv_text(["Post ID", "Permalink", "Publish time", "Post type", "Views", "Likes", "Comments", "Shares", "Saves", "Follows"],
                                                 [[f"1790000000{i:04d}", f"https://www.instagram.example/p/FICT{i:04d}/", f"{p['day'].strftime('%m/%d/%Y')} 18:30",
                                                   "IG carousel", p["impressions"], p["likes"], p["comments"], p["shares"], p["saves"], p["follows"]]
                                                  for i, p in enumerate(ig_posts, 1)])
    out.update(zernio_files(li, ig_posts))
    # Revenue
    def unix(p):
        return int(dt.datetime(p["day"].year, p["day"].month, p["day"].day, p["hour"], p["minute"], tzinfo=dt.timezone.utc).timestamp())
    charges = [{"id": p["id"], "object": "charge", "amount": p["amount"] * 100, "amount_refunded": p["refunded"] * 100, "currency": "eur",
                "created": unix(p), "customer": p["customer"], "paid": p["status"] == "succeeded", "status": p["status"],
                "description": "Meeting room booking (fictional)"} for p in reversed(pays)]
    half = len(charges) // 2
    out["revenue/api/charges-1.json"] = {"object": "list", "data": charges[:half], "has_more": True, "url": "/v1/charges"}
    out["revenue/api/charges-2.json"] = {"object": "list", "data": charges[half:], "has_more": False, "url": "/v1/charges"}
    out["revenue/csv/payments.csv"] = csv_text(["id", "Created date (UTC)", "Amount", "Amount Refunded", "Currency", "Status", "Customer ID", "Description"],
                                               [[p["id"], f"{p['day'].isoformat()} {p['hour']:02d}:{p['minute']:02d}:00", f"{p['amount']:.2f}",
                                                 f"{p['refunded']:.2f}", "eur", "Paid" if p["status"] == "succeeded" else "Failed", p["customer"],
                                                 "Meeting room booking (fictional)"] for p in pays])
    out["actions.csv"] = csv_text(["date", "channel", "stage", "action"], [
        ["2026-09-15", "site", "activation", "Apply button moved above the fold on the program page"],
        ["2026-10-01", "site", "acquisition", "Program page title and meta description rewritten"],
        ["2026-10-05", "blog", "activation", "Newsletter box added at the end of every blog article"],
        ["2026-10-06", "linkedin", "acquisition", "Carousel: what a pre-seed jury reads first"],
        ["2026-10-08", "linkedin", "acquisition", "Post: pitch night recap"],
    ])
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="Write the fictional growth-pulse fixtures (seeded, deterministic).")
    ap.add_argument("--check", action="store_true", help="exit 1 when a fixture differs from what the generator writes")
    args = ap.parse_args()
    changed = []
    for rel, content in files().items():
        text = content if isinstance(content, str) else json.dumps(content, indent=1, ensure_ascii=False) + "\n"
        p = HERE / rel
        if p.exists() and p.read_text(encoding="utf-8") == text:
            continue
        changed.append(rel)
        if not args.check:
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(text, encoding="utf-8")
    if args.check:
        print("fixtures up to date" if not changed else "fixtures differ: " + ", ".join(changed))
        return 1 if changed else 0
    print(f"{len(changed)} fixture file(s) written")
    return 0


if __name__ == "__main__":
    sys.exit(main())
