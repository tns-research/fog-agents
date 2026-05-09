# cold-outreach-builder

> Build a complete cold outreach sequence (email or LinkedIn) for a specific ICP. ICP research → 4 to 7 messages with widening-gap cadence → per-prospect personalization → CSV ready to import.

**Run when:** you have a sharp ICP and need 50 to 200 first conversations.

**Don't use it for:** generic spray-and-pray to 5000 contacts. The value is per-prospect personalization that's actually personal.

## What you get

Three deliverables saved to `<your-projects-root>/<project>/cold-outreach-builder/outreach-<YYYYMMDD>/`:

1. `sequence-templates.md`: 4 to 7 message templates with `{{tokens}}` and widening-gap send schedule.
2. `personalized-leads.csv`: your lead list + 2 personalization columns per prospect.
3. `import-instructions.md`: how to upload to Instantly. Other CSV-based outbound tools follow the same column conventions.
4. `outreach-summary-<YYYYMMDD>.md`: the strategic report (Cialdini lever map, deliverability check, banned-pattern audit).

## Quick start

```bash
git clone https://github.com/the20100/cli-skills.git ~/cli-skills
export PATH="$HOME/cli-skills/exa-cli/bin:$HOME/cli-skills/firecrawl-cli/bin:$HOME/cli-skills/instantly-cli/bin:$PATH"

export EXA_API_KEY="..."
export FIRECRAWL_API_KEY="..."
export INSTANTLY_API_KEY="..."   # optional
```

## Run it

> "Run the cold-outreach-builder agent at `agents/cold-outreach-builder/`. Offer: 'we ship a CRM that auto-summarizes every customer call so founders stop losing deal context'. ICP: B2B SaaS founders, 10 to 50 employees, France. Goal: book 15-min calls. Channel: email. Language: fr. Seniority: founder. Prospect list: ~/work/acme/leads/q2-list.csv"

## Inputs

| Input | Required | Default |
|-------|----------|---------|
| `offer` | yes | n/a |
| `icp` | yes | n/a |
| `goal` | yes | n/a |
| `channel` | yes | `email` |
| `prospect_list` | no | n/a |
| `language` | no | `en` |
| `seniority` | no | `mixed` |

## Per-project config

```
<your-projects-root>/<project>/cold-outreach-builder/config.json
```

## Required tools

| CLI | Purpose |
|-----|---------|
| `exa` | ICP language scan |
| `firecrawl` | per-prospect personalization (scrape sites, posts, About pages) |
| `instantly` | optional: push the campaign into Instantly.ai |

## Read more

- Full agent spec: [`AGENT_COLD_OUTREACH_BUILDER.md`](./AGENT_COLD_OUTREACH_BUILDER.md)
- Output skeleton: [`assets/output-template.md`](./assets/output-template.md)
- API references: [`references/README.md`](./references/README.md)

## License

Apache 2.0.
