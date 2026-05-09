# first-users-hunter

> Map where your first 10 to 50 users actually hang out, pre-filter ghost towns out, score the survivors with ICE, design 14-day falsifiable experiments per channel, write outreach templates.

**Run after** initial idea validation. Don't broadcast to everyone. Find the watering holes.

## What you get

- Target user profile (3 lines).
- Channel inventory: 8 to 12 communities + 5 to 8 niche platforms + 3 to 6 IRL events.
- 10 to 20 LinkedIn-adjacent profiles (real humans, with rationale).
- Activity gate filter: 6 community-health gates + 3 dead-giveaway anti-signals applied before scoring.
- Channel scoring with **ICE multiplicative** (Impact × Confidence × Ease, 1-cap veto).
- Top 3 to 5 channels turned into **14-day falsifiable experiments** (hypothesis + primary metric + success threshold + stop-rule + AARRR-stage mapping).
- One outreach template per top channel.

Saved to `<your-projects-root>/<project>/first-users-hunter/first-users-<YYYYMMDD>.md`.

## Quick start

```bash
git clone https://github.com/the20100/cli-skills.git ~/cli-skills
export PATH="$HOME/cli-skills/exa-cli/bin:$HOME/cli-skills/firecrawl-cli/bin:$PATH"

export EXA_API_KEY="..."        # https://dashboard.exa.ai/api-keys
export FIRECRAWL_API_KEY="..."  # https://www.firecrawl.dev/app/api-keys
```

## Run it

In Claude Code / Cursor / Codex / Gemini:

> "Run the first-users-hunter agent at `agents/first-users-hunter/`. Idea: a CRM that auto-summarises every customer call. Target user: B2B SaaS founders 10 to 50 employees, France."

## Inputs

| Input | Required | Default |
|-------|----------|---------|
| `idea` | yes | n/a |
| `target_user` | yes | n/a |
| `geography` | no | `global` |
| `language` | no | `en` |

## Per-project config

```
<your-projects-root>/<project>/first-users-hunter/config.json
```

## Required tools

| CLI | Purpose |
|-----|---------|
| `exa` | community + event + profile discovery |
| `firecrawl` | activity-level verification on community pages |

## Read more

- Full agent spec: [`AGENT_FIRST_USERS_HUNTER.md`](./AGENT_FIRST_USERS_HUNTER.md)
- Output skeleton: [`assets/output-template.md`](./assets/output-template.md)
- API references: [`references/README.md`](./references/README.md)

## License

Apache 2.0.
