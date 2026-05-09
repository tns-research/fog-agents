---
name: _template-agent
description: Reference scaffold for every agent in the Founders Growth Agent Stack. Copy this folder, rename, and fill in. Defines the canonical layout, prompts, config flow, CLI prerequisites, skills/assets/scripts pattern, and portability rules that all stack agents must follow.
license: Apache-2.0
compatibility: Claude Code, Cursor, Codex CLI, Gemini CLI
---

# _template-agent

This is the canonical template for every agent in the **Founders Growth Agent Stack**.
Copy it, rename, fill in. Do not skip sections.

For fuller examples of a skills + assets + scripts agent in action, see `portable-agents-shared/agent-cro-heuristic` and `agent-cold-emailing` (external reference, not a dependency).

## Why a template

Every agent must look the same to a founder who has never seen the stack:

- Same folder layout.
- Same `## Step 0` / `## When to run` / `## Inputs` / `## Workflow` / `## Output` sections.
- Same install path for required CLIs.
- Same per-project config convention.

Predictability is a feature.

## Folder layout

```
my-agent/
├── AGENT_MY_AGENT.md       ← this spec (renamed)
├── README.md                ← install, prerequisites, usage examples
├── config.example.json      ← optional per-project parameters
├── skills/                  ← methodology (heuristics, scoring, taxonomies, prompts)
│   └── <skill-name>/
│       └── SKILL.md
├── assets/                  ← data the methodology operates on (lists, checklists, templates)
│   ├── output-template.md   ← deliverable format
│   └── <rule-set>.md        ← optional per-skill data
├── scripts/                 ← bundled tools (optional, only when CLI-piping is not enough)
│   ├── <bundled-tool>.py
│   ├── requirements.txt
│   └── README.md
├── references/
│   └── README.md            ← links to APIs, docs, cli-skills, foundational reads
└── examples/                ← optional anonymized real runs
    └── <agent>-example-YYYYMMDD.md
```

## Required CLI prerequisites pattern

If an agent needs a CLI (search, scraping, analytics), do **not** reimplement it.
Reference the public `cli-skills` repo and have the user install once.

In the agent README, ship this block verbatim (replace the CLI list):

```bash
# Install once, reuse across all agents in this stack
git clone https://github.com/the20100/cli-skills.git ~/cli-skills

# Add the CLIs this agent needs to your PATH
export PATH="$HOME/cli-skills/exa-cli/bin:$PATH"
export PATH="$HOME/cli-skills/firecrawl-cli/bin:$PATH"

# Set the env vars the CLIs require (see each CLI's README)
export EXA_API_KEY="..."
export FIRECRAWL_API_KEY="..."
```

The `~/cli-skills` location is a convention, not a hard rule. Any folder works as long as the binaries land on `PATH`.

## Per-project config

If the agent has parameters that change per project (brand, target market, locale, audience), persist them in the **client project folder**, not in the agent folder. This keeps agents portable.

Default convention:

```
<your-projects-root>/<project-slug>/<agent-name>/config.json
```

Example:

```
~/work/acme-saas/market-signal/config.json
```

At runtime the agent:

1. Asks the user for the project slug if not obvious from context.
2. Loads `config.json` from that folder.
3. If missing, copies `config.example.json` from the agent folder, asks for missing values in chat, writes back.

Never hard-code a single project root. Use the user's chosen one.

The `config.example.json` MUST include a top-level `_comment` field describing what the file is and where it gets copied. This makes the file self-documenting.

## Workflow contract (every agent)

Every agent's `AGENT_<NAME>.md` MUST have these sections in order:

1. `## Step 0: context resolution` (resolve project slug, load config, fill missing values, do not proceed until resolved)
2. `## When to run` (1-3 sentences, founder-readable)
3. `## Inputs needed` (list, with required/optional + defaults)
4. `## Workflow` (numbered steps, each ≤ 6 lines, each step POINTS to a `skills/<name>/SKILL.md` or `assets/<file>.md` when methodology is loaded)
5. `## Output format` (markdown skeleton or link to `assets/output-template.md`)
6. `## Output location` (path pattern using `<your-projects-root>/<project>/<agent>/...`)
7. `## Failure modes` (each entry: `**<trigger>** → <fallback action>`)

## Skills, assets, scripts: when to use which

### When to create a skill

Move methodology out of `AGENT_<NAME>.md` into `skills/<skill-name>/SKILL.md` when at least one of these is true:

- The methodology is ≥ 50 lines of heuristics, scoring rules, taxonomy, or prompt patterns
- Two or more workflow steps reference the same methodology
- The methodology evolves on a different cadence than the workflow (you'll iterate the rubric without touching the agent)

A skill is a self-contained explanation a contributor can read without opening `AGENT.md`. Body ≤ 500 lines / ~5000 tokens (Anthropic Agent Skills spec). If a skill exceeds, split via `references/` or `assets/`.

### When to bundle a script

Add a script under `scripts/` only when the work cannot be done by piping `cli-skills` CLIs. Legitimate cases:

- Browser automation (Playwright capture, screenshot stitching)
- CSV / JSON transformations (reshape data, dedupe, join)
- Custom scoring formulas applied at scale
- API quota juggling, batched fetch with retry

Not for: things `firecrawl` / `exa` / `gsc` / `perplexity` already do.

Every script ships with `requirements.txt` (or equivalent) and a one-page `README.md` with install + usage + cross-platform notes (forward slashes only, no Windows-specific commands).

**Scripts solve, don't punt**: handle errors explicitly (return defaults or specific error messages), no magic numbers (document every constant inline), forward slashes only (cross-platform).

### When to use assets

Put any list, checklist, template, taxonomy, or example into `assets/`. The methodology in the skill *references* these assets at the relevant workflow step. Loading data lazily keeps the LLM's context lean.

### When to add an example

Optional but high-value. Drop one anonymized real run per agent in `examples/<agent>-example-YYYYMMDD.md`. Single biggest reduction in LLM hallucination about output format. Use synthetic-but-realistic data if anonymization is too heavy.

## SKILL.md frontmatter (Anthropic Agent Skills spec compliance)

Every `SKILL.md` MUST use this frontmatter:

```yaml
---
name: <skill-name>
description: <what the skill does, third person>. Use when <trigger context>. <key trigger words>.
license: Apache-2.0
compatibility: Claude Code, Cursor, Codex CLI, Gemini CLI
metadata:
  version: "1.0"
allowed-tools: Bash(firecrawl:*) Bash(exa:*) Read Write
---
```

**Field rules**:

- `name`: lowercase + hyphens, ≤64 chars, no leading/trailing/double hyphens, MUST equal the parent directory name.
- `description`: third person ("Applies", "Extracts", never "I help", "You can"). Both WHAT (capability) and WHEN (trigger) must appear. Include keyword triggers a user would naturally use. ≤1024 chars. Specific, not vague.
- `allowed-tools`: optional but recommended; locks down what the skill can call.

**Naming preferences**:

- Gerund form: `scoring-channels`, `selecting-hook-angles`, `detecting-query-decay`
- Noun phrase also acceptable: `lever-audit`, `intent-gap-analysis`
- Avoid generic: `helper`, `utils`, `tools`
- Reserved words forbidden: `anthropic`, `claude`

## Cross-cutting output conventions

### C1. Dual output: JSON + Markdown

For any agent producing structured data (rankings, scoring, lists), output BOTH a `.json` file (machine-readable, lossless) AND a `.md` report (human-readable). The JSON enables re-processing without re-querying APIs (re-render the report with an updated template, diff between runs, feed into downstream agents).

### C4. Source recency cutoffs

For any agent that mines public content (`exa`, `firecrawl`), default to:

- Reddit / X / HN: last 90 days
- Blog / forum content: last 12 months
- Older content is heavily discounted in scoring

Configurable via `recency_days` in `config.json`. Stale market signal is misleading.

### C5. Verbatim preservation

When extracting quotes from sources, NEVER paraphrase. Preserve exact words, original language, with permalink + date + upvote/karma + author age. Marketing copy is mined from the corpus, not invented. "Billing friction" is what the analyst writes; "I literally cannot understand why my invoices are off by 3 cents every single month" is what the customer says. The second one becomes the headline.

## Output location convention

```
<your-projects-root>/<project-slug>/<agent-name>/<label>-<YYYYMMDD>.md
```

Example:

```
~/work/acme-saas/first-users-hunter/first-users-20260427.md
```

Rules:

- Outputs live **outside** the agent folder.
- Filename pattern: `<label>-<YYYYMMDD>.md` (kebab case, ISO date).
- Each agent gets its own subfolder per project.
- Sidecar `<label>-<YYYYMMDD>.json` when the agent emits structured data (C1).

## Language

- Agent prompts, skills, assets, scripts, comments, references: **English** (LLMs perform best in English; the stack targets a global founder audience).
- User-facing output (the deliverable .md): **language of the user's request**, or pinned via `language` config parameter.
- Exception: copywriting outputs that are language-specific (e.g. FR cold-email assets) stay in their target language because translation loses linguistic nuance.

## Portability requirements (hard rules)

These are non-negotiable for any agent in this stack:

- ❌ No vendor-specific tool names (no `mcp__*`, no `zo-*`, no `claude-*`).
- ❌ No absolute paths to a single user's machine (no `/home/workspace/...`).
- ❌ No assumed runtime (no "run on my Zo", no "send to Discord").
- ❌ No paid SaaS in agent workflows or recommendations (no Profound, Scrunch, Frase, Clay, Apollo, Lemlist). Only established APIs with generous free tiers (`exa`, `firecrawl`, `gsc`, `perplexity`, `instantly`, SERPER.dev).
- ❌ No cross-agent path references (Anthropic spec: keep file references one level deep from `SKILL.md`). Duplicate methodology across agents until 3+ need it, then promote to a shared root.
- ✅ Use POSIX paths starting from the user's chosen project root.
- ✅ Use shell commands (`bash`, `curl`, `jq`) and the cli-skills CLIs.
- ✅ Forward slashes only in scripts (cross-platform).
- ✅ Work identically on Claude Code, Cursor, Codex CLI, Gemini CLI.

If you need a capability beyond what cli-skills + shell offer, call it out in `references/` and ask the user to install the missing tool. Never embed a vendor-locked tool call in an agent's workflow.

## How to create a new agent from this template

```bash
cp -r agents/_template-agent agents/my-new-agent
cd agents/my-new-agent
mv AGENT_TEMPLATE.md AGENT_MY_NEW_AGENT.md
# Edit AGENT_MY_NEW_AGENT.md, README.md, assets/output-template.md, config.example.json
# Add skills under skills/<skill-name>/SKILL.md if needed (see "When to create a skill")
# Add scripts/<tool>.py + scripts/requirements.txt + scripts/README.md if needed
# List required CLIs in the README "Prerequisites" section
```

That's it. Push to your stack.
