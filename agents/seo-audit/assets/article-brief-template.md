# Article brief: <working title>

For a page that does not exist yet (no URL of the site ranks or is indexed for the query). Before writing one, check `crawl.jsonl` and `bands.json`: when a page of the site already receives impressions for the query, this is a refresh (`refresh-brief-template.md`), never a new page.

**Query:** `<query>`. **Cluster and pillar:** <cluster>, links up to <pillar URL>.
**URL to create:** <https://site/path/> (checked absent from `crawl.jsonl` and from the sitemap).
**Language:** <en | fr>.

## What Google shows (read on YYYY-MM-DD, provider <serp provider>, file `serp-analysis.json`)

- Dominant format: <listicle, guide, comparison, tool page>; median words of the top 3: <n> (proxy, not a target).
- Questions people ask (People also ask, autocomplete): <list>.
- Schema seen in the top 3 (served HTML): <types>.

## Angle

<one paragraph: what this page answers that the top 3 do not, with the facts that support it (IDs from `facts-ledger.md`)>.

## To avoid

- <claims the brand cannot back, formats that do not fit the query, competitors' wording>

## Expected on the served page

- Title (draft): <...>; description (draft): <...>
- Canonical on itself, in the sitemap, indexable.
- JSON-LD: <Article or BlogPosting with author and dates; BreadcrumbList>, present in the served HTML.
- Internal links: from <pages> to this page; from this page to <pages>.

The writer delivers the source file; the agent runs `verify_served.py` on the published URL before the brief is closed.
