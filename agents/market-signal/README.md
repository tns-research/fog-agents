# market-signal

> Scan Reddit, X, niche forums, Hacker News, and product reviews for what real users actually say about a market. Output: sentiment, top issues, psychographic profile, and 15 to 20 verbatim quotes.

**Run before** writing copy or building features. Don't guess what users feel. Read what they wrote.

## What you get

- A markdown report with quantitative data (sentiment %, top issues by mention frequency).
- A psychographic profile in users' own words.
- 15 to 20 verbatim quotes with source URLs.
- 3 prioritized recommendations.

Saved to `<your-projects-root>/<project>/market-signal/market-signal-<YYYYMMDD>.md`.

## Quick start

```bash
# 1. Install the CLIs (once, reused across the whole stack)
git clone https://github.com/the20100/cli-skills.git ~/cli-skills
export PATH="$HOME/cli-skills/exa-cli/bin:$HOME/cli-skills/firecrawl-cli/bin:$HOME/cli-skills/perplexity-cli/bin:$PATH"

# 2. Set the API keys
export EXA_API_KEY="..."
export FIRECRAWL_API_KEY="..."
export PERPLEXITY_API_KEY="..."   # optional

# 3. Get API keys
#    - exa.ai          → https://dashboard.exa.ai/api-keys
#    - firecrawl.dev   → https://www.firecrawl.dev/app/api-keys
#    - perplexity      → https://www.perplexity.ai/settings/api
```

## Run it

In your AI coding harness (Claude Code, Cursor, Codex, Gemini), point at this folder and ask in plain language:

> "Run the market-signal agent at `agents/market-signal/`. Market: freelance invoicing tools for designers. Language: en."

The harness reads `AGENT_MARKET_SIGNAL.md`, runs the workflow, and writes the report.

## Inputs

| Input | Required | Default | Notes |
|-------|----------|---------|-------|
| `market` | yes | n/a | the market or product category |
| `language` | no | `en` | `en`, `fr`, or `both` |
| `geography` | no | `global` | optional geo focus |
| `depth` | no | `standard` | `quick` / `standard` / `deep` |

## Per-project config

Persist parameters in:
```
<your-projects-root>/<project>/market-signal/config.json
```
The agent creates this file on first run from `config.example.json`.

## Required tools

| CLI | Purpose | Setup |
|-----|---------|-------|
| `exa` | semantic search | `~/cli-skills/exa-cli/README.md` |
| `firecrawl` | URL → clean markdown | `~/cli-skills/firecrawl-cli/README.md` |
| `perplexity` | optional synthesis | `~/cli-skills/perplexity-cli/README.md` |

## Read more

- Full agent spec: [`AGENT_MARKET_SIGNAL.md`](./AGENT_MARKET_SIGNAL.md)
- Output skeleton: [`assets/output-template.md`](./assets/output-template.md)
- API references: [`references/README.md`](./references/README.md)

## License

Apache 2.0.
