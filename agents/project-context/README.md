# project-context

**The entry door of the founders OS.** Configure your brand and business context once; every other agent in the stack reads it instead of asking you again.

## What it produces

A shared folder in your project:

```
<your-projects-root>/<project-slug>/project-context/
├── context.json      # what you sell, to whom, your offer, positioning, proof, voice
├── context.md        # the same, in readable prose (edit by hand anytime)
├── brand.json        # colors, fonts, logo_path + a manifest of harvested assets
├── assets/
│   ├── logo.svg|png  # your logo, downloaded (inline-SVG logos included)
│   └── site/         # og:image, favicon, and your largest product/hero images
└── brand-debug/      # screenshots + preview card used to extract & validate the brand
```

Other agents (static-ads-builder, carousel-builder, ...) auto-detect this folder. If it is missing, they still run, they just ask you a couple of quick questions inline. Nothing in the stack hard-depends on it.

## When to run it

- **First**, before any other agent, when you set up a new project.
- **Again** when you rebrand or pivot (new logo, new ICP, new offer).

## Inputs

| Input | Required | Default | What it does |
|-------|----------|---------|--------------|
| project slug | yes | inferred from URL | names the shared folder |
| URL | recommended | none | auto-extracts brand + pre-fills business context |
| `web_enrichment` | optional | `auto` | `off`/`exa`/`firecrawl`/`auto`, pulls product/about/pricing pages |
| `language` | optional | `en` | language of `context.md` and `voice.language` |

Run it standalone-friendly: with no URL and no API keys, it just runs a short Q&A and still writes a valid folder.

## Prerequisites

```bash
# Install once, reuse across all agents in this stack
git clone https://github.com/the20100/cli-skills.git ~/cli-skills

# Add the CLIs this agent can use to your PATH
export PATH="$HOME/cli-skills/firecrawl-cli/bin:$PATH"
export PATH="$HOME/cli-skills/exa-cli/bin:$PATH"

# Optional keys (the agent degrades cleanly without them)
export FIRECRAWL_API_KEY="..."   # brand DOM/CSS + business page scrape
export EXA_API_KEY="..."         # broad business enrichment
```

Brand extraction uses a bundled Python script (Playwright screenshot + Pillow palette). Install its deps once:

```bash
pip install -r agents/project-context/scripts/requirements.txt
python -m playwright install chromium
```

## Run it

### Claude Code

```
Run the project-context agent at agents/project-context/AGENT_PROJECT_CONTEXT.md.
URL: https://acme.com  Language: en
```

### Cursor / Codex CLI / Gemini CLI

Open `agents/project-context/AGENT_PROJECT_CONTEXT.md` as the system prompt for a fresh session, then:

```
Follow this workflow. URL: https://acme.com  Language: en
```

## How it works

Two checkpoints, both human-validated:

1. **Brand checkpoint.** It extracts colors/fonts/logo from your URL (two signals: page DOM + a headless screenshot), reads your accent from the primary button, and **grabs your real assets** (logo, og:image, and your largest product/hero images) so the creative agents build from your own material. It renders a preview card showing the colors and a strip of the harvested assets, and you approve or correct. No auto-approve.
2. **Context checkpoint.** It drafts your business context from the scrape + a short Q&A, you review `context.md`, correct in chat or edit the file.

Then it writes `brand.json`, `context.json`, and `context.md`. Edit any of them by hand whenever you like.

## Notes

- This agent owns brand extraction for the whole stack. carousel-builder and static-ads-builder **read** `brand.json`, they do not re-extract.
- `context.json` carries a `voice.claims_policy` field ("no invented stats, every metric traces to a URL"). Copywriting agents read and enforce it.

## License

Apache 2.0 (matches the rest of the stack).
