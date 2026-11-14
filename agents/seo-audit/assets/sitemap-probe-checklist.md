# Sitemap probe checklist

`scripts/crawl.py` runs this protocol automatically (Sitemap lines of robots.txt, `/sitemap.xml`, `/sitemap_index.xml`, sitemap indexes, gzip) and reports it in `crawl-summary.json`. Use this checklist to read that output, or by hand when the crawl cannot run.

---

## The probe sequence

Run each step in order. Stop when a sitemap is found and validated.

Fetch with the `scrape` provider resolved at the agent's Step 0 ([`../../../shared/tools.md`](../../../shared/tools.md)). Sitemaps and robots.txt are raw files, so plain `curl` needs no key and is enough; `firecrawl scrape <url> --format markdown`, `curl https://r.jina.ai/<url>` or the host web fetch work the same.

### 1. Standard locations

```bash
curl -sL -A "Mozilla/5.0" -o /dev/null -w "%{http_code} %{content_type}\n" "<domain>/sitemap.xml"
curl -sL -A "Mozilla/5.0" -o /dev/null -w "%{http_code} %{content_type}\n" "<domain>/sitemap_index.xml"
curl -sL -A "Mozilla/5.0" -o /dev/null -w "%{http_code} %{content_type}\n" "<domain>/sitemap-index.xml"
curl -sL -A "Mozilla/5.0" -o /dev/null -w "%{http_code} %{content_type}\n" "<domain>/sitemap.xml.gz"
curl -sL -A "Mozilla/5.0" -o /dev/null -w "%{http_code} %{content_type}\n" "<domain>/sitemaps/sitemap.xml"
# then fetch the body of the first one that answers 200 with an XML type
curl -sL -A "Mozilla/5.0" "<domain>/sitemap.xml"
```

### 2. robots.txt directive

```bash
curl -sL -A "Mozilla/5.0" "<domain>/robots.txt"
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

If none of these exist, the site has no sitemap or it is at a non-standard path: report `sitemap-missing` (crawl.py raises it) and list the sitemap as Unverified. The Step 0 message of the next run can ask the founder for its URL; this step never stops for it.

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

Even a valid sitemap may not be processed if it's never been submitted. With the Search Console API, check `gsc sitemaps list <site>` and submit with `gsc sitemaps submit <site> <sitemap-url>` if empty or missing. Without it, the founder checks Search Console > Sitemaps and submits there (no setup); otherwise mark submission status Unverified.

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
    - "Resubmit via gsc sitemaps submit"
```

---

## Anti-patterns to refuse

- **Reporting "no sitemap found" without running the full probe.** The standard locations are not exhaustive; robots.txt directive is the canonical source.
- **Fixing a sitemap problem without verifying GSC submission.** A valid sitemap not submitted to GSC is invisible to Google's discovery layer.
- **Recommending priority/changefreq tweaks.** Google has confirmed it ignores them. Don't waste audit recommendations on these fields.

---

## Source

Compiled from sitemaps.org spec, Google Search Central documentation (2025-2026), and aggregate community-reported pitfalls. Calibrated for founder-stage sites typically running WordPress/Webflow/Framer/Next.js.
