---
name: researching-prospects
description: Builds one verified dossier per prospect before any message is written. Each prospect gets a research brief; sub-agents work the briefs in waves of three when the harness has them, otherwise the session works them one after the other. Every fact is dated, carries the URL it was read on and a verbatim excerpt of that page, and every page is cached locally so a script can check the excerpt is really there. LinkedIn profiles are never scraped; post dates come from the post id. Use at Steps 4 and 5 of cold-outreach-builder, or whenever a prospect list needs facts to open on. Triggers on "research the prospects", "personalize", "dossier", "find something to say about them".
license: Apache-2.0
compatibility: Claude Code, Cursor, Codex CLI, Gemini CLI
metadata:
  version: "2.0"
---

# researching-prospects

A cold message opens on something true about the reader, or it reads as mail merge. This skill produces that something as data a script can check: `dossiers/<id>/prospect.json`, contract [`../../assets/prospect.schema.json`](../../assets/prospect.schema.json). The model finds and reads; [`../../scripts/verify_dossiers.py`](../../scripts/verify_dossiers.py) decides whether a fact stands; [`../../scripts/score_prospects.py`](../../scripts/score_prospects.py) decides the tier. The model never scores a prospect.

## 1. Prepare the briefs

```bash
python3 scripts/run_dossiers.py prepare --leads <lead-list.csv> --run-dir <run> \
  --state <project>/cold-outreach-builder/state/state.json
```

`<run>` is `<project>/cold-outreach-builder/outreach-<YYYYMMDD>`. The command writes `<run>/leads.csv` (with a `prospect_id` per row), drops leads the state file excludes (already in a sequence, suppressed, touched under the recontact delay) into `<run>/excluded-already-contacted.csv`, and writes one `<run>/dossiers/<id>/brief.md` per remaining prospect. A brief holds everything a fresh worker needs: the lead row, the output path, the rules below, the cache and verify commands.

## 2. Work the briefs

Take the first option available:

| Option | How |
|--------|-----|
| Sub-agents of the harness | Start one sub-agent per brief, three at a time, each with only its `brief.md` as input. Wait for the wave, then run `python3 scripts/run_dossiers.py status --run-dir <run>`: it reads the files on disk, never the sub-agents' messages. Start the next wave. |
| A model CLI | `python3 scripts/run_dossiers.py run --run-dir <run> --agent-cmd "<cli that reads a prompt on stdin>"` (or set `FOG_AGENT_CMD`). Three at a time, a log per prospect in `dossiers/<id>/agent.log`. |
| Sequential | Work the briefs one after the other in this session, with the same rules and commands. `status` tells which remain after an interruption. |

Resume is free: a prospect whose `prospect.json` validates is never redone. A prospect whose task failed twice is worked in this session.

## 3. Rules for one dossier

**Where to look, in this order.** The company site and blog, press and announcements, public registries (company creation, filings), job posts, talks and podcasts pages, public posts (`linkedin.com/posts/...`, `x.com/<user>/status/...`), the person's own site or newsletter. The capability is `scrape` (and `web_search` to find the pages), any provider of [`../../../../shared/tools.md`](../../../../shared/tools.md).

**Never a LinkedIn profile or company page.** They sit behind a login wall and their terms forbid scraping; `cache_page.py` refuses them. Public posts are fine: find them with a web search such as `site:linkedin.com/posts "<first> <last>"`. See [`../../references/linkedin-public-posts.md`](../../references/linkedin-public-posts.md) for the date and the owner a post URL carries.

**Cache before you use.** Every page goes through the cache before a fact is taken from it:

```bash
python3 scripts/cache_page.py --cache <run>/cache <url>
python3 scripts/cache_page.py --cache <run>/cache --url <url> --from-file page.md   # text from another provider
```

A page that returns no text (JavaScript, wall) needs another scrape provider, then `--from-file`. Text the founder pastes goes in the same way.

**A fact** (`facts[]`):

- `id` `f1`, `f2`...; `type`: `funding`, `company_creation`, `launch`, `hiring`, `job_change`, `post`, `talk`, `press`, `other`.
- `claim`: the fact in one sentence, your words.
- `date`: `YYYY-MM-DD`, read on the page, or from the post id (`date_source: post_id`). A fact without a readable date is not a fact for this agent.
- `source_url`: the page it was read on, cached.
- `excerpt`: words copied verbatim from that page, 15 to 400 characters. Copy, never paraphrase: the check compares strings (case, quotes, dashes and spaces folded).
- `owner`: `self` (the person wrote or said it), `company`, `third_party`.

**What to look for.** First what the person or the company did in the last 120 days (raise, creation, launch, hiring, new role): one of these makes a tier A. Then their own posts and talks. Two to five facts are enough; stop there.

**Language and register.** `language` is what the person writes in publicly. For French, `register` is the form of address they use in public writing (`tu` or `vous`), with `register_source_url`; never infer it from age or seniority.

**Relationship and disqualifiers.** `relationship` is `none` unless the lead list or the founder says otherwise (`known`, `customer`, `investor`, `partner`, `in_conversation`): those go to tier C, the founder writes to them personally. A disqualifier (wrong segment, company closed, explicit "no cold email" on their page) goes in `disqualifiers` with its URL.

**Email.** Keep the one from the lead list (`email_source_url: lead_list`), or one published on a page (`email_source_url` = that page, checked). Never guess an address from a naming pattern. Never verify one by an SMTP probe.

**Nothing true and dated found.** Write the dossier with `"facts": []`. The prospect goes to tier C: that is a valid result, never a reason to invent or to stretch an old fact.

## 4. Verify, then score

```bash
python3 scripts/verify_dossiers.py <run>/dossiers --cache <run>/cache
python3 scripts/score_prospects.py <run>/dossiers
```

`verify_dossiers.py` exits 1 while a dossier has an error (`excerpt-not-found`, `not-cached`, `post-date`, `owner-mismatch`, `future-date`, `email-not-on-page`, `schema`). Fix the dossier: copy the exact words, cache the page, correct the date, or delete the fact. Never edit the check or the cache text. Stale facts (older than `freshness.fact_max_age_days`) stay as warnings: they never score and never become a hook.

`score_prospects.py` writes `<run>/tiers.json` with, per prospect, the score, the tier and the reason, and the strongest verified fact as hook candidate:

| Tier | Rule (defaults of `assets/criteria.example.json`) | What the prospect receives |
|------|------|------|
| A | score at least 65 and a strong fact (raise, creation, launch, hiring, new role) under 120 days | every step written for this person around that fact |
| B | score at least 35 and at least one verified fact | the shared template, with a hook sentence built on a verified fact |
| C | anything else, with the reason | nothing: listed in the report, never a generic message |

The project copy of the grid lives in `<project>/cold-outreach-builder/criteria.json` (`--criteria`).

## Failure modes

- **Sub-agent returns a message but no file** → it did not finish; `status` shows it pending. Run it again once, then work it in this session.
- **Every fact of a prospect fails verification** → the dossier is rewritten from the cached pages, not from memory. If the pages do not hold the fact, the fact goes.
- **The founder supplies a fact by chat** (a meeting, a mutual contact) → `date_source: founder`, `source_url` of a page that shows it when one exists; otherwise keep it out of the message and note it in `notes` for the founder's own follow-up.
- **No scrape provider at all** → the founder pastes the pages; `--from-file` caches them. Without pages, every prospect is tier C and the report says why.
