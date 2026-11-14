# first-users-hunter

> People who asked for what you build this month, one row each: the dated signal with its link and verbatim words, proof they post now, why they fit, and the first message written for them. Handed to cold-outreach-builder as is.

**Run after** idea validation, when you need ten real conversations this week rather than a list of places.

## What you get

- `people-<YYYYMMDD>.jsonl`, one line per person, validated by [`assets/person.schema.json`](assets/person.schema.json):
  - the **signal**: type (`ask`, `switch`, `complaint`, `question`, `trigger`, `event`, `build`), URL, date, verbatim excerpt checked against the cached page, community;
  - the **activity proof**: at least 2 weighted own posts in the window, dates decoded from LinkedIn and X post ids or read from the APIs; people not proven active are left out;
  - the **fit** reason with its source, a **score** computed by script from [`assets/criteria.json`](assets/criteria.json);
  - **touch 1** (a reply where the signal was said, no pitch, no link) and **touch 2** (DM, connection note or event introduction).
- `first-touches-<YYYYMMDD>.md`: the messages to send, by person, with the signal link.
- `prospects-<YYYYMMDD>.csv` and `handoff-<YYYYMMDD>/`: the prospect list in the [`shared/handoffs.md`](../../shared/handoffs.md) columns plus the signal columns, and one cold-outreach-builder dossier per person with its cached page. cold-outreach-builder verifies them with its own scripts without researching again.
- A report: dropped people with reasons, the channel map derived from where the people spoke, activity gates, ICE scoring and 14-day experiments, source health.
- `ledger.csv`: who was listed or approached; the next run skips them unless they posted a newer signal.

## Sources (all free)

| Source | How | Key |
|--------|-----|-----|
| Hacker News | Algolia API | none |
| GitHub issues | search API | none (discussions: free `GITHUB_TOKEN`) |
| Reddit | official OAuth | free script app (`REDDIT_CLIENT_ID`, `REDDIT_CLIENT_SECRET`) |
| Luma | public city and event pages | none |
| Notion and folk lists | public endpoints of published lists | none |
| French company registry | `recherche-entreprises.api.gouv.fr` | none |
| LinkedIn and X posts | your harness's web search, dated from the post ids | none |
| Closed groups (Slack, Discord, WhatsApp) | your screenshots | none |

Not used, because they fail from a server: anonymous Reddit JSON (403), read.cv (closed) and Discord scraping (login wall). No email finder, no SMTP check, no paid API.

## Run it

In Claude Code, Cursor, Codex or Gemini:

> "Run the first-users-hunter agent at `agents/first-users-hunter/`. Idea: a scheduling tool for physiotherapists. Target user: independent physiotherapists in France."

The deterministic part runs alone too:

```bash
python3 scripts/pipeline.py --config <project>/first-users-hunter/config.json --run-dir <project>/first-users-hunter/run-<YYYYMMDD>
python3 scripts/verify_people.py <project>/first-users-hunter/people-<YYYYMMDD>.jsonl --run-dir <run>
python3 scripts/export_handoff.py <project>/first-users-hunter/people-<YYYYMMDD>.jsonl --run-dir <run> --out-dir <project>/first-users-hunter
```

Scripts and tests: [`scripts/README.md`](scripts/README.md). Example run with fictional people: [`examples/swanbase-preseed-founders-20261012/`](examples/swanbase-preseed-founders-20261012/).

## Inputs

If you ran [`project-context`](../project-context/) first, `idea`, `target_user`, `geography` and `language` are prefilled.

| Input | Required | Default |
|-------|----------|---------|
| `idea` | yes | project-context |
| `target_user` | yes | project-context |
| `geography` | no | `global` |
| `language` | no | `en` |
| `icp_keywords` | no | derived from the target user and pains |
| `founder.handles`, `founder.weekly_hours` | no | none, 3 |
| `sources` | no | HN, GitHub, Luma, manual on |

## Per-project config

```
<your-projects-root>/<project>/first-users-hunter/config.json
```

From [`config.example.json`](config.example.json).

## Tools

| Capability | Default | Without it |
|------------|---------|------------|
| `community_search` | the collectors in `scripts/collectors/` | sources without a key are skipped and listed |
| `web_search` | host web search | LinkedIn and X people only from URLs you give |
| `scrape` | host web fetch, `scripts/cache_page.py` | you paste the page text |
| `vision` | host model | closed groups from pasted text |

Full list of providers: [`shared/tools.md`](../../shared/tools.md).

## Read more

- Workflow: [`AGENT_FIRST_USERS_HUNTER.md`](AGENT_FIRST_USERS_HUNTER.md)
- Report skeleton: [`assets/output-template.md`](assets/output-template.md)
- Sources and endpoints: [`references/README.md`](references/README.md)

## License

Apache 2.0.
