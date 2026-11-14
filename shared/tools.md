# Tools: capabilities and providers

Every agent in this stack runs **without any paid API**. External services make a run faster, richer or more precise; none is mandatory. Agents never name a vendor as a requirement: they ask for a **capability** (search the web, scrape a page, take a screenshot) and the founder decides which **provider** fills it, according to the tools they already pay for.

How an agent picks a provider at run time: [`skills/resolving-tools/SKILL.md`](./skills/resolving-tools/SKILL.md).

## Provider tiers

Every capability below lists its providers in these four tiers (`image_gen` also lists an MCP server and a harness image tool, both behind the founder's yes). The resolver walks them top down and takes the first one that is available, unless the founder pinned one.

| Tier | What it is | Cost |
|------|-----------|------|
| **API** | A third-party service called with a key from the environment | paid or free quota |
| **Local** | A program running on the founder's machine (Playwright, Lighthouse, curl) | free |
| **Built-in** | The host agent's own tools: web search and web fetch in Claude Code, Codex CLI, Cursor, Gemini CLI | included |
| **Manual** | The founder pastes text, URLs, screenshots or a CSV export | free |

When no tier is available, the agent **skips** the step, marks the dependent criteria or sections "Unverified", and lists them in the report's Limitations. A run never stops because a key is missing.

## Capabilities

### `web_search`: find pages for a query

| Tier | Provider | How |
|------|----------|-----|
| API | Exa | `EXA_API_KEY`, `exa search "<query>"` ([cli-skills](https://github.com/the20100/cli-skills)) |
| API | Serper | `SERPER_API_KEY`, `POST https://google.serper.dev/search` |
| API | Brave Search | `BRAVE_API_KEY`, `GET https://api.search.brave.com/res/v1/web/search` |
| API | Tavily | `TAVILY_API_KEY`, `POST https://api.tavily.com/search`; takes `include_domains`, `time_range`, `search_depth` (basic 1 credit, advanced 2) |
| Built-in | host web search | the host agent's search tool |
| Manual | founder | pastes a list of URLs |

Degraded without it: the agent works only from URLs the founder provides.

### `community_search`: find discussions (Reddit, forums, Hacker News, reviews)

| Tier | Provider | How |
|------|----------|-----|
| API | Exa | `exa search "<query>" --include-domains reddit.com,news.ycombinator.com` |
| API | any `web_search` API | add `site:reddit.com` (or the forum domain) to the query |
| Local | free public APIs, no key: HN Algolia, Arctic Shift (Reddit archive), StackExchange, Discourse `/search.json`, App Store review RSS | collectors in `agents/market-signal/scripts/` and `agents/first-users-hunter/scripts/collectors/`; Reddit's anonymous JSON and G2 answer 403 from most servers, use Reddit OAuth (free app key) or Arctic Shift instead |
| Local | Hacker News Algolia | `curl "https://hn.algolia.com/api/v1/search?query=<query>"`, no key |
| Built-in | host web search | query with `site:reddit.com` |
| Manual | founder | pastes thread URLs or exported reviews |

### `scrape`: turn a URL into clean text (markdown) or HTML

| Tier | Provider | How |
|------|----------|-----|
| API | Firecrawl | `FIRECRAWL_API_KEY`, `firecrawl scrape <url> --format markdown` |
| API | Jina Reader | `curl https://r.jina.ai/<url>`, works without a key at low rate, `JINA_API_KEY` raises it |
| Local | curl | `curl -sL -A "Mozilla/5.0" <url>` for raw HTML (no JavaScript rendering) |
| Local | Playwright | renders JavaScript pages, see the agent's capture script when it has one |
| Built-in | host web fetch | the host agent's fetch tool |
| Manual | founder | pastes the page text |

### `serp`: Google results with positions, "People also ask" and AI Overviews

| Tier | Provider | How |
|------|----------|-----|
| API | Serper | `SERPER_API_KEY` |
| API | SerpApi | `SERPAPI_API_KEY`, `GET https://serpapi.com/search.json` |
| API | DataForSEO | `DATAFORSEO_LOGIN` and `DATAFORSEO_PASSWORD` |
| Built-in | host web search | result order only, no "People also ask", no AI Overview: mark those findings Unverified |
| Manual | founder | pastes the first page of results or a screenshot |

### `search_console`: the founder's own Google traffic data

| Tier | Provider | How |
|------|----------|-----|
| API | Google Search Console API | service account or OAuth credentials |
| Manual | CSV export | Search Console > Performance > Export, drop the CSV in the project folder (works well and needs no setup) |

Degraded without it: the agent switches to its no-traffic mode (keyword research from `serp` or `web_search`).

### `screenshot`: render a page as images

| Tier | Provider | How |
|------|----------|-----|
| Local | Playwright | `pip install playwright && playwright install chromium`, then the agent's capture script |
| Built-in | host browser tool | when the host agent has one |
| Manual | founder | drops screenshots in the output folder |

Degraded without it: visual criteria are Unverified, text criteria still run.

### `page_speed`: Core Web Vitals

| Tier | Provider | How |
|------|----------|-----|
| API | PageSpeed Insights | works without a key at low volume, `PAGESPEED_API_KEY` raises the quota |
| Local | Lighthouse CLI | `npx lighthouse <url> --only-categories=performance --form-factor=mobile --output=json --output-path=psi.json --chrome-flags="--headless"` (lab data) |
| Manual | founder | runs https://pagespeed.web.dev and pastes LCP, INP, CLS |

### `image_gen`: generate images

| Tier | Provider | How |
|------|----------|-----|
| API | fal | `FAL_API_KEY` or `FAL_KEY` |
| API | OpenAI Images | `OPENAI_API_KEY` |
| API | Google Gemini image | `GEMINI_API_KEY` |
| MCP | Higgsfield MCP (`generate_image`, `media_upload`, `jobs_wait`) | billed in the founder's Higgsfield credits; the agent reads `get_cost` first and waits for a yes |
| Harness | an image tool the harness already exposes (an MCP server, a built-in tool) | the agent writes the prompt pack and calls the tool itself, after the founder's yes on tool, count and price; it saves each file under the name the pack gives |
| Manual | any tool the founder uses (Midjourney, Canva, Figma, a designer) | the agent writes the prompts and the brief, the founder generates and drops the files back |
| Local | HTML/CSS/SVG rendered by Playwright and Chromium | the default for anything that carries text (carousel slides, typographic ads, SEO article covers and body visuals): exact copy, 0 USD. Generated images are kept for photo backgrounds without text. |

Degraded without it: the agent ships prompts, layouts and copy; HTML or SVG rendering still works when the agent has a template renderer.

### `email_finder`: professional email for a named person

| Tier | Provider | How |
|------|----------|-----|
| API | Hunter | `HUNTER_API_KEY` |
| API | Dropcontact, Apollo, Kaspr, Lusha | the founder's own account and key |
| Manual | founder | enriches the CSV in their own tool and drops it back |

Degraded without it: the prospect list ships without the email column, with the LinkedIn or website URL instead.

### `ads_insights`: last period's ad results

| Tier | Provider | How |
|------|----------|-----|
| API | Meta Marketing API insights (`GET /<ad-account>/insights?level=ad`) | the founder's own token or tool, never stored in the repo |
| Manual | Ads Manager CSV export | the founder exports the report and drops the file; no setup |

Degraded without it: the next batch is all exploration and the report says "No performance data".

### `email_verify`: check that an address accepts mail

| Tier | Provider | How |
|------|----------|-----|
| API | the verification service the founder already pays for (NeverBounce, ZeroBounce, Hunter verify, Dropcontact) | the founder's own key |
| Manual | founder | verifies the CSV in their own tool and drops it back |

Never probe SMTP servers from the founder's machine: repeated probes get the IP listed on public blocklists. Degraded without it: addresses ship marked "unverified" and the sequence starts with a smaller first send.

### `ai_answers`: what answer engines say about a question

| Tier | Provider | How |
|------|----------|-----|
| API | Perplexity API | `PERPLEXITY_API_KEY`: answers and cited sources |
| API | any other answer API the founder pays for (OpenAI, Anthropic or Gemini with web search, a GEO tool) | wrapped in a small CLI, called through `--provider command` |
| Local | an answer-engine CLI the founder already has | question on stdin, answer and URLs on stdout |
| Manual | founder | prefilled ChatGPT, Perplexity, Claude and Google links, one click per question, answers pasted back |

Several draws per question: one capture is not a measure. A surface nobody could read is Unverified, never 0 %. Details: `agents/seo-audit/skills/auditing-geo-aeo/SKILL.md`. Degraded without it: the GEO section reports crawler access only.

### `deep_research`: cited synthesis across many sources

| Tier | Provider | How |
|------|----------|-----|
| API | Perplexity | `PERPLEXITY_API_KEY` |
| Built-in | host web search plus fetch | slower, same result |

Always optional: used for cross-checks only.

### `vision`: read images

Used by [`skills/reviewing-renders/SKILL.md`](./skills/reviewing-renders/SKILL.md) to read rendered slides, ads, captures and contact sheets.

| Tier | Provider | How |
|------|----------|-----|
| Built-in | host model image reading | the host agent opens the PNG or JPG itself (file read or image attachment) |
| Local | contact sheet only | `python3 shared/skills/reviewing-renders/scripts/contact_sheet.py` (Pillow) builds the sheet a reviewer reads; it does not judge |
| Manual | founder | looks at the contact sheet and answers the checklist questions |

Degraded without it: mechanical checks (sizes, the agent's QA script) still run; the visual checklist goes to the founder, or the report marks the render "Visual review: not done".

### `critic`: a reviewer that did not produce the work

Used by [`skills/reviewing-with-fresh-eyes/SKILL.md`](./skills/reviewing-with-fresh-eyes/SKILL.md).

| Tier | Provider | How |
|------|----------|-----|
| Built-in | fresh subagent | the host's subagent tool, started with the critique packet only |
| Local | second session or model CLI | a blank session of the same tool, or `claude -p`, `codex exec -`, `gemini -p` with the prompt on stdin |
| Manual | founder or teammate | answers the rubric as a short form |

Degraded without it: the report says "Fresh-eyes review: not run" and the deliverable is listed as unreviewed. A second pass by the producing session does not count as this capability.

### `copy_lint`: machine-writing gate

Used by [`skills/writing-gate/SKILL.md`](./skills/writing-gate/SKILL.md) on every piece of copy.

| Tier | Provider | How |
|------|----------|-----|
| Local | writing gate | `python3 shared/skills/writing-gate/scripts/lint_copy.py --project <project> <file>`, stdlib only, exit 1 on BLOCK |
| Local | slopcheck | add `--with-slopcheck` when the `slopcheck` command is installed; its BLOCKs also fail the gate |
| Manual | checklist | the family table of the writing-gate skill, applied by reading |

Degraded without it: the agent applies the checklist by hand and writes "Writing gate: manual" in Methodology.

### `transcription`: words with timings from an audio or video file

Used by `short-video-builder`, and by `founder-content-writer` to turn a voice note into text before `ingest.py` (which reads text files only).

| Tier | Provider | How |
|------|----------|-----|
| Local | faster-whisper | `pip install faster-whisper`, model downloaded once, runs on CPU |
| Local | whisper.cpp or openai-whisper | when installed; their JSON output is imported as is |
| Manual | founder | provides an SRT, VTT or JSON transcript |

Degraded without it: the agent asks for a transcript file; word timings are estimated from cue times and the karaoke highlight is marked approximate.

### `publish`: send an approved post to a network

Used by `content-publisher`, only for items a person approved.

| Tier | Provider | How |
|------|----------|-----|
| API | Zernio | `ZERNIO_API_KEY` |
| API | any scheduler or native API | the `command` adapter (Buffer, Typefully, a script of yours) or the `webhook` adapter (`CONTENT_PUBLISHER_WEBHOOK_URL`) |
| Local | dry-run | default: writes what would be sent to `outbox/` |
| Manual | founder | posts by hand from the review packet |

Degraded without it: the queue still lints, approves and schedules; the founder posts the dry-run output by hand.

### `web_analytics`: visits, sources and conversions of the founder's site

Used by `growth-pulse`.

| Tier | Provider | How |
|------|----------|-----|
| API | Plausible | `PLAUSIBLE_API_KEY`, `PLAUSIBLE_SITE_ID` |
| API | Umami | `UMAMI_API_KEY` (Cloud) or `UMAMI_BASE_URL` with a login (self-hosted), `UMAMI_WEBSITE_ID` |
| API | Google Analytics 4 | `GA4_ACCESS_TOKEN` |
| Manual | founder | CSV export from the analytics tool |

Degraded without it: the traffic section of the report says "no data" and no experiment rests on traffic numbers.

### `social_stats` and `revenue_data`: followers, engagement, revenue

Used by `growth-pulse`.

| Tier | Provider | How |
|------|----------|-----|
| API | Zernio | `ZERNIO_API_KEY` (social, `agents/growth-pulse/scripts/connect_zernio.py`; a read-only key is enough) |
| API | Stripe | `STRIPE_API_KEY` (revenue) |
| Manual | founder | CSV exports of the social networks and of the billing tool |

Degraded without it: the section is marked "no data"; the other sources still run.

### `subagents`: run steps in parallel with a fresh context

Used by `growth-sprint` (waves of up to three steps), `first-users-hunter` (one collector family per task) and `carousel-builder` (direction renders and the fresh review).

| Tier | Provider | How |
|------|----------|-----|
| Built-in | host subagent tool | one brief file per task, the task ends on a check of its file on disk |
| Local | second session or model CLI | `claude -p`, `codex exec -`, `gemini -p` with the brief on stdin |
| Manual | same session | the tasks run one after the other |

Degraded without it: the same steps run in sequence; only the duration changes.

## Declaring the founder's tools

Optional file, shared by every agent of a project:

```
<your-projects-root>/<project>/project-context/tools.json
```

Template: [`tools.example.json`](./tools.example.json). Each capability takes `"auto"` (default: first available tier), a provider name from the tables above, `"builtin"`, `"manual"` or `"none"`. An agent's own `config.json` may hold a `tools` object with the same keys: it overrides the project file for that agent only. A choice given in chat overrides both.

## Rules for agent authors

1. In `AGENT_*.md`, the section is called `## Tools` and is a table: capability, what the agent uses it for, what happens without it. Link here for providers; never list an API as a prerequisite.
2. Workflow steps name the capability (`scrape the page`, `web_search`), then show the default command as one example among the providers of this file.
3. Scripts that call an API read the key from the environment, accept a flag or a fallback provider, and exit with a clear message (never a stack trace) when nothing is available, so the agent can switch tier.
4. The report's Methodology lists the provider actually used per capability, and Limitations lists what was skipped.
