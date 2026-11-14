# Carousel: <title>

**Project:** <project-slug> · **Date:** <YYYY-MM-DD> · **Language:** <fr | en> · **Format:** <linkedin | instagram | square>, <N> slides
**Direction:** <direction id> · **Cover hook:** <hook id and text>
**Status:** <ready | delivered with open issues>

<If anything is open, list it here first: QA errors left, warnings accepted, review items not fixed.>

---

## 1. Angle

**Kernel:** <what the reader knows after the last slide>
**Angle chosen:** <title>, <why, one line>
**Other angles considered:** <one line each, and why not>

## 2. Slides

| # | Role / layout | Tone | Content (title or lead) | Material | Source |
|---|---------------|------|-------------------------|----------|--------|
| 1 | cover / cover-a | calm | <hook> | <photo, object> | <source id> |
| 2 | content / stat | calm | <value + label> | | <source id> |
| ... |

## 3. Sources

| id | Source and URL | Accessed | Used on slides |
|----|----------------|----------|----------------|

## 4. Quality

- **qa.json:** <PASS/FAIL>, <errors>, <warnings> (list accepted warnings with the reason)
- **Visual review:** <rounds>, rubric <score>/24, by <model | founder>
- **Fresh reviewer:** <PASS/FAIL>, <score>/24, <main points and what was revised> (or "not run")
- **Writing gate:** <pass, BLOCK count fixed> · **Claims:** <all data blocks sourced>

## 5. Files

| File | Use |
|------|-----|
| `export/carousel.pdf` | LinkedIn document post |
| `export/slide-01.jpg` ... | Instagram carousel |
| `export/slide-01.png` ... | archive, other tools |
| `export/contact-sheet.jpg` | overview at 25 % |
| `captions.md` | post texts, first comment, alt text, sources |
| `export/video-<aspect>.mp4` (optional) | LinkedIn native video, Instagram feed video (4:5) or Reel (9:16); duration, size and QA from `video-<aspect>.json` |
| `deck.json` | the source: every change goes here |

## 6. Posting notes

- LinkedIn: upload the PDF as a document, title "<meta.title>", post text from `captions.md`, links in the first comment.
- Instagram: upload the JPEGs in order, caption and hashtags from `captions.md`, alt text per image (Advanced settings).

## Methodology

- Tools: web_search <provider | none>, scrape <provider | none>, vision <builtin | founder>, critic <subagent | session | founder | not run>, copy_lint <local | manual>, image_gen <not used | provider>.
- Engine: build.py, fit.js, render.py (Chromium <version>), qa.py.

## Limitations

- <skipped capabilities, fonts that fell back, sources not reachable, material missing>
