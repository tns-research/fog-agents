# Refresh brief: {{id}}

**URL (keep it):** {{url}}
**Suggested action:** {{action}} (effort {{effort}}). {{action_rule}}
**Bands:** {{bands}}. **Priority:** {{priority}} (score {{score}} / effort {{effort}}).
**Target query:** `{{target_query}}`
**State:** open in `state.json` as `{{id}}`.

## Rules for whoever writes this change

- Rewrite at the existing URL and in the existing source file. Never create a new URL, a dated copy or an alternative slug, and never change the slug.
- The published page is the source of truth for its own numbers and worked examples: a number changes only with a new source in `facts-ledger.md`.
- Change only what the action and the list below require. Sections that rank stay as they are.
- The visible "updated" date and `dateModified` move only for update, expand or retarget, never for a refine.
- Every new fact, number or name comes from `facts-ledger.md` with its URL and access date; otherwise it stays out.
- Merge only: move the unique content to the surviving URL first, then 301 every merged URL to it, then point the internal links at it.

## Current state (read from the crawl, never from memory)

{{current_state}}

## Technical blockers to fix first

{{blockers}}

## Search Console (bands.json)

{{gsc}}

{{merge}}

## SERP drift check (fill before writing)

| Dimension | This page | Current SERP (date, provider) | Verdict |
|---|---|---|---|
| Format | | | stable or shifted |
| Depth | {{word_count}} words in the raw HTML | | on par or thin |
| Coverage (H2, People also ask) | | | covered or gaps |
| Schema | {{jsonld_types}} | | match or missing |
| Facts and dates | | n/a | current or stale |

Drift verdict: (one line). Final action: (update, refine, expand, retarget or merge; change the suggested action only with a reason from this table).

## Changes (only these)

- [ ] (exact change, located by its heading)

## Do NOT touch

- The URL and the slug.
- (sections that rank today, by heading)

## After publication

1. `python3 scripts/verify_served.py --expect {{expect_path}} --out verify-<YYYYMMDD>.json` passes: title, canonical on itself, og:url, hreflang, listed in the sitemap, JSON-LD parsed with the expected types, indexable, no production jargon.
2. `python3 scripts/seo_state.py ship --state <state.json> --id {{id}} --date <YYYY-MM-DD>`, then `verified --id {{id}} --report verify-<YYYYMMDD>.json`.
3. Search Console follow-up at 14, 28 and 56 days (`seo_state.py due`), tagged `refresh:{{action}}`.
