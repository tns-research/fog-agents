---
name: collecting-signals
description: Plans and runs the collection of dated public signals (a request for help, a complaint, a tool switch, a public question, a company creation, an event) from free sources, one record per act of one person, with the health of every source recorded. Covers the signal taxonomy, query writing, the collectors (Hacker News Algolia, GitHub search, Reddit OAuth, Luma, Notion and folk lists, the French company registry), the manual path for LinkedIn and X posts found by web search, market-signal quotes and closed groups read from screenshots. Use at Steps 1 and 2 of first-users-hunter, or alone to refresh signals. Triggers on "find people who need", "who is asking for", "signals", "first users", "collect".
license: Apache-2.0
compatibility: Claude Code, Cursor, Codex CLI, Gemini CLI
metadata:
  version: "2.0"
allowed-tools: Read Write Bash
---

# collecting-signals

A first user is someone who said, in public and recently, that they have the problem. This skill finds those moments. Collectors do the fetching and dating; the model writes the queries, adds what only a web search finds, and never retypes a date or an excerpt.

## Signal taxonomy

| Type | What the person did | Default max age | Points |
|------|---------------------|----------------:|-------:|
| `ask` | asked for help, a recommendation or a tool for the task | 45 days | 12 |
| `switch` | is leaving a tool or a way of working, asked for an alternative | 60 | 10 |
| `complaint` | complained about the status quo, a workaround, a competitor | 60 | 9 |
| `question` | asked a public question on the problem space | 45 | 7 |
| `trigger` | a dated event that opens the need: company created, funding, a hire, a launch | 60 | 6 |
| `event` | hosts or speaks at an event on the topic (may be ahead, up to 60 days) | 14 | 5 |
| `build` | builds in public in an adjacent domain | 30 | 4 |
| `listed` | appears in a public list or directory | seed only | 0 |

Values live in [`assets/criteria.json`](../../assets/criteria.json); `recency_days` in `config.json` overrides the ages. A `listed` row never qualifies a person alone: it seeds a search for their own posts. A registry `trigger` says a company exists, nothing about its need: same treatment in practice, since a registry person has no handle until you find their posts.

`collect.py` classifies each record with the patterns of `criteria.json > classifier` (switch, ask, complaint, question, else build). A comment is classified on its own words, not on the story title. The model may correct the type in `people-<YYYYMMDD>.jsonl` after reading the thread.

## Step 1: write the plan into config.json

1. **Profile in three lines**: role pattern; stage, vertical or size; the moment the need appears (a launch, a first hire, a raise, a tool that breaks).
2. **`icp_keywords`**: 6 to 12 words the person writes about themselves or the problem (`pre-seed`, `solo founder`, `beta testers`, `invoice`, the job title). A signal must contain one (registry rows excepted). Too broad and the shortlist fills with noise; too narrow and it stays empty.
3. **Queries per collector**: phrases the person would type when the need is live, not category words. "looking for a cofounder", "alternative to <incumbent>", "how did you find your first users", "<incumbent> pricing" for complaints. Two to five queries per source; one `id` each (it shows in the shortlist).
4. **Sources**: enable what fits the target user. Developers and technical founders: HN, GitHub. Consumer or general founders: Reddit (with keys), LinkedIn and X by web search. Local communities: Luma places. FR company founders: `registry_fr` with a narrow query (postcode, activity section). Lists a community published on Notion or folk: as seeds.

## Step 2: run, then add what no API serves

```bash
python3 scripts/collect.py signals --config <project>/first-users-hunter/config.json --run-dir <run>
```

Each record is validated against [`assets/signal.schema.json`](../../assets/signal.schema.json); its verbatim text is cached under `<run>/cache/<hash>.txt` for its URL; `<run>/source-health.json` gets one line per collector (`ok`, `empty`, `skipped`, `blocked`, `error`, with the message). Run it again after adding manual rows: records merge by `signal_id`, cached pages are kept.

### The collectors

| Collector | Endpoint | Key | Health from a server, tested 2026-10-12 |
|-----------|----------|-----|-----------------------------------------|
| `hn` | `hn.algolia.com/api/v1/search_by_date`, user API `hacker-news.firebaseio.com/v0/user/<id>.json` | none | 200; a missing user returns `null` |
| `github` | `api.github.com/search/issues`, `users/<u>/events/public`; GraphQL for discussions | none for issues; free `GITHUB_TOKEN` for discussions | 200 without key; unknown user 404 |
| `reddit` | `www.reddit.com/api/v1/access_token` then `oauth.reddit.com` | free script app: `REDDIT_CLIENT_ID`, `REDDIT_CLIENT_SECRET` | without keys: `skipped`, no call made |
| `luma` | `luma.com/<place>` and event pages, data in `__NEXT_DATA__` | none | 200, 20 events per city page |
| `notion` | `<space>.notion.site/api/v3/loadPageChunk`, `queryCollection` | none | see [`references/public-list-endpoints.md`](../../references/public-list-endpoints.md) |
| `folk` | `gateway.folk.app/networks/graphql` (`sharedViewContactList`) | none | same reference |
| `registry_fr` | `recherche-entreprises.api.gouv.fr/search` | none | 200; no date filter, sorted by relevance: narrow queries |
| `manual` | `<run>/manual-signals.csv` | none | local file |

Each collector runs alone too: `python3 scripts/collectors/<name>.py --help`, `--config`, `--activity <handle>`, `--fixtures` (offline replay), `--record <dir>` (save live answers as fixtures).

Not used because they fail from a server: anonymous Reddit JSON (403 on `/search.json`, `/r/<sub>/new.json`, `old.reddit.com`, `api.reddit.com`; the `.rss` feed answers once then 429), read.cv (402, site closed), Discord channel URLs (login page). Bluesky public search answered 403 on 2026-10-10. A founder on a home connection may still read Reddit pages: paste them through the manual path.

### The manual path: LinkedIn, X, pasted threads, closed groups

LinkedIn and X have no free search API. Their public posts are indexed by web search:

- `site:linkedin.com/posts "<phrase>"` and `site:x.com "<phrase>"` with the phrases of Step 1; patterns in [`assets/linkedin-search-patterns.md`](../../assets/linkedin-search-patterns.md).
- Keep only URLs that carry a post id (`activity-<id>`, `ugcPost-<id>`, `/status/<id>`): the date comes from the id (`python3 scripts/date_from_url.py <url>`), never from the search snippet.
- Fetch the post with the `scrape` capability, save its text in `<run>/texts/<name>.txt` exactly as shown, and add a row to `<run>/manual-signals.csv` (columns in `scripts/collectors/manual.py --help`). The handle is the LinkedIn slug in the URL: a URL whose slug is someone else (a post where the person is only tagged) is refused.
- Never open a LinkedIn profile page: posts only.

Other manual rows:

- **market-signal quotes** whose author is a person: one `complaint` row per quote with its `permalink` and `date`. The quote is a reason to talk to its author, never a testimonial.
- **Closed groups**: the founder joins and drops 3 to 5 screenshots of the recent feed. Read them with `vision`, transcribe the messages that are signals verbatim with author and timestamp, `network: community`, `date_source: founder`, the screenshot file as `text_file`. Without vision, the founder pastes the exported text.
- **Threads the founder pastes** (Reddit without OAuth, a forum, Indie Hackers): `date_source: page` with the date read on the page.

## Done when

`<run>/signals.jsonl` holds every collected and manual record, all valid; `<run>/source-health.json` has a line per collector; the report's Methodology lists the sources used, skipped and failed, with their messages.

## Anti-patterns

- Category queries ("startup tools") instead of the words of someone with the need.
- Dating a LinkedIn or X post from the search snippet or the page "2w" label: the id is exact.
- Retyping a quote: copy it from the page; `verify_people.py` compares it with the cache.
- Counting a list row or a registry row as a signal.
- Any scraping behind a login, or a collector that needs a paid key.
