# project-context

**The entry door of the founders OS.** Configure your brand and business context once; every other agent in the stack reads it instead of asking you again.

## What it produces

A shared folder in your project:

```
<your-projects-root>/<project-slug>/project-context/
├── context.json      # what you sell, to whom, your offer, positioning, proof, voice
├── context.md        # the same, in readable prose (edit by hand anytime)
├── brand.json        # color roles, fonts, light and dark logo variants with their audit, harvested assets
├── people.json       # who may appear in visuals and posts, with their consent
├── partners.json     # which companies may be named or shown, with consent and light/dark logos
├── tools.json        # optional: which tools you already use (search, scraping, images, email finder)
├── docs/             # optional: your deck and notes, with the text of every page
├── voice/            # optional: your voice pack, measured on texts you wrote
├── assets/
│   ├── logos/        # your logo as harvested, plus wordmark and mark variants for light and dark backgrounds
│   ├── fonts/        # Google Fonts files, for renders that load no remote stylesheet
│   ├── people/       # portraits, only for people whose consent is recorded
│   ├── partners/     # partner logos, one for light and one for dark backgrounds
│   └── site/         # og:image, favicon, a screenshot, a hero capture and your page images
└── brand-debug/      # screenshots, logo tests and the brand board used to extract & validate the brand
```

Every other agent in the stack (market-signal, first-users-hunter, seo-audit, landing-page-analyzer, cold-outreach-builder, carousel-builder, static-ads-builder, short-video-builder, founder-content-writer, content-publisher, growth-pulse, growth-sprint) auto-detects this folder and prefills its inputs from it, and the agents that write copy enforce your claims policy on it. If it is missing, they still run, they just ask you a couple of quick questions inline. Nothing in the stack hard-depends on it.

## When to run it

- **First**, before any other agent, when you set up a new project.
- **Again** when you rebrand or pivot (new logo, new ICP, new offer).

## Inputs

| Input | Required | Default | What it does |
|-------|----------|---------|--------------|
| project slug | yes | inferred from URL | names the shared folder |
| URL | recommended | none | auto-extracts brand + pre-fills business context |
| `web_enrichment` | optional | `auto` | `off`/`auto`/`firecrawl`/`jina`/`http`/`exa`, pulls product/about/pricing pages (`auto` works with no key) |
| `language` | optional | `en` | language of `context.md` and `voice.language` |
| your texts | optional | none | posts, about page, emails you wrote: measured into a voice pack (sentence length, form of address, banned words) that copy agents follow |
| deck, notes | optional | none | your pitch deck (PDF) or notes: read page by page so you answer fewer questions; every number taken from them is checked against its page |
| people, partners | optional | none | who and which companies the stack may show; nobody appears without a recorded consent |

Run it standalone-friendly: with no URL and no API keys, it just runs a short Q&A and still writes a valid folder.

## Your tools (`tools.json`)

During setup the agent asks you one question: which tools you already use for web search, scraping, image generation and finding emails. It writes your answer to `project-context/tools.json`, copied from [`../../shared/tools.example.json`](../../shared/tools.example.json):

```json
{
  "web_search": "exa",
  "scrape": "auto",
  "image_gen": "manual",
  "email_finder": "hunter"
}
```

Each capability takes `auto` (default: the first available provider), a provider name from [`../../shared/tools.md`](../../shared/tools.md), `builtin` (your coding agent's own search or fetch), `manual` (you paste or drop files, for example Midjourney or Canva output) or `none`. Skip the question and everything stays `auto`. The file never holds a key: keys stay in your environment. Every agent reads it at its Step 0, so you never re-declare your stack; edit it by hand anytime.

## Tools

No paid API is required. Defaults are one option among others:

| Capability | Used for | Without it |
|------------|----------|------------|
| `screenshot` | brand extraction, asset harvest, logo variants and brand board (default: local Playwright) | you give colors and a logo in chat |
| `scrape` | business pre-fill from your site (default: Jina Reader keyless, else plain HTTP; Firecrawl, Exa or a keyed Jina only after you agree to spend credits) | you answer the Q&A without pre-fill |
| `web_search` | optional broad enrichment (Exa, or any search provider) | skipped |

Brand extraction uses bundled Python scripts (Playwright render + Pillow pixel sampling). Install their deps once:

```bash
pip install -r agents/project-context/scripts/requirements.txt
python -m playwright install chromium
```

Optional, only if you already use them:

```bash
export FIRECRAWL_API_KEY="..."   # scrape provider for the business pre-fill
export EXA_API_KEY="..."         # web_search provider (with the exa CLI from https://github.com/the20100/cli-skills)
```

## Run it

### Claude Code

```
Run the project-context agent at agents/project-context/AGENT_PROJECT_CONTEXT.md.
URL: https://acme.example  Language: en
```

### Cursor / Codex CLI / Gemini CLI

Open `agents/project-context/AGENT_PROJECT_CONTEXT.md` as the system prompt for a fresh session, then:

```
Follow this workflow. URL: https://acme.example  Language: en
```

## How it works

Two checkpoints, both human-validated:

1. **Brand checkpoint.** It extracts colors/fonts/logo from your URL (two signals: page DOM + a headless screenshot), reads your accent from the primary button, **grabs your real assets** (logo, og:image, a hero capture and your page images) so the creative agents build from your own material, and builds light and dark versions of your logo tested for contrast. It renders a brand board showing every color, font and logo variant with its checks and the harvested images, and you approve or correct. No auto-approve.
2. **Context checkpoint.** It drafts your business context from the scrape + a short Q&A, you review `context.md`, correct in chat or edit the file.

Then it writes `brand.json`, `context.json`, `context.md`, `people.json` and `partners.json` when you listed anyone, the voice pack when you gave texts, and `tools.json` if you accepted it. Edit any of them by hand whenever you like.

## Notes

- This agent owns brand extraction for the whole stack. carousel-builder and static-ads-builder **read** `brand.json`, they do not re-extract.
- `context.json` carries a `voice.claims_policy` field ("no invented stats, every metric traces to a URL"). Copywriting agents read and enforce it.
- Each proof item has a kind, a source, the date of the fact and, for a testimonial or a customer, a consent. Agents use only the items still valid: a metric older than 180 days, or a quote without consent for that use, stays out of the copy until you update it (`python3 shared/scripts/proof.py check <your-project>/project-context/context.json --scope ads` shows which).

## License

Apache 2.0 (matches the rest of the stack).
