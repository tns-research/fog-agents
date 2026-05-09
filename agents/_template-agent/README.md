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
1. `AGENT_MY_NEW_AGENT.md`: frontmatter, `## When to run`, `## Inputs`, `## Workflow`, `## Output`.
2. `README.md`: prerequisites (which cli-skills CLIs), usage examples, env vars.
3. `assets/output-template.md`: the deliverable's markdown skeleton.
4. `skills/`: only if the agent has reusable sub-skills (often you don't need this).
5. `references/README.md`: links to API docs and the relevant cli-skills CLI READMEs.

## Install on your harness

The whole stack works the same on Claude Code, Cursor, Codex CLI, Gemini CLI. There's no harness-specific install: each agent is a folder of markdown your harness reads as context.

The two patterns:

**A. Reference the agent in your harness's project rules / system prompt:**

> "When the user asks for a market signal scan, follow `agents/market-signal/AGENT_MARKET_SIGNAL.md`."

**B. Or invoke directly when chatting:**

> "Run the agent at `agents/market-signal/`."

## Required tools

Most agents in this stack rely on the public **cli-skills** repo:

```bash
git clone https://github.com/the20100/cli-skills.git ~/cli-skills
```

Each agent's `README.md` lists which CLIs it needs and the env vars to set.

## License

Apache 2.0 (matches the rest of the stack).
