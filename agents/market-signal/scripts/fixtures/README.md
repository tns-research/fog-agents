# fixtures/

Frozen inputs of `selftest.py`. Nothing here is fetched at test time.

Fictional data: every review, post, article excerpt, title, author, id and URL below is invented; any resemblance to real people, posts, products or companies is coincidental. Only the shape of each API answer, and the two error messages marked as such, come from the real services.

| Folder | What it is | Fictional or synthetic |
|--------|-----------|-------------------|
| `appstore-ok/` | One page of the iTunes review feed for a fictional business bank app (Comptoir Pro, fake app id, fr storefront), four entries | fictional reviews in the shape of a real answer; reviewer names are pseudonyms, review ids fake |
| `se-closed-site/` | Stack Exchange API answer for the closed site `startups`: HTTP 400 "No site found" | real API error message, no user content |
| `discourse-not-found/` | A forum host that is not Discourse (`community.nocode.example`): HTTP 404 on `/search.json` | synthetic 404 page |
| `reddit-throttled/` | Arctic Shift answering HTTP 422 "Timeout. Maybe slow down a bit" to a comment search | real API error message, no user content |
| `import/synthetic-reviews.csv` | A G2-style review export for a fictional product, with one undated row and one row outside the window | synthetic, fictional reviewers |
| `import/exa-april-q0.txt` | The first two results of an Exa query as the CLI prints them, with no text and no date: the import drops both | fictional titles and `.example` URLs, pseudonymous bylines |
| `april-2026/` | Regression case of an unchecked run: `corpus.jsonl` holds excerpts of invented articles (`.example` URLs, fictional campus, funds and accelerators), `citations.json` quotes cited the way an unchecked run prints them, each with one defect (2018 and 2020 texts in a 90-day window, recapitalised, elided, absent), plus one citation by record id and passage that passes | fictional reconstruction |

The synthetic HTTP 429 of the Hacker News quota test is written by `selftest.py` into its temporary folder and never committed.

Each fixture file is named after the SHA-1 of the URL the collector requests (`mslib.Fetcher`); a collector run with `--record <folder>` writes new ones, scrubbed (`mslib.scrub`: handles pseudonymised, contact details and profile links replaced) and ASCII-escaped so third-party text never trips the repo's dash check.
