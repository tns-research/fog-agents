# Schema gap checklist

Used by `analyzing-serp-competition/SKILL.md` and `auditing-geo-aeo/SKILL.md` to flag schema markup that's missing, miscoded, or duplicated.

Wrong schema is worse than missing schema: Google can devalue or generate manual penalties for incorrect markup.

---

## High-ROI schema types (audit for presence)

### BreadcrumbList

Mark up the breadcrumb trail at the top of every non-home page.

```json
{
  "@context": "https://schema.org",
  "@type": "BreadcrumbList",
  "itemListElement": [
    {"@type": "ListItem", "position": 1, "name": "Home", "item": "https://example.com/"},
    {"@type": "ListItem", "position": 2, "name": "Guides", "item": "https://example.com/guides/"},
    {"@type": "ListItem", "position": 3, "name": "Freelance Invoicing", "item": "https://example.com/guides/freelance-invoicing/"}
  ]
}
```

**Why**: Google renders breadcrumb-rich result; high-ROI for SERP appearance even without changing rank.

### Article (with author sub-graph)

Every article gets `Article` schema with `author` linked to a `Person` entity, which links via `sameAs` to LinkedIn / Twitter / personal site.

```json
{
  "@context": "https://schema.org",
  "@type": "Article",
  "headline": "...",
  "datePublished": "2025-09-15T...",
  "dateModified": "2026-04-12T...",
  "author": {
    "@type": "Person",
    "name": "Sarah Lin",
    "url": "https://example.com/author/sarah-lin",
    "sameAs": [
      "https://www.linkedin.com/in/sarahlin",
      "https://twitter.com/sarahlin"
    ]
  },
  "publisher": {
    "@type": "Organization",
    "name": "Acme",
    "logo": {"@type": "ImageObject", "url": "https://example.com/logo.png"}
  }
}
```

**Why**: foundational E-E-A-T signal + AEO citation eligibility.

### FAQPage

For Q-format content (FAQ section, troubleshooting article, How-to with questions).

See full example in `aeo-winning-patterns.md` Pattern 2.

**Why**: highest-ROI structured data for AI Overview citation in 2026.

### HowTo

For step-by-step content.

```json
{
  "@type": "HowTo",
  "name": "How to invoice in multiple currencies",
  "step": [
    {"@type": "HowToStep", "name": "Set default currency", "text": "..."},
    {"@type": "HowToStep", "name": "Add line items", "text": "..."}
  ]
}
```

**Why**: AI engines extract steps verbatim; HowTo schema makes the extraction explicit.

### Organization (on home + about)

```json
{
  "@type": "Organization",
  "name": "Acme",
  "url": "https://example.com",
  "logo": "https://example.com/logo.png",
  "sameAs": [
    "https://www.linkedin.com/company/acme",
    "https://twitter.com/acme"
  ],
  "contactPoint": {
    "@type": "ContactPoint",
    "contactType": "customer support",
    "email": "support@example.com"
  }
}
```

**Why**: brand-entity signal; helps AI engines establish "what is Acme".

### Product (for product pages, not just for retail)

For SaaS landing pages, `Product` schema with `Offer` sub-graph (price, availability, supported plans).

**Why**: Google rich-result eligibility for product queries; AI engines pull pricing from Offer schema directly.

### Review / AggregateRating (where legitimate)

Only when the page actually contains reviews. Faking AggregateRating is a manual-action trigger.

```json
{
  "@type": "AggregateRating",
  "ratingValue": "4.6",
  "reviewCount": "240"
}
```

**Why**: legitimate reviews boost CTR via stars in SERP. Fake reviews destroy trust and trigger penalties.

---

## Audit per page

Run the following on every top-priority page:

```yaml
schema_audit:
  url: ...
  found_types: [Article, BreadcrumbList]
  missing_high_roi:
    - FAQPage           # page has Q-format content but no schema
    - Author sub-graph  # Article schema present but author is just a string
  miscoded:
    - "Article schema missing dateModified"
    - "Person author lacks sameAs links"
  duplicated:
    - "Article + Product on same page (consolidate to one type)"
  recommendations:
    - "Add FAQPage with the 3 PAA questions from SERP analysis"
    - "Expand Article.author to a Person sub-graph with sameAs"
    - "Remove duplicate Product type (page is editorial, not transactional)"
```

---

## Validation

After applying schema fixes:

1. Validate via Google's Rich Results Test (manual, surfaced to founder).
2. Validate via `validator.schema.org` (manual).
3. Re-fetch URL inspection in GSC to confirm Google parses the markup.
4. Check Search appearance in GSC's Performance report (rich results filter) over the next 14-28 days.

---

## Common errors

| Error | Diagnosis |
|-------|-----------|
| Multiple Article schemas on one page | One page = one Article. Duplicate is a parser error. |
| FAQPage with non-FAQ content | Schema spam; Google ignores or penalizes. |
| HowTo with non-step content | Same. Schema must match content. |
| AggregateRating without visible reviews | Manual-action trigger. Remove. |
| Schema in HTML comments or data attributes | Parsers ignore. Use JSON-LD in `<script type="application/ld+json">` or microdata. |
| sameAs pointing to dead profiles | Devalues entity signal. Verify all sameAs URLs return 200. |
| Logo URL in Organization schema returns 404 | Organization entity rejected. Verify logo URL. |
| Article.author as string, not Person | Loses E-E-A-T sub-graph; expand to full Person object. |

---

## Anti-patterns to refuse

- **Adding schema for every type "just in case".** Schema overload is parser confusion. Pick types that match content.
- **Generating schema with AI without validating.** AI generates plausible-looking but invalid schemas regularly. Always run through validator.
- **Stuffing keyword variants into schema fields.** Names and headlines should match what's on the page, not be SEO-stuffed.
- **Adding Review schema based on testimonials on the page.** Testimonials are not Reviews unless they have rating + author + date. Use carefully.

---

## Source

Compiled from schema.org documentation, Google Search Central rich-results docs (2025-2026), and aggregate audit reports. Citation-lift figures referenced in `aeo-winning-patterns.md` are aligned with this checklist.
