# Article template (mode write)

Shape of `draft.md` and `final.md` in `<project>/seo-audit/articles/<slug>/`. The model writes both; `scripts/write_article.py check` reads them. Everything between angle brackets is replaced; nothing of this explanation stays in the file.

```markdown
---
title: "<title tag, at most title_max_chars of assets/crawl-rules.json>"
description: "<meta description, description_min_chars to description_max_chars>"
---

# <H1: the topic in the reader's words>

<Two sentences that answer the topic directly. A reader or an answer engine that stops here has the answer.>

<Context, the facts that support the answer, one outbound link to the primary source of the strongest fact.>

## <H2 of a must group of outline.json, in your wording>

<Two sentences that answer this H2 directly.>

<Details, examples, a list or a table when the content is a list or a comparison.>

### <H3 when the section has parts>

<...>

## <FAQ heading in the article language: FAQ, Questions fréquentes>

### <People also ask question 1, as people ask it>

<Two to four sentences, self-contained: they are read out of context.>

### <People also ask question 2>

<...>
```

Rules the check enforces (thresholds in `assets/write-rules.json`, overridable by `write` in config.json):

- `final.md` has 15 to 25 % fewer words than `draft.md` (the concision pass);
- 1 to 4 links to other sites, at least 2 links to 200 pages of the site, written absolute or root-relative;
- every `must` H2 of `outline.json` covered by an H2 or an H3 (FAQ apart), or one line `h2-NN: reason` in `decisions.md`;
- one H1; an FAQ with 2 questions or more when People also ask was captured;
- no placeholder, no production jargon (`assets/pipeline-jargon.json`), no banned word of `context.json`, no long dash;
- title and description inside the bounds of `assets/crawl-rules.json`.

No image placeholder in the body: visuals come from `visuals.json` (skill `rendering-article-visuals`) and `assemble` inserts them after the first paragraph of their H2. No frontmatter beyond `title` and `description` (and optional `tags`): `assemble` writes the site's frontmatter.
