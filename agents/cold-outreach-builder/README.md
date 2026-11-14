# cold-outreach-builder

> Cold outreach where every first message opens on a true, dated, sourced fact about the reader. One dossier per prospect, facts checked against the cached page by script, tiers scored by a grid, a lint loop until zero BLOCK, a sender check by DNS, a CSV any sequencer imports, and a memory of who was contacted and what they answered. The agent never sends anything.

**Run when:** you have a sharp ICP and 20 to 200 people to reach, or replies to triage from a sequence you already sent.

**Don't use it for:** mass sends, purchased lists, or people you already know (they go to tier C: write to them yourself).

## How it works

1. **Dossiers.** One research brief per prospect, worked by sub-agents three at a time (or one after the other). Every page read is cached; every fact carries a date, a URL and a verbatim excerpt. LinkedIn profiles are never scraped: public posts are dated from their id.
2. **Verification.** `verify_dossiers.py` checks each excerpt is really in the cached page, the date, the post id, the post owner. Facts that fail are fixed or dropped.
3. **Tiers.** `score_prospects.py` applies a JSON grid to verified facts only. **A**: a strong fact under 120 days (raise, company creation, launch, hiring, new role), every message written for the person. **B**: an older or weaker fact, the template plus a hook built on it. **C**: nothing true and dated, or a known relationship: no message, listed with the reason.
4. **Writing.** Templates, hooks and tier A messages, one Cialdini lever per step, the claims gate on every line, `{{sender_first_name}}` as signature.
5. **Lint loop.** `lint_outreach.py` runs the stack's shared writing gate and the outreach patterns on every message of every prospect, then checks what no single-text linter sees: the same address twice, identical or near-identical hooks between prospects, unfilled variables, length, links, subject, the sourced fact in message 1, numbers without a source, the signature. Fix, rebuild, rerun until 0 BLOCK.
6. **Sender check.** `check_sender.py` reads SPF, DKIM, DMARC and MX by DNS only. No SMTP probe, ever.
7. **After sending.** Register the export in the project state; later, export your replies (CSV or `.eml`), `ingest_replies.py` classifies them (positive, negative, out of office, off topic, bounce) with the sentence that decided, stops or pauses each sequence, suppresses who asked, and the next run skips everyone already contacted.

You validate the export before importing it; that is the only stop.

## What you get

In `<your-projects-root>/<project>/cold-outreach-builder/outreach-<YYYYMMDD>/`: `sequence-export.csv` (one row per prospect, every step written or rendered, with the hook's fact and source URL), the dossiers and their cache, `tiers.json`, `messages.json`, `lint.json`, `sender-check.json`, `import-instructions.md`, and the report `outreach-summary-<YYYYMMDD>.md`. Across runs: `state/state.json`, `replies-<YYYYMMDD>.md`, `followups-<YYYYMMDD>.md`.

## Quick start

No API key needed: Python 3.9+ standard library only. Replay the example and the tests:

```bash
cd agents/cold-outreach-builder
python3 tests/run_tests.py          # offline, about 150 checks
```

The example ([`examples/swanbase-preseed-founders-20261012/`](examples/swanbase-preseed-founders-20261012/)) shows a tier A, a tier B and a tier C prospect, fictional, end to end; its [`preview.md`](examples/swanbase-preseed-founders-20261012/preview.md) holds the rendered messages.

Then, from your AI coding harness:

> "Run cold-outreach-builder for project acme. Offer: 'we ship a CRM that auto-summarizes every customer call so founders stop losing deal context'. ICP: B2B SaaS founders, 10 to 50 employees, France. Goal: book 15-min calls. Channel: email. Sender domain: outreach.acme.example, DKIM selector s1. Prospect list: leads/q4-list.csv"

The agent follows [`AGENT_COLD_OUTREACH_BUILDER.md`](AGENT_COLD_OUTREACH_BUILDER.md).

## Inputs

If you ran [`project-context`](../project-context/) first, `offer`, `icp` and `language` are prefilled. Proof in the messages comes only from your `positioning.proof` list or a source URL. Per-project settings: [`config.example.json`](config.example.json) (sender domain, DKIM selector, your first name for the signature, kept in your private project folder).

| Input | Required | Default |
|-------|----------|---------|
| `offer` | yes | from project-context |
| `icp` | yes | from project-context |
| `goal` | no | `give feedback` |
| `channel` | no | `email` |
| `prospect_list` | no | latest `first-users-hunter` prospects file |
| `language` | no | `en` (per prospect, the language they write in) |
| `sender_domain`, `dkim_selector` | for the sender check | not run |

## Tools

| Capability | Used for | Free fallback |
|------------|----------|---------------|
| `web_search`, `scrape` | prospect research | host web search and fetch, `cache_page.py` (urllib), pasted pages |
| `community_search` | ICP language | HN Algolia, Arctic Shift (Reddit archive), host web search |
| `email_finder` | missing emails | none: rows listed for you to enrich |
| `critic` | fresh-eyes review | second session, or "not run" |

Full list of providers: [`shared/tools.md`](../../shared/tools.md). Scripts: [`scripts/README.md`](scripts/README.md).

## Limits

- Facts come from public pages only; search engines index part of LinkedIn. A prospect with nothing public and dated is tier C.
- The agent never sends, never connects to a mailbox or a sequencer; you export replies as files.
- No reply rate is predicted, and no variant is declared a winner: compare classified replies with their sample size.

## Read more

- Workflow: [`AGENT_COLD_OUTREACH_BUILDER.md`](AGENT_COLD_OUTREACH_BUILDER.md)
- Report skeleton: [`assets/output-template.md`](assets/output-template.md)
- References: [`references/README.md`](references/README.md)

## License

Apache 2.0.
