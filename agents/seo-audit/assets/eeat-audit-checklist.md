# E-E-A-T audit checklist

E-E-A-T (Experience, Expertise, Authoritativeness, Trust) is Google's quality framework, expanded with the first "E" (Experience) in December 2022 (Google Search Central blog, 2022-12-15, https://developers.google.com/search/blog/2022/12/google-raters-guidelines-e-e-a-t). It describes what Google's quality raters look for; it is not a single ranking factor, so this checklist finds weak signals, it does not predict a ranking change.

Used at Step 8 of `AGENT_SEO_AUDIT.md` to comment the measured signals of `eeat.json` (`scripts/eeat.py`), by `auditing-geo-aeo/SKILL.md` Step E when a page ranks but is never cited, and by `mapping-content-clusters/SKILL.md` to evaluate whether a pillar can credibly hold topical authority.

---

## The four signals

### Experience - first-hand involvement

Has the author actually done the thing they're writing about? Specifics that prove first-hand experience:

| Check | What to look for |
|-------|------------------|
| First-person account | "I tested X for 3 months..." rather than "X is a tool that..." |
| Specific numbers | "I sent 240 invoices in 2025", concrete, dated |
| Original screenshots | UI screenshots from the author's actual usage, dated |
| Dated events | "In Q2 2025, I switched from..." |
| Limitations honestly named | "X works for solo freelancers but breaks at 5+ team members because..." |

Pages with no first-hand markers are pure secondary content. Treated as low-Experience.

### Expertise - qualified to speak

Author credentials that are verifiable.

| Check | What to look for |
|-------|------------------|
| Named author | Real name, not "Editorial Team" or "Admin" |
| Bio with credentials | Education, prior roles, specific years of experience |
| Persistent author page | `/author/<slug>` URL on the domain, linkable |
| External profile links | LinkedIn, Twitter/X, personal site (sameAs schema) |
| Topic-relevant credentials | A finance writer with finance background, not a generic content marketer |
| Publication history | Other articles on related topics by the same author, on this site or elsewhere |

### Authoritativeness - the site/author is recognized

Whether the broader web treats this content/author as authoritative.

| Check | What to look for |
|-------|------------------|
| Backlinks from authoritative sources | Domain has been cited by recognized industry sites |
| Wikipedia mentions | The brand or author appears on Wikipedia |
| Press mentions | Linked press coverage on the domain (linked, not screenshotted) |
| Organization schema with sameAs | Brand entity established with official social links |
| Speaker / author at named events | Conference talks, named podcast appearances |
| Industry certifications | Official designations where applicable (CPA, MD, CFA, etc.) |

### Trustworthiness - the foundation

| Check | What to look for |
|-------|------------------|
| HTTPS, no mixed content | Basic table stakes |
| Visible contact info | Real email, phone, or office address |
| Visible privacy + terms pages | Linked from footer |
| About page with team | Real photos, real bios, not stock |
| No misleading claims | No "guaranteed results", no fabricated stats |
| Clear ownership / publisher | Who runs this site? |
| Refund / return policies | For commercial sites |
| Disclosed conflicts of interest | Affiliate disclosure where applicable |

---

## Measured by script, commented by the model

The score is not the model's: `scripts/eeat.py` measures the signals below on `crawl.jsonl` (served HTML) and scores them with the fixed weights of [`eeat-weights.json`](eeat-weights.json) (formula in its `_comment`). Same crawl, same weights, same `--today`: same `eeat.json`. The model copies the scores, comments the missing signals and proposes the fix; it never rates a page, never edits a score, and `scripts/check_report.py --eeat` blocks a score that differs from `eeat.json` or a hand rating such as "Expertise 2/4".

| Pillar | Signal in `eeat.json` | Measured from |
|--------|-----------------------|---------------|
| Expertise | `author_visible` | byline element (class or id `author` / `byline`, `itemprop=author`, `a[rel=author]`) with text |
| Expertise | `author_schema` | JSON-LD `author` of the article (string, Person, `@id` resolved), microdata author |
| Expertise | `author_page_linked` | byline link, `rel=author` or JSON-LD `author.url` to an internal page answering 200 |
| Trust | `date_published`, `date_modified` | JSON-LD dates, `article:*_time` meta, `itemprop`, `<time>`, dated "Published" / "Updated" phrases |
| Trust | `date_visible` | a `<time>` with text or a dated phrase a reader sees |
| Trust | `freshness` | days between the update date and the run date |
| Authoritativeness | `external_sources` | outbound links to other sites, social networks and the site's own hosts excluded |
| Authoritativeness | `citations` | `blockquote[cite]`, `q[cite]`, `<cite>`, footnote links, a reference-list heading |
| Trust (site) | `about_page`, `contact_page`, `legal_page`, `privacy_page` | crawled 200 pages whose path names them |
| Authoritativeness (site) | `organization_schema`, `organization_same_as` | Organization-type JSON-LD and its `sameAs` |
| Trust (site) | `reviews_marked_up`, `testimonial_blocks` | Review / AggregateRating markup; testimonial blocks are reported, not scored |
| Expertise (site) | `author_pages` | distinct author pages linked from the articles |

Every signal comes with its evidence (selector, JSON-LD path, URL and crawl line, or the excerpt). A missing signal is a fact of the served HTML: check it on the page before writing the fix.

### What stays a comment

Experience cannot be measured by a parser: first-person accounts, specific dated numbers, original screenshots, limits named honestly. The model reads the priority pages and quotes what it sees, without a score:

```markdown
### https://acme.example/blog/x/ (crawl.jsonl:7), E-E-A-T score 59 (eeat.json)

- Missing signals (eeat.json): `author_visible`, `date_modified`.
- Comment: the article has a JSON-LD author but no byline a reader sees; add the byline linked to /authors/<slug>/ and the update date in the layout.
- Experience markers read on the page: "we sent 240 invoices in March" (paragraph 2). No original screenshot.
```

Authoritativeness beyond the site (backlinks, press, Wikipedia) is outside the crawl: report it only from a sourced tool output, otherwise write Unverified.

---

## Common patterns and diagnoses

| Symptom | Bottleneck | Fix |
|---------|------------|-----|
| Founder personally writes everything but isn't credited | Expertise (gap is just visibility) | Add bylines + author page; cheap fix |
| Content is summary of secondary sources | Experience | Add first-hand specifics; harder fix |
| Site is anonymous (no team page, no contact) | Trust | Build out about page; medium fix |
| Site is new with no backlinks | Authoritativeness | Time-and-effort issue; surface as 6-month roadmap, not 7-day fix |
| Site has all signals but content is thin | All four collapsed because content fails everywhere | Re-audit content depth before E-E-A-T efforts |

---

## Anti-patterns to refuse

- **Auto-generating fake author pages.** AI-generated bios for fictional experts are a violation; they will be caught. Use real authors.
- **Stock photos for team members.** Reverse image search catches them. Real photos or no photos.
- **Padding bios with vague credentials.** "Industry expert with 10+ years of experience" is not a credential; it's filler. Specific roles, named companies.
- **Scoring E-E-A-T by hand.** A 0-4 or 0-15 rating moves from one run to the next; the score is `eeat.json`, the model comments it.
- **Citing your own pages as "expert sources".** Self-citation is not E-E-A-T. External authoritative citations are.
- **Treating E-E-A-T as a Google-only concept.** AI engines (Perplexity, ChatGPT) weight similar signals. The audit serves both surfaces.

---

## Source

Compiled from Google Quality Rater Guidelines (December 2022 + 2024 + 2026 updates), Search Engine Land's E-E-A-T post-March-2026 analyses, and the Sistrix / SEMrush studies on the March 2026 core update. Calibrated for founder-stage sites where formal credentials are often modest but first-hand experience is high.
