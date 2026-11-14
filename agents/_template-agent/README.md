# _template-agent

Reference scaffold for every agent in the **Founders Growth Agent Stack**.

## What it is

Not a runnable agent. A copy-paste starting point. Read `AGENT_TEMPLATE.md` to understand the contract every stack agent must satisfy, then fork this folder when you build a new one.

## How to use

```bash
# From the stack root
cp -r agents/_template-agent agents/my-new-agent
cd agents/my-new-agent
mv AGENT_TEMPLATE.md AGENT_MY_NEW_AGENT.md
```

Then fill in:
1. `AGENT_MY_NEW_AGENT.md`: frontmatter (`name`, `description`), then the sections of the workflow contract in `AGENT_TEMPLATE.md`: `## Step 0: context resolution` (with the Resolve tools step), `## When to run`, `## Inputs needed`, `## Tools`, `## Workflow`, `## Checks before delivery`, `## Review`, `## Autonomous mode`, `## Output format`, `## Output location`, `## Failure modes`, `## Per-project config`.
2. `README.md`: the Tools table (capabilities, what happens without each), optional provider setup, usage examples.
3. `config.example.json`: the per-project parameters, with a top-level `_comment`.
4. `assets/output-template.md`: the deliverable's markdown skeleton, plus a `review-rubric.md` in `assets/` when the agent has its own rubric.
5. `skills/<skill-name>/SKILL.md`: at least one skill, its `name` equal to its folder name. `scripts/validate_stack.py` refuses an agent folder without one.
6. `references/README.md`: links to API docs and the relevant cli-skills CLI READMEs.
7. `examples/README.md`: an index of the example runs, when the agent ships any.

Then run `python3 scripts/validate_stack.py` from the repo root.

## Install on your harness

The whole stack works the same on Claude Code, Cursor, Codex CLI, Gemini CLI. There's no harness-specific install: each agent is a folder of markdown your harness reads as context.

The two patterns:

**A. Reference the agent in your harness's project rules / system prompt:**

> "When the user asks for a market signal scan, follow `agents/market-signal/AGENT_MARKET_SIGNAL.md`."

**B. Or invoke directly when chatting:**

> "Run the agent at `agents/market-signal/`."

## Tools

No agent in this stack requires a paid API. Each one lists the **capabilities** it uses (web search, scrape, screenshot, image generation...) and what happens without each; the founder's own tools fill them. Catalog and providers: [`shared/tools.md`](../../shared/tools.md). Step 0 of every agent resolves them with [`shared/skills/resolving-tools/SKILL.md`](../../shared/skills/resolving-tools/SKILL.md).

The public [cli-skills](https://github.com/the20100/cli-skills) repo lists one convenient set of default API providers, optional. Each CLI builds with Go:

```bash
mkdir -p ~/.local/bin
for t in exa firecrawl; do
  git clone --depth 1 https://github.com/the20100/$t-cli /tmp/$t-cli
  (cd /tmp/$t-cli && go build -o ~/.local/bin/$t .)
  rm -rf /tmp/$t-cli
done
export PATH="$HOME/.local/bin:$PATH"
```

## License

Apache 2.0 (matches the rest of the stack).
