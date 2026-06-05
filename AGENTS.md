# fog-agents, agent briefing

This repo contains 8 focused AI agents for early-stage founders working on growth (shared project context, market signal, first users, SEO, landing page, cold outreach, carousel building, static ads), plus a `_template-agent` scaffold to fork.

If you are an AI agent reading this on first open, you have everything you need below.

## Repo layout

- `agents/<name>/`, one folder per agent.
  - `AGENT_<NAME>.md`, the workflow to follow. Start here.
  - `README.md`, quick description, inputs, outputs.
  - `config.example.json`, copy to `config.json` and fill in.
  - `skills/<skill-name>/SKILL.md`, Anthropic Agent Skills the workflow loads at specific steps.
  - `assets/`, `references/`, frameworks and templates the workflow uses.

## Running an agent

When the user asks to run an agent named `X`:

1. Read `agents/X/AGENT_X.md` from start to finish before doing anything.
2. If a `skills/` folder exists, the workflow tells you which `SKILL.md` to load at each step. Load only the skill listed for the current step.
3. Inputs come from `agents/X/config.json` (if present) or directly from the user.
4. Write the agent output report into the user project, not into this repo. The default output path is `<project-root>/<project-slug>/<agent-name>/<label>-<YYYYMMDD>.md`.
5. Honor the failure modes and stop conditions documented in `AGENT_X.md`.

## Available agents

| Agent | Use case |
|-------|----------|
| `project-context` | Run-once setup. Shared brand (colors, fonts, logo, site assets) + business context every other agent reuses. |
| `market-signal` | Mine real user discourse before writing copy or building. |
| `first-users-hunter` | Map where the first 10 to 50 users hang out. |
| `seo-audit` | One-shot SEO snapshot when traffic dips. |
| `landing-page-analyzer` | CRO heuristic audit on a single page. |
| `cold-outreach-builder` | Sequence + per-prospect personalization. |
| `carousel-builder` | LinkedIn / Instagram brand-consistent carousel from a chat prompt. |
| `static-ads-builder` | Funnel-aware static Meta / Instagram ad creatives rendered on fal.ai with real brand assets, behind two budget gates. |

Plus `_template-agent`, the canonical scaffold to fork when building your own.

## CLIs the agents expect

Most agents call CLIs from [`the20100/cli-skills`](https://github.com/the20100/cli-skills): `exa`, `firecrawl`, `gsc`, `perplexity`, `instantly`. Each agent `AGENT_<NAME>.md` lists which API keys it needs in the environment.

## Hard rules for any AI agent working in this repo

- Stay harness-agnostic. Do not introduce Claude Code, Cursor, Codex, or Gemini specific tool calls into agent workflows. The stack must run on all four.
- Do not paraphrase verbatim user quotes. Agents like `market-signal` rely on quotes being literal, with permalinks.
- No absolute paths to a single user machine. Use POSIX paths from the user chosen project root.
- When in doubt, follow `AGENT_<NAME>.md` over your own intuition.

## License

Apache 2.0. See `LICENSE` and `NOTICE`.
