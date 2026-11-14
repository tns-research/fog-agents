#!/usr/bin/env python3
"""
connect_revenue.py

Daily revenue, payments, new customers and returning payments from Stripe or from a
revenue CSV into the growth-pulse source file (assets/source.schema.json).

Providers, in the order --provider auto tries them:
  csv  a payments export: the Stripe dashboard export (Payments > Export: id,
       Created date (UTC), Amount, Amount Refunded, Currency, Status, Customer ID) or
       any file with date, amount, currency and a customer column (an invoicing tool,
       a spreadsheet). Amounts in major units (12.50).
  api  Stripe: STRIPE_API_KEY (a restricted key with read access to charges is
       enough). GET /v1/charges, paginated, from --history-days before the window so a
       returning customer is told from a new one. Reading the API costs nothing.
  none nothing set: a 'missing' health file with the export instructions.

    python3 connect_revenue.py --today 2026-10-14 --out <run>/data/revenue.json
    python3 connect_revenue.py --today 2026-10-14 --csv exports/payments.csv --currency eur --out <run>/data/revenue.json

Metrics per day, in the main currency: gross (succeeded payments), refunds, net,
payments (count), new_customers (first succeeded payment ever seen), returning_payments
(payments by a customer who paid before). Customer ids are read to tell new from
returning and never written: the output holds counts and amounts only. Days are UTC.

Exit codes: 0 data written (ok, partial or stale), 1 health file written without data
(missing or error), 2 usage error or unreadable input.
"""

from __future__ import annotations

import argparse
import datetime as dt
import os
import sys
from collections import Counter
from typing import Any, Dict, List, Optional

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.dont_write_bytecode = True
import gp_lib as G  # noqa: E402

HOW = ("export the payments to CSV (Stripe: Payments > Export; or any file with date, amount, currency, "
       "customer) covering at least the window plus some history, and pass it with --csv")
ZERO_DECIMAL = {"bif", "clp", "djf", "gnf", "jpy", "kmf", "krw", "mga", "pyg", "rwf", "ugx", "vnd", "vuv", "xaf", "xof", "xpf"}
COLS = {
    "date": ["created date (utc)", "created (utc)", "created", "date", "paid at", "payment date"],
    "amount": ["amount", "amount paid", "total", "gross"],
    "refunded": ["amount refunded", "refunded amount", "refunds", "refund"],
    "currency": ["currency"],
    "status": ["status"],
    "customer": ["customer id", "customer", "customer_id", "client", "customer email"],
}
OK_STATUS = {"", "paid", "succeeded", "success", "complete", "completed", "captured"}


class Payment:
    __slots__ = ("day", "amount", "refunded", "currency", "customer")

    def __init__(self, day: dt.date, amount: float, refunded: float, currency: str, customer: Optional[str]) -> None:
        self.day, self.amount, self.refunded, self.currency, self.customer = day, amount, refunded, currency, customer


def has_api() -> Optional[str]:
    return G.env_set("STRIPE_API_KEY", "STRIPE_SECRET_KEY")


def aggregate(payments: List[Payment], args, since: dt.date, until: dt.date, today: dt.date, provider: str,
              notes: List[str]) -> Dict[str, Any]:
    if not payments:
        return G.build_source("revenue", provider, since, until, G.Daily(), today=today, status="error",
                              message="no succeeded payment in the input")
    currency = (args.currency or Counter(p.currency for p in payments).most_common(1)[0][0]).lower()
    other = [p for p in payments if p.currency != currency]
    if other:
        notes.append(f"{len(other)} payment(s) in another currency than {currency.upper()} left out")
    seen = set()
    daily = G.Daily()
    first_day = min(p.day for p in payments)
    # A payments list holds payments only: a day without one is a zero, not a missing day.
    for d in G.days_between(since, until):
        daily.touch(d)
    for p in sorted(payments, key=lambda x: x.day):
        if p.currency != currency:
            continue
        returning = p.customer is not None and p.customer in seen
        if p.customer is not None:
            seen.add(p.customer)
        if not since <= p.day <= until:
            continue
        daily.add(p.day, "gross", p.amount)
        daily.add(p.day, "refunds", p.refunded)
        daily.add(p.day, "net", p.amount - p.refunded)
        daily.add(p.day, "payments", 1)
        if p.customer is None:
            continue
        daily.add(p.day, "returning_payments" if returning else "new_customers", 1)
    if first_day > since:
        notes.append(f"first payment in the input on {first_day.isoformat()}: check that the export starts before the window")
    notes.append("days without a payment count as zero: the export must cover the whole window")
    history = (since - first_day).days
    notes.append(f"currency {currency.upper()}; new vs returning judged on {max(history, 0)} day(s) of history before the window")
    return G.build_source("revenue", provider, since, until, daily, today=today,
                          fill_zero=["gross", "refunds", "net", "payments", "new_customers", "returning_payments"], notes=notes)


def api(args, since: dt.date, until: dt.date, today: dt.date) -> Dict[str, Any]:
    start = since - dt.timedelta(days=args.history_days)
    gte = int(dt.datetime.combine(start, dt.time()).replace(tzinfo=dt.timezone.utc).timestamp())
    lte = int(dt.datetime.combine(until, dt.time(23, 59, 59)).replace(tzinfo=dt.timezone.utc).timestamp())
    key = os.environ.get("STRIPE_API_KEY") or os.environ.get("STRIPE_SECRET_KEY") or ""
    headers = {} if args.fixtures else {"authorization": "Bearer " + key}
    payments: List[Payment] = []
    after, page = None, 1
    while True:
        url = f"https://api.stripe.com/v1/charges?limit=100&created[gte]={gte}&created[lte]={lte}"
        if after:
            url += f"&starting_after={after}"
        data = G.http_json(url, key=f"charges-{page}", fixtures=args.fixtures, headers=headers)
        items = data.get("data", [])
        for c in items:
            if c.get("status") != "succeeded" or not c.get("paid", True):
                continue
            cur = str(c.get("currency", "")).lower()
            div = 1 if cur in ZERO_DECIMAL else 100
            day = dt.datetime.fromtimestamp(int(c["created"]), tz=dt.timezone.utc).date()
            payments.append(Payment(day, int(c.get("amount", 0)) / div, int(c.get("amount_refunded", 0)) / div, cur,
                                    c.get("customer") or None))
        if not data.get("has_more") or not items:
            break
        after, page = items[-1]["id"], page + 1
        if page > args.max_pages:
            raise G.ProviderError(f"more than {args.max_pages} pages of charges: narrow the window or raise --max-pages")
    return aggregate(payments, args, since, until, today, "fixture" if args.fixtures else "api", [f"{page} page(s) of charges"])


def from_csv(args, since: dt.date, until: dt.date, today: dt.date) -> Dict[str, Any]:
    payments: List[Payment] = []
    notes = []
    for path in args.csv:
        rows = G.read_csv(path)
        if not rows:
            continue
        hs = rows[0].keys()
        cols = {k: G.pick_column(hs, a) for k, a in COLS.items()}
        if not cols["date"] or not cols["amount"]:
            raise G.InputError(f"{path}: expected at least a date and an amount column")
        skipped = 0
        for r in rows:
            status = (r.get(cols["status"], "") if cols["status"] else "").strip().lower()
            day = G.parse_date_cell(r[cols["date"]], args.date_format)
            amount = G.parse_number(r[cols["amount"]])
            if status not in OK_STATUS or day is None or amount is None:
                skipped += 1
                continue
            refunded = G.parse_number(r.get(cols["refunded"], "")) if cols["refunded"] else 0.0
            cur = (r.get(cols["currency"], "") if cols["currency"] else (args.currency or "eur")).strip().lower() or "eur"
            cust = (r.get(cols["customer"], "") if cols["customer"] else "").strip() or None
            payments.append(Payment(day, amount, refunded or 0.0, cur, cust))
        notes.append(f"read {os.path.basename(path)}" + (f", {skipped} row(s) not succeeded or unreadable left out" if skipped else ""))
    return aggregate(payments, args, since, until, today, "csv", notes)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Stripe or revenue CSV into a growth-pulse source file.")
    G.add_common_args(ap, "payments export (Stripe Payments export or date, amount, currency, customer)")
    ap.add_argument("--currency", help="main currency, e.g. eur (default: the most frequent one)")
    ap.add_argument("--history-days", type=int, default=365, help="API: days fetched before the window to tell returning customers (default 365)")
    ap.add_argument("--max-pages", type=int, default=50, help="API: page cap, 100 charges per page (default 50)")
    ap.add_argument("--date-format", help="strptime format of the CSV date column when auto-detection is wrong")
    args = ap.parse_args(argv)
    return G.run_connector("revenue", args, has_api=has_api, api=api, from_csv=from_csv, how_to_export=HOW)


if __name__ == "__main__":
    sys.exit(main())
