# Sources

What each collector covers, what it misses, and how to aim it. Used at Step 1 to write `plan.json` and at Step 2 to read `health.json`. Behaviour observed from a cloud server in October 2026; recheck with a live run when a source looks dead.

## Free collectors (no key)

| Source | Script | Covers | Limits | Aim it with |
|--------|--------|--------|--------|-------------|
| Reddit | `collect_reddit.py` | Comments (default) or posts of one subreddit, full text, score, permalink | Through the Arctic Shift archive: hours to days behind, deleted texts gone. Heavy full-text queries on big subreddits answer "Timeout. Maybe slow down a bit" (health `quota`): keep `--kind comments`, small caps, one query per job; `collect.py` runs Reddit jobs one after the other | Subreddits where the persona asks for help, not only the category's own subreddit. Find them in the threads Hacker News or a web search returns, or ask the founder |
| Hacker News | `collect_hn.py` | Stories and comments, exact phrases in quotes, comments of the best threads (`thread_comments`) | Comment scores are not public (no resonance); generic words match the monthly hiring threads. Comments of the job-seeker threads ("Who wants to be hired", "Seeking freelancer") are never stored | Exact phrases (`"warm intro"`), `tags: comment`, `thread_comments: 1` or `2` on Show HN and Ask HN threads |
| Stack Exchange | `collect_stackexchange.py` | Questions (and answers with `answers: true`) of one site, full text | 300 requests a day per IP. Many sites are closed (`startups` is gone: health `error`). Questions skew towards how-to | Sites where the persona works: `money`, `workplace`, `freelancing`, `softwareengineering`, `ux`, `pm`, `law`, ... (list: https://api.stackexchange.com/2.3/sites) |
| Discourse forums | `collect_discourse.py` | Posts of any public Discourse forum, full text, likes | Only Discourse hosts (a 404 on `/search.json` means it is not one); search matches words, so expect noise | Product communities of the tools the persona uses (no-code builders, open-source projects, SaaS user forums). A forum's `/about.json` answering JSON confirms Discourse |
| App Store | `collect_appstore.py` | Reviews of one app, rating, title and text | No date filter (paged until past the window), 10 pages of 50 at most, no per-review permalink (url is the app's review listing). The feed often answers empty for hours (health `empty`): retry later or with another `country` | The alternatives the persona uses today, in the founder's storefronts. App id: https://itunes.apple.com/search?term=<name>&entity=software |

## Through `import_records.py`

| Source | Why not collected | How it gets in |
|--------|-------------------|----------------|
| G2, Capterra, Trustpilot, Product Hunt | Answer 403 to servers | The founder exports or copies reviews into a CSV (`url,date,text` at least), `--format csv` |
| Reddit with the founder's own account | Reddit OAuth needs the founder's app credentials | The founder's export as JSONL or CSV |
| Exa, Perplexity, other paid search | Optional and paid, never called by the scripts | `exa search ... --json --text` (or `--highlights`) saved to a file, `--format exa-json`; a result without text or date is dropped |
| Blogs, newsletters, articles | No common API | Host web fetch, then one CSV row per passage with its url and publication date; label the speaker `press` or `other` when the author reports someone else's words |
| Interviews, support tickets, sales calls | Private | Only with the people's consent, anonymised, `source: interview`; never shipped in a public example |

## Language

One query bank per language, with the words people use in that language, not translations of the English queries. Communities in the language: national subreddits and their founder subreddits, local Discourse forums, the App Store storefront of the country (`country: fr`, `de`, `es`). Quotes stay in their original language; a consumer that needs English tags its own translation `[translated]` and keeps the original.

## Reading health

| Status | Means | Do |
|--------|-------|----|
| `ok` | at least one record in the window | read `capped`: a capped job keeps the newest records only, so its volume is a lower bound |
| `empty` | the source answered, nothing matched | an alert, not proof of silence: other words or communities once, then `sources-rejected.md` |
| `error` | the source refused or broke (4xx, 5xx, network, unexpected shape) | read `errors[0]`; a closed site or a wrong host goes to `sources-rejected.md` |
| `quota` | the source asked to slow down or the daily quota is spent | retry later with a smaller cap; never loop |
