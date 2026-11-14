---
name: _template-agent
description: Reference scaffold for every agent in the Founders Growth Agent Stack. Copy this folder, rename, and fill in. Defines the canonical layout, prompts, config flow, tool resolution, skills/assets/scripts pattern, and portability rules that all stack agents must follow.
license: Apache-2.0
compatibility: Claude Code, Cursor, Codex CLI, Gemini CLI
---

# _template-agent

This is the canonical template for every agent in the **Founders Growth Agent Stack**.
Copy it, rename, fill in. Do not skip sections.

For fuller examples of a skills + assets + scripts agent in action, see [`../landing-page-analyzer/`](../landing-page-analyzer/) (capture script, scored grid, render review of captures) and [`../cold-outreach-builder/`](../cold-outreach-builder/) (copy skills, export script, writing gate before review).

## Why a template

Every agent must look the same to a founder who has never seen the stack:

- Same folder layout.
- Same `## Step 0` / `## When to run` / `## Inputs needed` / `## Tools` / `## Workflow` / `## Checks before delivery` / `## Review` / `## Autonomous mode` / `## Output format` / `## Output location` / `## Failure modes` / `## Per-project config` sections.
- Same way to pick tools: capabilities resolved at Step 0, no API ever required.
- Same per-project config convention.

Predictability is a feature.

## Folder layout

```
my-agent/
├── AGENT_MY_AGENT.md       ← this spec (renamed)
├── README.md                ← install, Tools (optional providers), usage examples
├── config.example.json      ← per-project parameters, with a top-level _comment
├── skills/                  ← methodology (heuristics, scoring, taxonomies, prompts), at least one skill
│   └── <skill-name>/
│       └── SKILL.md
├── assets/                  ← data the methodology operates on (lists, checklists, templates), never empty
│   ├── output-template.md   ← deliverable format
│   ├── review-rubric.md     ← optional, the agent's own fresh-eyes rubric
│   ├── <contract>.schema.json ← optional, the schema of a file the agent writes or reads
│   └── <rule-set>.md        ← optional per-skill data
├── scripts/                 ← bundled tools (optional, only when CLI-piping is not enough)
│   ├── <bundled-tool>.py
│   ├── selftest.py          ← offline test of the scripts (some agents use tests/run_tests.py instead)
│   ├── requirements.txt
│   └── README.md
├── references/
│   └── README.md            ← links to APIs, docs, cli-skills, foundational reads
└── examples/                ← optional fictional or anonymized runs
    ├── README.md            ← one row per example: what it shows, how to rebuild it
    └── <project>-<label>-<YYYYMMDD>/
```

`python3 scripts/validate_stack.py` (from the repo root) checks the required part of this layout: `AGENT_*.md`, `README.md`, `config.example.json`, `references/README.md`, a non-empty `assets/`, at least one `skills/<name>/SKILL.md`, and `README.md` plus `requirements.txt` in a `scripts/` folder that holds `.py` files.

## Tools pattern (every external call is optional)

An agent never requires a paid API. It asks for a **capability** (`web_search`, `scrape`, `screenshot`, `image_gen`...) and the founder decides which **provider** fills it: an API they already pay for, a local program, the host agent's built-in tools, or manual input. The catalog of capabilities, providers and tiers is [`shared/tools.md`](../../shared/tools.md); the Step 0 resolver is [`shared/skills/resolving-tools/SKILL.md`](../../shared/skills/resolving-tools/SKILL.md).

In `AGENT_<NAME>.md`, ship a `## Tools` section after `## Inputs needed`, shaped like this:

```markdown
## Tools

Every capability is optional. Providers, tiers and setup: [`../../shared/tools.md`](../../shared/tools.md).

| Capability | Used for | Without it |
|------------|----------|------------|
| `web_search` | <what the agent searches for> (Step N) | <fallback: host web search, founder URLs; what is marked Unverified> |
| `scrape` | <what the agent reads> (Step N) | <fallback: host web fetch or curl; what degrades> |

The defaults shown in the workflow (`exa`, `firecrawl`) are one option among others: any provider of `shared/tools.md` fills the same capability, with the same output.
```

Rules:

- Never write a `Prerequisites` section that lists API keys as required. The "Without it" column must describe a run that still completes.
- A capability that is **core** to the deliverable (for example `image_gen` in an ad or carousel agent) falls back to `manual`, never to "stop": the agent ships everything it can without the API (briefs, prompts, copy, HTML or SVG renders) plus a clear drop-back loop ("drop your files in `<folder>` named `<pattern>`, then rerun `<step>`").
- Workflow steps name the capability first, then show the default command as an example (`scrape the page, for example firecrawl scrape <url>`), then the fallback.
- Install snippets for API providers stay optional examples, never the first thing a founder must do. Reference the public `cli-skills` repo rather than reimplementing a CLI:

```bash
# Optional example: default API providers listed in cli-skills, built with Go (any provider of shared/tools.md works)
mkdir -p ~/.local/bin
for t in exa firecrawl; do
  git clone --depth 1 https://github.com/the20100/$t-cli /tmp/$t-cli
  (cd /tmp/$t-cli && go build -o ~/.local/bin/$t .)
  rm -rf /tmp/$t-cli
done
export PATH="$HOME/.local/bin:$PATH"
export EXA_API_KEY="..."
export FIRECRAWL_API_KEY="..."
```

The `~/.local/bin` location is a convention. Any folder works as long as the binaries land on `PATH`.

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
4. Reads the optional `tools` object of `config.json` (same keys as [`shared/tools.example.json`](../../shared/tools.example.json)): it overrides the project's `project-context/tools.json` for this agent only.

Never hard-code a single project root. Use the user's chosen one.

The `config.example.json` MUST include a top-level `_comment` field describing what the file is and where it gets copied, and mentioning the optional `tools` object. This makes the file self-documenting.

## Workflow contract (every agent)

Every agent's `AGENT_<NAME>.md` MUST have these sections in order:

1. `## Step 0: context resolution` (resolve the project slug, load the project context, read the project memory, resolve tools, load the config, then ask every missing input **in one message**; skeleton below)
2. `## When to run` (1-3 sentences, founder-readable)
3. `## Inputs needed` (list, with required/optional + defaults: every input has the default used when the founder does not answer, or says why it has none)
4. `## Tools` (capability table, see "Tools pattern" above)
5. `## Workflow` (numbered steps; each step POINTS to a `skills/<name>/SKILL.md` or `assets/<file>.md` when methodology is loaded, and ends with a **Done when** line, see below)
6. `## Checks before delivery` (the shared gates in their fixed order, with the exact commands, see below)
7. `## Review` (who reviews the deliverable and against what, see below)
8. `## Autonomous mode` (what the agent does when nobody answers, see below)
9. `## Output format` (markdown skeleton or link to `assets/output-template.md`; the report's Methodology lists the provider used per capability and the result of every check, Limitations lists every skipped capability and what it left Unverified)
10. `## Output location` (path pattern using `<your-projects-root>/<project>/<agent>/...`)
11. `## Failure modes` (each entry: `**<trigger>** → <fallback action>`; a missing key is a fallback, never a failure)
12. `## Per-project config` (where `config.json` lives and a link to `config.example.json`)

Most agents also open with a `## Skills loaded` table (skill, step, output) and an `## Assets used` table (asset, used by) before Step 0. Some agents carry the Review and Autonomous mode content in gate 5 of their Checks section and in their Step 0 instead of separate sections; a new agent writes both sections out.

Step 0 skeleton (numbering may grow; project memory and Resolve tools always come right after the project context):

```markdown
## Step 0: context resolution

1. **Project.** Resolve the project slug (from the user, or infer from a URL). Ask once if ambiguous.
2. **Project context.** Follow [`../../shared/skills/loading-project-context/SKILL.md`](../../shared/skills/loading-project-context/SKILL.md) and prefill what it provides (add its `brand` option when the agent renders visuals).
3. **Project memory.** Follow [`../../shared/skills/keeping-project-memory/SKILL.md`](../../shared/skills/keeping-project-memory/SKILL.md) (Step 0 part): read `<project>/project-context/memory/decisions.md` and apply the active decisions as hard rules; stop with a `skipped` run line when `memory/runs.jsonl` shows the same inputs already done.
4. **Resolve tools.** Follow [`../../shared/skills/resolving-tools/SKILL.md`](../../shared/skills/resolving-tools/SKILL.md) for the capabilities listed in Tools below, and announce the tool plan in one block.
5. **Config.** Load `<your-projects-root>/<project>/<agent>/config.json`, or copy `config.example.json`.
6. **One message of questions.** Ask every input still missing in a single message, each with the default used without an answer. Then run on the answers or the defaults and write each default used in Methodology. No later step stops for an answer, except a step that spends money or publishes.
```

### Done when: verifiable end criteria

A step is finished when something outside the model's own judgment says so. Write the criterion as a check another agent could run without reading the conversation:

- a file that exists and is not empty (`<out>/desktop.png`, `<label>-<YYYYMMDD>.json`);
- a command that exits 0 (`python3 scripts/validate_briefs.py briefs.json`, the writing gate, the schema validator);
- a count (`10 to 15 fixes`, `every quote has a permalink`, `one row per non-skipped prospect`);
- an explicit, recorded skip (`no screenshot provider: S rows marked Unverified in Limitations`).

```markdown
3. **Score the grid.** Load `skills/<name>/SKILL.md`. Walk `assets/<grid>.md` ...
   Done when: every applicable row has a verdict (OK / Partial / Missing / N/A / Unverified) and `scores.json` parses.
```

Length is not a criterion. A step may be long when its method is long; methodology over about 50 lines still moves into a skill (see below).

### Checks before delivery

The gates of [`shared/README.md`](../../shared/README.md#order-of-the-gates), in this order, each on the output of the previous one. Commands run from the agent folder (from the repo root, drop `../../`); a gate that does not apply says so in one line instead of disappearing.

```markdown
## Checks before delivery

1. **Writing gate** on every piece of delivered copy:
   python3 ../../shared/skills/writing-gate/scripts/lint_copy.py --project <project> --json <files> > <out>/writing-gate.json
   0 BLOCK, 3 passes at most; without Python, the skill's family table by hand ("Writing gate: manual").
2. **Claims check** with ../../shared/skills/enforcing-claims-policy/SKILL.md on the passing copy.
3. **Schema check** of every contract file written (brand.json, the handoff sidecar, the run line):
   python3 ../../shared/scripts/validate_json.py <schema> <file>
   A sidecar with no schema yet: it must parse, and say so.
4. **Render review** (agents that output images) with ../../shared/skills/reviewing-renders/SKILL.md:
   contact sheet, scored checklist, fix the source never the image, 3 rounds at most.
5. **Fresh-eyes review**, see Review.
6. **Run log and decisions** with ../../shared/skills/keeping-project-memory/SKILL.md:
   python3 ../../shared/scripts/validate_json.py --jsonl ../../shared/schemas/run-record.schema.json <project>/project-context/memory/runs.jsonl
```

The writing gate and the claims check run **before** any human checkpoint, so the founder never judges copy a script would have rejected.

### Review

Name the reviewer and the rubric:

- **Rubric**: a `review-rubric.md` in the agent's `assets/` folder (`agents/<name>/assets/review-rubric.md`) when the agent has its own (criteria scored 0 to 2, a threshold, a floor of 1 on every criterion), otherwise the default rubric of [`shared/skills/reviewing-with-fresh-eyes/SKILL.md`](../../shared/skills/reviewing-with-fresh-eyes/SKILL.md).
- **Reviewer**: a fresh subagent, else a blank session or a second model CLI, else the founder (the `critic` capability of [`shared/tools.md`](../../shared/tools.md)). A second pass by the producing session never counts.
- **Bounds**: one critique, one revision; a hard check outranks a written constraint, which outranks taste. An agent-specific self-check (a review skill of its own) runs before and does not replace it.

### Autonomous mode

What the agent does when it runs unattended (scheduled run, orchestrator, nobody answering):

- Every question has a documented default (Inputs table); the defaults used are listed in Methodology.
- It stops only at steps that **spend money** (an image render, a paid API batch) or **publish** (send, post, promote a shared file such as `brand.json`). There it writes everything up to the gate, records the pending decision, and ends the run as `partial`. Never auto-confirm a spend or a publication.
- A missing capability degrades the run (Unverified, manual drop-back), never stops it.
- The run always ends with its `runs.jsonl` line, failures included, and its proposed decisions written as `Status: proposed`.

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

Scripts that call an API follow rule 3 of [`shared/tools.md`](../../shared/tools.md): read the key from the environment, accept a `--provider` flag (or a fallback provider, `manual` when the capability is core), and exit with a clear one-line message and a documented exit code (never a stack trace) when nothing is available, so the agent can switch tier. Test `--help` and a run with no key set before shipping.

**Scripts solve, don't punt**: handle errors explicitly (return defaults or specific error messages), no magic numbers (document every constant inline), forward slashes only (cross-platform).

### When to use assets

Put any list, checklist, template, taxonomy, or example into `assets/`. The methodology in the skill *references* these assets at the relevant workflow step. Loading data lazily keeps the LLM's context lean.

### When to add an example

Optional but high-value. Drop one fictional or anonymized run per agent in `examples/<project>-<label>-<YYYYMMDD>/` (the inputs and the deliverable), or a single `examples/<agent>-example-<YYYYMMDD>.md`, and list it in `examples/README.md`. Single biggest reduction in LLM hallucination about output format. Use synthetic-but-realistic data if anonymization is too heavy. `scripts/validate_stack.py` refuses an e-mail address outside the reserved test domains (`example.com`, `example.org`, `example.net`, the `.example`, `.test` and `.invalid` TLDs) and a `linkedin.com/in/` URL whose slug does not say "fictive", "fictional" or "example" in `examples/`, `tests/fixtures/` and `scripts/fixtures/`.

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
- ❌ No paid SaaS in agent workflows or recommendations (no Profound, Scrunch, Frase, Clay, Apollo, Lemlist).
- ❌ No required API. Every external call sits behind a capability of [`shared/tools.md`](../../shared/tools.md) with a free fallback (local program, host built-in tool, or manual input). The founder's own tools (their API keys, Midjourney, Canva, a CSV export) are always accepted as providers.
- ❌ No cross-agent path references (Anthropic spec: keep file references one level deep from `SKILL.md`). Duplicate methodology across agents until 3+ need it, then promote it to the shared root [`shared/`](../../shared/) and link it with a relative path (`../../shared/skills/<skill>/SKILL.md`).
- ✅ Step 0 loads the founder's shared business context through [`shared/skills/loading-project-context/SKILL.md`](../../shared/skills/loading-project-context/SKILL.md) (with its `brand` option when brand assets are needed), reads the project's decisions through [`shared/skills/keeping-project-memory/SKILL.md`](../../shared/skills/keeping-project-memory/SKILL.md), and asks only for inputs it could not prefill, in one message.
- ✅ Every deliverable passes the gates of [`shared/README.md`](../../shared/README.md#order-of-the-gates) in order before the founder sees it, and every run ends with its line in `memory/runs.jsonl`.
- ✅ Any agent that writes copy runs [`shared/skills/enforcing-claims-policy/SKILL.md`](../../shared/skills/enforcing-claims-policy/SKILL.md): no proof, customer name, metric or testimonial without an allowed claim or a source URL.
- ✅ Use POSIX paths starting from the user's chosen project root.
- ✅ Step 0 resolves tools through [`shared/skills/resolving-tools/SKILL.md`](../../shared/skills/resolving-tools/SKILL.md) and the run degrades, never stops, when a provider is missing.
- ✅ Use shell commands (`bash`, `curl`, `jq`) and the cli-skills CLIs as optional providers.
- ✅ Forward slashes only in scripts (cross-platform).
- ✅ Work identically on Claude Code, Cursor, Codex CLI, Gemini CLI.

If you need a capability that `shared/tools.md` does not list yet, propose it there (capability, tiers, fallback) instead of hard-wiring a vendor. Never embed a vendor-locked tool call in an agent's workflow.

## How to create a new agent from this template

```bash
cp -r agents/_template-agent agents/my-new-agent
cd agents/my-new-agent
mv AGENT_TEMPLATE.md AGENT_MY_NEW_AGENT.md
# Edit AGENT_MY_NEW_AGENT.md, README.md, assets/output-template.md, config.example.json
# Add at least one skill under skills/<skill-name>/SKILL.md (see "When to create a skill")
# Add scripts/<tool>.py + scripts/requirements.txt + scripts/README.md if needed
# Fill the "## Tools" table (capability, used for, without it) in AGENT_*.md and README.md
# Give every workflow step a "Done when" line, and fill Checks before delivery, Review and Autonomous mode
```

Then run `python3 scripts/validate_stack.py` from the repo root and fix anything it reports before you push. Besides the layout, it checks relative links and backticked repo paths, frontmatter, JSON parsing and the `_comment` of `config.example.json`, the `## Tools` section and its link to the resolving-tools skill (and no `## Prerequisites` section), em and en dashes, forbidden terms, and personal data in sample files.

That's it. Push to your stack.
