---
name: auditing-geo-aeo
description: Measures how answer engines (ChatGPT, Perplexity, Claude, Google AI Overviews, Gemini) talk about the brand, as a panel and not as one capture. First access: which AI crawlers robots.txt lets in (GPTBot, OAI-SearchBot, ChatGPT-User, ClaudeBot, Claude-SearchBot, PerplexityBot, Google-Extended, CCBot...), Content-Signal lines, and pages almost empty without JavaScript. Then a panel of real questions per topic, several draws per question and surface collected through the ai_answers capability (an API, any answer-engine CLI the founder has, or the founder pasting answers from prefilled links), and scripts/geo_panel.py computes mention rate, citation rate, share of voice against named competitors, citation share and the spread between draws. A surface nobody could read is Unverified, never 0 %. Triggers on "GEO", "AEO", "AI Overview", "cited by ChatGPT", "Perplexity", "answer engine", "share of voice", "GPTBot", "AI crawlers".
license: Apache-2.0
compatibility: Claude Code, Cursor, Codex CLI, Gemini CLI
metadata:
  version: "2.0"
allowed-tools: Read Write Bash(python3:*)
---

# auditing-geo-aeo

Generated answers vary from one draw to the next: one capture per query, presented as a fact, can say "never cited" for a brand cited two times out of three. And a site that blocks the crawlers of an answer engine, or that shows an empty page without JavaScript, cannot be cited whatever its content. This skill checks access first, then measures a panel with several draws, by script.

## When to invoke

- Step 7 of an audit run, or alone (`geo` mode) to re-run the panel and follow its trend.
- When the founder asks "are we cited by ChatGPT / Perplexity / AI Overviews for X?".

## Capability `ai_answers`

Answers of an answer engine to a question, with the sources it cites. Resolved at Step 0 like every capability ([`../../../../shared/skills/resolving-tools/SKILL.md`](../../../../shared/skills/resolving-tools/SKILL.md)), per surface.

| Tier | Provider | How |
|------|----------|-----|
| API | Perplexity API | `PERPLEXITY_API_KEY`, `geo_panel.py run --provider perplexity` (model `sonar` by default): answers and citations |
| API | any other answer API the founder pays for (OpenAI, Anthropic or Gemini with web search, a GEO tool) | wrapped in a small CLI and used through `--provider command` |
| Local | an answer-engine CLI the founder already has | `geo_panel.py run --provider command --cmd "<cli>"`: the question arrives on stdin, the CLI prints text (URLs in it count as citations) or `{"answer": ..., "citations": [...]}` |
| Built-in | none | the host's web search returns result lists, not answers: never counted as a surface |
| Manual | founder | `geo_panel.py links` (prefilled ChatGPT, Perplexity, Claude and Google links, one click per question) and `template` (a capture file); the founder pastes each answer and its sources, `import` reads it |

Every API or metered CLI call goes through the spend gate: `run` prints the number of calls and exits 1 without `--confirm-spend`. The agent asks once (Step 0 message) and passes the flag only after the founder agreed. A model CLI without web search answers from its training data: label the surface that way ("model only, no retrieval"); its citation rate is n/a.

Without the capability: the panel is Unverified for that surface, the access check still runs.

## Step A: access (always, free)

```bash
python3 scripts/geo_panel.py robots --site <domain> --crawl <run>/crawl.jsonl --paths /,/blog/ --out-dir <run>/geo/
```

- One row per AI user agent of `assets/ai-crawlers.json` (operator, purpose: training, search, user, control; link to the operator's documentation), the robots.txt group that applies and whether each path is allowed.
- Search and user agents blocked on `/` come first in the report: their engine cannot fetch the page to cite it. Blocking training agents only is a legitimate choice; say what it does and does not block.
- `Content-Signal` lines are a stated preference, not an access rule.
- Pages flagged `thin-raw-html` by the crawl: several AI crawlers do not run JavaScript and read them almost empty.
- A CDN or firewall can block bots that robots.txt allows; when answers on every surface never cite the site although it ranks, say that the server logs or the CDN bot settings are the next thing to check.

Done when `ai-access.json` and `ai-access.md` exist.

## Step B: write the panel

`<project>/seo-audit/geo/panel.json` (example: `tests/fixtures/geo/panel.json`):

- `brand`: name, aliases, domains. `competitors`: the ones the founder names, else those that dominate the SERP of the target queries; never more than 5.
- 3 to 6 topics, 10 to 30 questions in all, written as a user asks an assistant ("Which pre-seed accelerators in Paris accept first-time founders?"), not as keywords.
- Every question has a `source`: `icp.jobs[]` or `icp.pains[]` of project-context, a People also ask question or an autocomplete suggestion of the SERP step, a market-signal quote ID (its verbatim wording), or the founder. A question nobody asked is not in the panel.
- `draws`: 3 by default (config `geo.draws`). `surfaces`: the ones resolved at Step 0, plus any the founder cares about even without a provider (they will show Unverified).
- Keep the same panel from run to run: change it only by adding questions, so the trend stays comparable.

```bash
python3 scripts/geo_panel.py check --panel <project>/seo-audit/geo/panel.json
```

Done when `check` exits 0.

## Step C: collect

Answers go to `<project>/seo-audit/geo/answers-<YYYYMMDD>.jsonl`, one line per question, surface and draw.

```bash
# API or CLI, after the spend gate
python3 scripts/geo_panel.py run --panel <panel> --surface perplexity --provider perplexity --out <answers> --confirm-spend
python3 scripts/geo_panel.py run --panel <panel> --surface chatgpt --provider command --cmd "<founder's cli>" --out <answers> --confirm-spend
# Manual: links and capture file sent in the Step 0 message, read back when the founder drops it
python3 scripts/geo_panel.py links --panel <panel> --out <project>/seo-audit/geo/links.md
python3 scripts/geo_panel.py template --panel <panel> --surface chatgpt --out <project>/seo-audit/geo/capture-chatgpt.md
python3 scripts/geo_panel.py import --capture <project>/seo-audit/geo/capture-chatgpt.md --out <answers>
```

`run` is resumable: it skips what the file already holds. Each draw is a new conversation, signed out where possible; record the country the answers were read from in Methodology.

Done when every resolved surface has its answers, or its missing draws are listed.

## Step D: score

```bash
python3 scripts/geo_panel.py score --panel <panel> --answers <answers> --out-dir <run>/geo/ [--previous <previous run>/geo/geo-score.json]
```

`geo-score.md`, per surface, topic and question: mention rate (draws naming the brand), citation rate (draws citing a brand URL, over answers that cite anything), share of voice (brand mentions against the competitors'), citation share, spread between draws, `k/n` per question with "same result every draw", most cited domains, incomplete draws, trend against the previous panel. Copy the surface table into the report.

Done when `geo-score.json` exists.

## Step E: diagnose and fix

Read the questions where competitors are named and the brand is not, and the domains cited instead:

| Finding | Likely cause | Fix (goes to the fix list or a brief) |
|---------|--------------|---------------------------------------|
| search agents blocked, or JavaScript shell | the engine cannot read the page | robots.txt group, server rendering of the main content |
| cited domains are forums, directories, review sites | the engine trusts third-party mentions on this topic | presence on those pages (founder's call, no fake reviews) |
| the brand's page ranks in the top 10 but is never cited | no passage answers the question directly | an answer paragraph under a question heading, sourced facts, author and dates visible (`assets/aeo-winning-patterns.md`; the page's missing signals in `eeat.json`, `assets/eeat-audit-checklist.md`) |
| a competitor is cited for a fact the brand owns | the fact is not on the brand's site in plain text | publish it with its source (facts ledger) |
| high spread between draws | the engine has no stable source on the topic | treat as an opening, re-measure next run |

Schema is never the fix on its own: it must match visible content and survive to the served HTML (`verify_served.py`).

## Anti-patterns to refuse

- One capture per question presented as a rate.
- Counting an unread surface as "not cited".
- Keywords as panel questions, or questions without a source.
- Paid GEO dashboards as a requirement: a panel, a script and the founder's own tools are enough.
- Promising citation gains from an outside percentage: the agent measures this site's panel, run after run.
