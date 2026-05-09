# AEO winning patterns

Lookup table for the content patterns that drive citation in AI Overviews, Perplexity, and ChatGPT. Used by `auditing-geo-aeo/SKILL.md` Step E to translate diagnoses into specific fixes.

Citation-lift percentages cited below are from public 2025-2026 studies (Search Engine Land, Backlinko, AIPRM) and are directional, not contractual. The pattern presence matters more than the precise percentage.

---

## Top patterns (highest signal)

### 1. Question-first H2/H3 matching real prompts

Each section heading is a question, phrased the way a user would actually prompt an AI engine.

✅ "How do freelancers handle multi-currency invoicing?"
❌ "Multi-currency invoicing"

How to discover real prompts: People-Also-Ask box from `analyzing-serp-competition` output. PAA questions ARE the prompts users run.

**Effect**: AI engines look for direct question-answer pairs. Question-first H2 makes the answer immediately citable.

### 2. FAQPage schema with prompt-matched questions

Mark up an FAQ section at the bottom of every cluster page with `FAQPage` JSON-LD. Each question matches a real prompt (PAA or Perplexity-related-question).

```json
{
  "@context": "https://schema.org",
  "@type": "FAQPage",
  "mainEntity": [{
    "@type": "Question",
    "name": "How do freelancers handle multi-currency invoicing?",
    "acceptedAnswer": {
      "@type": "Answer",
      "text": "Most freelancers use ..."
    }
  }]
}
```

**Effect**: structured data is the cleanest signal of an answer; AI engines preferentially cite structured-marked content.

### 3. 40-word answer blocks at top of sections

The first paragraph after every H2/H3 should be a complete, self-contained ~40-word answer to the heading. Bold or call-out-styled.

✅ "Freelancers handle multi-currency invoicing by setting their default currency, adding alternate-currency line items, and using a tool that auto-converts at the invoice date's mid-market rate. The two common pitfalls are using last week's rate and forgetting to disclose the conversion fee on the invoice itself."

❌ A 600-word essay where the answer is buried in paragraph 4.

**Effect**: AI engines extract verbatim from the top of the section. A clear 40-word answer block is what gets cited.

### 4. Expert quotes with named source

A 2-3 sentence quote attributed to a named individual with a link to their public profile.

✅ "*'The biggest invoicing mistake I see freelancers make is undercharging for revisions.'*. Sarah Lin, freelance illustrator and Substack publisher of Designer Notebook"

**Effect**: ~+41% citation lift. AI engines treat named-expert content as more authoritative than anonymous prose.

### 5. Inline statistics with cited source

Specific numbers, in-line in the body, with the source credited inline (not just in a footer).

✅ "According to a 2025 Freelance Forward report, 38% of freelancers wait 30+ days to be paid (Upwork, 2025-09)."

❌ "Many freelancers wait a long time to get paid."

**Effect**: ~+30% citation lift. Statistics anchor citations because AI engines cite the **claim**, which carries the source attribution with it.

### 6. Inline citations in body (not just footnotes)

When making a factual claim, link inline to a primary source.

✅ "[The HMRC requires UK freelancers to retain invoices for 6 years](https://gov.uk/...)."
❌ "[1] HMRC, 2025."

**Effect**: ~+30% citation lift. Inline citation surfaces the source URL in the same DOM neighborhood as the claim, which AI parsers traverse together.

---

## Mid-tier patterns

### 7. Comparison tables with structured columns

For commercial-intent queries ("X vs Y", "best X for Y"), comparison tables with consistent columns (price, features, target user, free tier).

**Effect**: AI engines extract from tables more reliably than from prose. Table cells are cited verbatim.

### 8. Dated last-updated and truthful timestamps

Every page shows last-updated date in body (not just metadata). The date is truthful, pages updated when there's a real reason, not auto-bumped daily.

**Effect**: AI engines preferentially cite recent, dated content. Fake daily lastmod is detected and ignored.

### 9. Author byline + linked author page

Visible byline at the top of the article, linking to a persistent `/author/<slug>` page on the same domain. Author page contains credentials, contact, sameAs links to LinkedIn / Twitter / personal site.

**Effect**: foundational E-E-A-T signal. Without it, even good content is cited at lower rates.

### 10. HowTo schema where applicable

Step-by-step content marked with `HowTo` JSON-LD.

**Effect**: AI engines extract steps verbatim and often cite the source page when reproducing the steps.

### 11. Linkable fragments (anchor IDs on every H2/H3)

Every heading has an `id` that AI engines can deep-link to. The Overview can cite "yourdomain.com/post/#how-do-freelancers-...".

**Effect**: ~+15% citation lift; the page becomes more useful to cite because the cite can be specific.

### 12. Original data or research

Any first-party data the brand publishes (a survey, an internal benchmark study, a unique dataset).

**Effect**: high. Original data is cited preferentially over secondary summaries because it's the primary source.

---

## Anti-patterns (kill citation chances)

| Anti-pattern | Why it fails |
|--------------|--------------|
| Wall of text with no headings | AI parsers can't isolate answer blocks |
| Buried-lede ("In this post we'll discuss...") | Answer is not in the first 40 words; the page is skipped for shorter alternatives |
| Heavy keyword-stuffing in headings | AI engines downrank pattern-matchy SEO content as inauthentic |
| Auto-bumped lastmod with no real changes | Detected and devalued |
| Anonymous content (no author) | E-E-A-T-low; rarely cited |
| Article + Product + Review schema all on one page | Schema confusion; AI engines prefer clean single-type pages |
| Citing only your own internal pages | Looks promotional; reduces authority signal |
| Generic "industry experts say..." quotes | Named source required; anonymous quotes are not citable |

---

## How to apply during the audit

For each page diagnosed by `auditing-geo-aeo` as "ranks but not cited":

1. Run a 12-pattern check (above).
2. Identify the 3-5 patterns the page is missing.
3. Add to the fix list with effort estimates: schema + answer block changes are usually 1-2 hours each; bringing in expert quotes is 1-2 days; original data is a multi-week effort.
4. Sequence by ROI: schema + answer block first (highest leverage per hour), then expert quotes / statistics, then original data.

---

## Source

Synthesized from 2025-2026 public AEO studies (Search Engine Land, AIPRM citation analysis, Backlinko AI Overview benchmarks), schema.org guidelines, and aggregate E-E-A-T community research. Citation-lift figures are directional benchmarks, not guarantees.
