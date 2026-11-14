---
name: linking-internal-pages
description: Internal linking of the audited site. scripts/links.py audit reads crawl.jsonl (anchor text and zone of every internal link, text blocks of each body) and bands.json, measures body inlinks apart from nav, footer and template links, flags orphans, pages reached only from the menu, quick wins with too few links, deep pages, generic and repeated anchors, links that go through a redirect or to an error page, then proposes links to add on words each source page already wrote, matched against the target's Search Console queries, H1, slug and title. scripts/links.py patch turns them into patches of the site repository checked by git apply. Use at every audit after the crawl and the bands, and in write mode before publishing a new article (inbound links). Triggers on "internal linking", "maillage interne", "internal links", "orphan pages", "link to my new article", "which pages should link to".
license: Apache-2.0
compatibility: Claude Code, Cursor, Codex CLI, Gemini CLI
metadata:
  version: "1.0"
allowed-tools: Read Write Bash(python3:*) Bash(git:*)
---

# linking-internal-pages

A page that no article links to waits for the crawler to find it in the sitemap, and Google reads the anchor of each link as a description of the page it points to. Menus and footers repeat the same links on every page, so they say little about any one page: the links that count are the ones inside the text. This skill measures those, then adds the missing ones where the site already wrote the words.

The script never writes prose. An anchor is always a phrase that already sits in a sentence of the source page; the link wraps it, nothing else in the sentence changes.

Thresholds: `assets/link-rules.json`, overridden by a `links` object in the project's `config.json`.

## Step A: audit

Inputs: `R/crawl.jsonl` from `crawl.py` (it records `internal_anchors` and `text_blocks`; a crawl file without `internal_anchors` exits 2 and asks for a new crawl), `R/bands.json` when Search Console is available.

```
python3 scripts/links.py audit --crawl R/crawl.jsonl --bands R/bands.json --out-dir R/links --config <project>/seo-audit/config.json --today <YYYY-MM-DD>
```

What it counts as a body link: an `<a>` outside `nav`, `header`, `footer` and `aside`, and not repeated with the same anchor on at least 30 % of the pages of its language (a "read the guide" card in every article is template, not text). Defects, most severe first:

| Code | Meaning | What to do |
|---|---|---|
| `orphan` | no page links to it | link it from the closest article, or remove it from the sitemap |
| `orphan-body` | only the menu, footer or template reach it | a link from an article body; info only for a menu entry with 10 or more nav inlinks |
| `weak-inlinks` | position 4 to 20 in Search Console, or a new page, with fewer than 3 body inlinks | the links proposed for it first |
| `deep-page` | 4 clicks or more from the home page | a link from a page closer to the home page |
| `anchor-generic` | "read more", "ici", "en savoir plus" | rewrite the anchor with the subject of the target page |
| `anchor-monotone` | one short anchor carries more than 70 % of the body links of a page | vary the anchors in the next edits |
| `link-to-redirect` | the link answers a redirect | patch to the final URL (`R01`...) |
| `link-broken` | the link answers 4xx or 5xx | `repo_fix.py` patches it |
| `dead-end` | the body links to no other page (info) | one or two links to the closest pages |

Then the links to add (`L01`...). For each target page the script builds phrases from its Search Console queries (`bands.json`), its H1, its URL slug and its title without the brand. It scans every text block of every other page of the same language, outside the links already there, and keeps a match when:

- the target is not the home page, a legal page or a listing;
- the source does not already link to the target from its body, is not a legal page, and is not a listing page (more than 50 body links: its excerpts change with every article);
- the source page is not itself about those words (they are not in its own title, H1 or URL);
- the words do not run across punctuation and are not part of a longer name (`NYSE OPEN Venture Capital Unicorn`).

Scores favour new pages, pages without body links, quick wins and deep pages; strong source pages (body inlinks, clicks); and pages on the same subject. Caps: 3 new links per source page, 1 per paragraph, 5 per target, the same anchor at most twice for one target. Confidence is `high` for a Search Console query or a declared keyword, or an anchor of three words or more on a page of the same subject.

Read `R/links/links.md` before using it: drop a suggestion whose sentence reads wrong with a link (a quote, a list of competitors where the link would look like an endorsement), and note why in the run log. The report section "Internal linking" is `links.md`, trimmed to what the founder should act on.

## Step B: a new article (write mode)

Before publishing, give the draft as a page that does not exist yet:

```
python3 scripts/links.py audit --crawl R/crawl.jsonl --bands R/bands.json --new-page /blog/<slug>/=A/final.md --out-dir A/links
```

The new page gets phrases from the frontmatter keyword (`keyword`, `keywords`, `primary_keyword`, `focus_keyword`, `target_keyword`, `query`), its title and its H1, plus shorter pieces of the keyword and H1 that no existing page owns in its title, H1, URL or queries. The outbound links of the article itself are checked by `write_article.py check`; this step adds the inbound ones. The patches of Step C point at a URL that answers 404 until the article is online: apply them in the same deploy as the article.

## Step C: patches (with `repo_path`)

```
python3 scripts/links.py patch --out-dir R/links --repo <repo_path> [--only L01,L04,R01]
```

For each link, the script finds the source file of the page (the file whose path maps to the URL, a frontmatter slug or permalink, else the single file holding its H1 or title; among several, the one named after the URL slug), then the single line that holds the anchor outside any link, tag, inline code, code fence, heading, import or frontmatter. It wraps the words in `[anchor](/path/)` in `.md` and `.mdx`, in `<a href="/path/">anchor</a>` elsewhere. A redirect fix replaces the old href with the final URL in the source files of the linking pages and the components they import. One patch per file in `R/links/repo/patches/`, each checked by `git apply --check` on a temporary copy; the repository is never written. Exit 1 when a check fails.

A phrase found on zero or several lines, wrapped across two lines, split by formatting (`**burn** rate`), or only in a shared component is listed "to place by hand" in `R/links/links-patch.md` with the reason: no guessed patch. After the deploy, `verify_served.py --check-links` on the changed pages.

## Failure modes

- **Old crawl.** `crawl.jsonl` without `internal_anchors`: rerun `crawl.py`.
- **Local build served by a folder server.** Folder listings (`Index of /`) are dropped; routes the server cannot map (`/contact/` built as `contact.html`) show as `link-broken` that production does not have. Check one in production before reporting it.
- **Stale build.** The text of the build and the text of the repository differ: the patch lists the link to place by hand. Rebuild before the crawl when the repository moved.
