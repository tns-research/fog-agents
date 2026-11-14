# References

API documentation of the optional providers, read by the connectors. Check the endpoint when a provider changes its API; the connectors fail with an `error` health status (never a crash) when an answer does not parse.

| Provider | Documentation | Endpoint used |
|----------|---------------|---------------|
| Plausible Stats API v2 | https://plausible.io/docs/stats-api | `POST /api/v2/query`, dimensions `time:day` and `event:goal` |
| Umami API | https://umami.is/docs/api | `GET /websites/{id}/pageviews` (unit day), `GET /websites/{id}/events/series` |
| Umami Cloud API keys | https://umami.is/docs/cloud/api-key | header `x-umami-api-key`, base `https://api.umami.is/v1` |
| GA4 Data API | https://developers.google.com/analytics/devguides/reporting/data/v1 | `POST properties/{id}:runReport`, dimensions `date`, `eventName` |
| Search Console API | https://developers.google.com/webmaster-tools/v1/searchanalytics/query | `POST sites/{site}/searchAnalytics/query`, dimensions `date`, `query`, `page` |
| Search Console data delay | https://support.google.com/webmasters/answer/96568 | why a Monday run sees the week as stale |
| Zernio daily metrics | https://docs.zernio.com/analytics/get-daily-metrics | `GET /analytics/daily-metrics`, `attribution`, `platform`, `profileId` |
| Zernio follower stats | https://docs.zernio.com/accounts/get-follower-stats | `GET /accounts/follower-stats`, `granularity=daily` |
| Zernio limits and prices | https://docs.zernio.com/guides/rate-limits, https://docs.zernio.com/pricing | per-second window on analytics, cache, X reads billed at X's rate |
| Stripe charges | https://docs.stripe.com/api/charges/list | `GET /v1/charges`, `created[gte]`, `created[lte]`, `starting_after` |
| Stripe restricted keys | https://docs.stripe.com/keys#limit-access | a read-only key for charges is enough |
| gsc CLI (cli-skills) | https://github.com/the20100/cli-skills | any tool that writes Search Console API JSON works as the `json` provider |

## Methods

- AARRR ("pirate metrics"): Dave McClure, "Startup Metrics for Pirates" (2007), https://www.slideshare.net/dmc500hats/startup-metrics-for-pirates-long-version
- ICE scoring (impact, confidence, ease): used here as a ranking aid only, never as a forecast.
- Noise bands: a Poisson approximation for counts of independent events, widened to the observed spread of the reference weeks; the two-proportion standard error for rates. Conventions to filter noise on small sites, not significance tests: see the comments of `assets/pulse-rules.json`.
- Search Console decline: the same thresholds as the `decline` object of seo-audit's `gsc-bands.json`, mirrored in `assets/pulse-rules.json` and kept equal by the selftest.
