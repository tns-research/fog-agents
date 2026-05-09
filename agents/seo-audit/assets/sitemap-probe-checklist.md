# Sitemap probe checklist

Used by `analyzing-gsc-data/SKILL.md` Step F when the GSC sitemap report is empty or stale, and as a sanity check on every audit.

---

## The probe sequence

Run each step in order. Stop when a sitemap is found and validated.

### 1. Standard locations

```bash
firecrawl scrape "<domain>/sitemap.xml" --format markdown --only-main-content
firecrawl scrape "<domain>/sitemap_index.xml" --format markdown --only-main-content
firecrawl scrape "<domain>/sitemap-index.xml" --format markdown --only-main-content
firecrawl scrape "<domain>/sitemap.xml.gz" --format markdown --only-main-content
firecrawl scrape "<domain>/sitemaps/sitemap.xml" --format markdown --only-main-content
```

### 2. robots.txt directive

```bash
firecrawl scrape "<domain>/robots.txt" --format markdown --only-main-content
```

Parse the `Sitemap:` directive (case-insensitive, multiple allowed). This is the discovery hint Google itself uses.

```
User-agent: *
Disallow: /admin
Sitemap: https://example.com/sitemap.xml
Sitemap: https://example.com/blog-sitemap.xml
```

### 3. CMS-specific defaults

| CMS | Common path |
|-----|-------------|
| WordPress / Yoast | `/sitemap_index.xml` |
| Webflow | `/sitemap.xml` |
| Framer | `/sitemap.xml` |
| Next.js (default) | `/sitemap.xml` |
| Shopify | `/sitemap.xml` (auto-generated, includes products) |
| Wix | `/sitemap.xml` |
| Ghost | `/sitemap.xml` |

If none of these exist, the site has no sitemap or it's at a non-standard path. Ask the founder.

---

## Validation checks

For the sitemap that's found:

| Check | Pass condition |
|-------|----------------|
| Status code | 200 (not 404, not 301, not 5xx) |
| Content-Type | `application/xml` or `text/xml` |
| Top-level element | `<urlset>` or `<sitemapindex>` |
| URL count | <50,000 per file (>50K requires sitemap-index splitting) |
| File size | <50 MB uncompressed (>50 MB requires sitemap-index splitting) |
| `<lastmod>` present | Recommended; truthful timestamps only |
| `<changefreq>` and `<priority>` | Optional; Google ignores them |
| URLs are absolute and canonical | Not relative, not non-canonical |
| URLs return 200 | Spot-check 5 random URLs |
| URLs are indexable | Not blocked by robots.txt, not noindex |
| URLs match canonical | The URL in sitemap matches the page's `<link rel="canonical">` |

---

## Common pitfalls

### Pitfall 1: Stale lastmod (auto-bumped daily)

Google detects fake daily lastmods and ignores them. The lastmod must reflect actual content changes. If every URL has today's date, treat the sitemap's lastmod as untrusted.

### Pitfall 2: Sitemap includes non-indexable URLs

URLs with noindex, blocked by robots.txt, returning 404, or 301-redirected should not be in the sitemap. They confuse Google about indexing priority.

### Pitfall 3: Mismatch between Sitemap directive in robots.txt and actual location

Robots.txt says `Sitemap: https://example.com/sitemap.xml` but the actual sitemap is at `/sitemap_index.xml`. Google follows the directive; if it's wrong, the sitemap is invisible.

### Pitfall 4: Gzipped variant without correct Content-Encoding

`/sitemap.xml.gz` works only if the server returns the file with `Content-Encoding: gzip` and `Content-Type: application/xml`. Plain `.gz` MIME doesn't work.

### Pitfall 5: Sitemap has 50K+ URLs in one file

Beyond 50K URLs or 50 MB, Google splits indexing across the file inconsistently. Use a sitemap-index referencing multiple sub-sitemaps each <50K URLs.

### Pitfall 6: Sitemap not submitted to GSC

Even a valid sitemap may not be processed if it's never been submitted via `gsc sitemaps add`. Check `gsc sitemaps list`, if empty or sitemap not present, submit it.

### Pitfall 7: International / hreflang sitemaps

For multi-language sites, each URL should have hreflang annotations (either inline `<xhtml:link>` in the sitemap or in the page `<head>`). Missing hreflang is a common discovery gap on FR/EN dual sites.

---

## Output

Append to the audit JSON:

```yaml
sitemap:
  found: true
  url: https://example.com/sitemap_index.xml
  type: sitemap_index | urlset
  total_urls: 423
  validation:
    all_200: true
    all_canonical: true
    truthful_lastmod: true
    no_noindex: true
  pitfalls_detected: []
  gsc_submitted: true
  gsc_last_processed: 2026-04-15
  recommendations: []
```

If pitfalls detected:

```yaml
sitemap:
  ...
  pitfalls_detected:
    - "Auto-bumped lastmod (every URL has today's date)"
    - "12 URLs in sitemap return 404"
  recommendations:
    - "Configure CMS to set lastmod only on real edits"
    - "Remove the 12 broken URLs (list in JSON)"
    - "Resubmit via gsc sitemaps add"
```

---

## Anti-patterns to refuse

- **Reporting "no sitemap found" without running the full probe.** The standard locations are not exhaustive; robots.txt directive is the canonical source.
- **Fixing a sitemap problem without verifying GSC submission.** A valid sitemap not submitted to GSC is invisible to Google's discovery layer.
- **Recommending priority/changefreq tweaks.** Google has confirmed it ignores them. Don't waste audit recommendations on these fields.

---

## Source

Compiled from sitemaps.org spec, Google Search Central documentation (2025-2026), and aggregate community-reported pitfalls. Calibrated for founder-stage sites typically running WordPress/Webflow/Framer/Next.js.
