# seo-audit

> One-shot SEO + AEO audit for a single domain. GSC data + live SERP (SERPER.dev) + AI Overview / Perplexity citation audit + pillar-cluster topology + prioritized fix list with concrete title/meta rewrites.

**Run when:** traffic dipped, before a refresh sprint, after a Google update, or to find out whether you're cited in AI Overviews / Perplexity for your target queries.

**Don't use it for:** continuous SEO monitoring or competitive tracking. This is a snapshot, not a pipeline.

## What you get

- Four opportunity bands: low-hanging (positions 4-15), decay candidates, CTR underperformers vs position-band benchmark, lost queries.
- Live SERP intent-gap analysis per target query (top 10 + AI Overview + PAA + featured snippet).
- AI Overview / Perplexity / ChatGPT citation diagnosis ("ranks but uncited" gap).
- Pillar-and-cluster topic map with cannibalization detection.
- E-E-A-T 4-signal audit per ranking page.
- 10 to 15 prioritized fixes (impact × ease), with concrete title/meta rewrites and AEO-pattern recommendations.
- 90-day topical-authority roadmap.

Saved to `<your-projects-root>/<project>/seo-audit/seo-audit-<YYYYMMDD>.md` plus a JSON sidecar.

## Quick start

```bash
# CLIs
git clone https://github.com/the20100/cli-skills.git ~/cli-skills
export PATH="$HOME/cli-skills/firecrawl-cli/bin:$HOME/cli-skills/perplexity-cli/bin:$PATH"

# gsc binary (Go install, one-time)
git clone https://github.com/the20100/gsc-cli /tmp/gsc-cli
cd /tmp/gsc-cli && go build -o gsc . && sudo mv gsc /usr/local/bin/
cd - && rm -rf /tmp/gsc-cli

# Auth (one-time OAuth)
gsc auth setup

# API keys
export FIRECRAWL_API_KEY="..."    # https://www.firecrawl.dev/app/api-keys
export SERPER_API_KEY="..."       # https://serper.dev (free tier: 2500 queries/month, exposes aiOverview field)
export PERPLEXITY_API_KEY="..."   # https://www.perplexity.ai/settings/api (for AEO citation audit)

# Optional: Python deps for the bundled SERP analyzer script
pip install -r agents/seo-audit/scripts/requirements.txt
```

You also need:
- A **verified GSC property** for the domain.
- A **Google Cloud OAuth client** (Desktop app credentials): see `gsc auth setup` output.

## Run it

> "Run the seo-audit agent at `agents/seo-audit/`. Domain: https://acme.com/. Target queries: invoice software for designers, freelance billing app, accounting tool freelancer."

## Inputs

| Input | Required | Default |
|-------|----------|---------|
| `domain` | yes | n/a |
| `target_queries` | yes | n/a |
| `period_days` | no | `90` |
| `country` | no | `all` |
| `language` | no | `en` |

## Per-project config

```
<your-projects-root>/<project>/seo-audit/config.json
```

## Required tools

| Tool | Purpose | Setup |
|------|---------|-------|
| `gsc` | Search Console queries, sitemaps, URL inspection | https://github.com/the20100/cli-skills/tree/main/g-search-console-cli |
| `firecrawl` | competitor page crawl + SERP fallback | https://github.com/the20100/cli-skills/tree/main/firecrawl |
| SERPER.dev | live SERP + AI Overview citation field (free tier 2500 q/mo) | https://serper.dev |
| `perplexity` | programmatic Perplexity citation audit | https://github.com/the20100/cli-skills/tree/main/perplexity-cli |

## Read more

- Full agent spec: [`AGENT_SEO_AUDIT.md`](./AGENT_SEO_AUDIT.md)
- Output skeleton: [`assets/output-template.md`](./assets/output-template.md)
- API references: [`references/README.md`](./references/README.md)

## License

Apache 2.0.
