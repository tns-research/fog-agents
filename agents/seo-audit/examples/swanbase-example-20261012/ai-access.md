# AI crawler access

Source: robots.txt. Operators' documentation in `assets/ai-crawlers.json`.

| User agent | Operator | Purpose | Group applied | / | /blog/ |
|---|---|---|---|---|---|
| `GPTBot` | OpenAI | training | `GPTBot` | **blocked** | **blocked** |
| `OAI-SearchBot` | OpenAI | search | `*` | allowed | allowed |
| `ChatGPT-User` | OpenAI | user | `*` | allowed | allowed |
| `ClaudeBot` | Anthropic | training | `*` | allowed | allowed |
| `Claude-SearchBot` | Anthropic | search | `*` | allowed | allowed |
| `Claude-User` | Anthropic | user | `*` | allowed | allowed |
| `PerplexityBot` | Perplexity | search | `PerplexityBot` | **blocked** | allowed |
| `Perplexity-User` | Perplexity | user | `*` | allowed | allowed |
| `Googlebot` | Google | search | `*` | allowed | allowed |
| `Google-Extended` | Google | control | `*` | allowed | allowed |
| `Bingbot` | Microsoft | search | `*` | allowed | allowed |
| `Applebot-Extended` | Apple | control | `*` | allowed | allowed |
| `CCBot` | Common Crawl | training | `CCBot` | **blocked** | **blocked** |
| `meta-externalagent` | Meta | training | `*` | allowed | allowed |
| `Amazonbot` | Amazon | search | `*` | allowed | allowed |
| `DuckAssistBot` | DuckDuckGo | search | `*` | allowed | allowed |

Content-Signal lines (a stated preference, not an access rule; see https://contentsignals.org/):

- `search=yes, ai-train=no`

Search or user agents blocked on `/`: PerplexityBot. Their answer engine cannot fetch these pages to cite them.
Training or control agents blocked on `/`: GPTBot, CCBot (no effect on citation by search agents).

1 page(s) show fewer words than the crawl threshold without JavaScript; crawlers that do not run JavaScript see them almost empty:

- https://swanbase.example/events/ (0 words, crawl.jsonl:9)
