# Growth pulse: swanbase, week 2026-W41

Week 2026-W41 (2026-10-05 to 2026-10-11), compared with 2026-W40 and with the mean of the 4 weeks before it. Generated on 2026-10-14 from `pulse.json` (inputs hash `49451941b28e`). Every figure below comes from that file or from `experiments-20261014.json`; this is a fictional example run on invented data.

## Summary

- LinkedIn impressions reached 14365 against a 4-week mean of 6402 (+124.4%), in the week of the first weekly carousel. Last run's carousel experiment E-20260930-1 met its threshold.
- Site visitors held at 529 against a 4-week mean of 559.5: inside the noise band of 53.2, so no visible change in traffic.
- Search clicks fell to 72 from 124 (-41.9%), a decline by the shared Search Console definition, cause position: the average position went from 9.7 to 12.1.
- Activation stayed inside the noise: 36 apply clicks against a mean of 48.8, a visitor-to-apply rate of 6.8% against 8.7%.
- Revenue and referral counts are too small for percentages this week (3 payments, 3 invite links copied): read them as counts.

## Source health

| Source | Provider | Status | Days with data | Report week complete | Note |
|---|---|---|---:|---|---|
| plausible | none | missing | 0 | no | not configured, no API key and no CSV: in Plausible, Export > CSV, unzip, pass visitors.csv with --csv; add a date,event,count file for daily goal conversions |
| umami | fixture | ok | 42 | yes | complete |
| ga4 | none | missing | 0 | no | not configured, no API key and no CSV: in GA4, open the report, Share > Download CSV (one table by Date with Active users, Sessions, Views; one by Date and Event name with Event count) and pass the files with --csv |
| gsc | fixture | ok | 42 | yes | complete |
| social | csv | ok | 42 | yes | complete |
| revenue | csv | ok | 42 | yes | complete |

Plausible and GA4 are not connected; Umami covers web traffic on its own. Every connected source has the full report week.

## This week by stage

"Read" compares the week with the 4-week mean. A metric marked flat moved less than its noise band; small volume means fewer than 30 events, shown as counts.

#### Acquisition

| Metric | This week | Last week | Change | 4-week mean | vs 4 weeks | Read |
|---|---:|---:|---:|---:|---:|---|
| Search clicks | 72 | 124 | -52 (-41.9%) | 159.8 | -87.8 (-54.9%) | worse |
| Search CTR | 2.6% | 4.2% | -1.7 pts | 5.4% | -2.8 pts | worse |
| Search impressions | 2812 | 2925 | -113 (-3.9%) | 2963.2 | -151.2 (-5.1%) | worse |
| Average search position | 12.1 | 9.7 | +2.4 | 9.4 | +2.7 | worse |
| Instagram engagements | 97 | 76 | +21 (+27.6%) | 75.2 | +21.8 (+28.9%) | better |
| Instagram new followers | 5 | 5 | 0 | 4 | +1 | flat (within noise) |
| Instagram impressions | 764 | 798 | -34 (-4.3%) | 868.2 | -104.2 (-12%) | flat (within noise) |
| Instagram posts published | 2 | 2 | 0 | 2 | 0 | flat (within noise) |
| LinkedIn link clicks | 183 | 66 | +117 (+177.3%) | 72.2 | +110.8 (+153.3%) | better |
| LinkedIn engagements | 280 | 153 | +127 (+83%) | 138.2 | +141.8 (+102.5%) | better |
| LinkedIn impressions | 14365 | 6505 | +7860 (+120.8%) | 6402 | +7963 (+124.4%) | better |
| Pageviews (umami) | 1055 | 981 | +74 (+7.5%) | 1065 | -10 (-0.9%) | flat (within noise) |
| Visitors (umami) | 529 | 536 | -7 (-1.3%) | 559.5 | -30.5 (-5.5%) | flat (within noise) |

#### Activation

| Metric | This week | Last week | Change | 4-week mean | vs 4 weeks | Read |
|---|---:|---:|---:|---:|---:|---|
| Event apply_click (umami) | 36 | 53 | -17 (-32.1%) | 48.8 | -12.8 (-26.2%) | flat (within noise) |
| Event newsletter_signup (umami) | 13 | 12 | +1 | 11.2 | +1.8 | flat (within noise) |
| Visitor to apply_click rate (umami) | 6.8% | 9.9% | -3.1 pts | 8.7% | -1.9 pts | flat (within noise) |
| Visitor to newsletter_signup rate (umami) | 13 of 529 | 12 of 536 | small volume | 2% | small volume | small volume |

#### Retention

| Metric | This week | Last week | Change | 4-week mean | vs 4 weeks | Read |
|---|---:|---:|---:|---:|---:|---|
| Payments from returning customers | 3 | 1 | +2 | 1.2 | +1.8 | flat (within noise) |

#### Referral

| Metric | This week | Last week | Change | 4-week mean | vs 4 weeks | Read |
|---|---:|---:|---:|---:|---:|---|
| Instagram reposts and shares | 5 | 3 | +2 | 4.5 | +0.5 | flat (within noise) |
| LinkedIn reposts and shares | 17 | 8 | +9 | 7.8 | +9.2 | better |
| Event invite_link_copied (umami) | 3 | 2 | +1 | 2.5 | +0.5 | flat (within noise) |
| Visitor to invite_link_copied rate (umami) | 3 of 529 | 2 of 536 | small volume | 10 of 2238 | small volume | small volume |

#### Revenue

| Metric | This week | Last week | Change | 4-week mean | vs 4 weeks | Read |
|---|---:|---:|---:|---:|---:|---|
| Revenue, gross | 420.00 EUR | 240.00 EUR | +180.00 EUR | 375.00 EUR | +45.00 EUR | small volume |
| Revenue, net of refunds | 420.00 EUR | 240.00 EUR | +180.00 EUR | 375.00 EUR | +45.00 EUR | small volume |
| New paying customers | 0 | 1 | -1 | 0.8 | -0.8 | flat (within noise) |
| Payments | 3 | 2 | +1 | 2 | +1 | flat (within noise) |
| Refunds | 0.00 EUR | 0.00 EUR | 0.00 EUR | 0.00 EUR | 0.00 EUR | small volume |

## What moved

**LinkedIn reach, without more site visits.** LinkedIn impressions went from 6505 to 14365, link clicks from 66 to 183 and engagements from 153 to 280. The founder logged the carousel on 2026-10-06 and a recap post on 2026-10-08, in the same week. Site visitors did not follow: 529 against 536 the week before, and the day-by-day correlation between LinkedIn impressions and visitors stays weak (C3 and C4 below). The reach grew; the visits to the site did not grow with it.

**Search Console, position first.** Clicks fell from 124 to 72 while impressions moved far less (2812 against 2925, -3.9%). The search CTR went from 4.2% to 2.6%, and the average position from 9.7 to 12.1, worse by 2.4 positions. The program page lost 13 clicks and the home page 22, both with a worse position. The founder rewrote the program page title and meta description on 2026-10-01, and the position started to slip in the following days. That is an order in time, not a proof: experiment E-20261014-1 restores the old title to test it.

**Activation inside the noise.** Apply clicks went from 53 to 36 and the visitor-to-apply rate from 9.9% to 6.8%. Against the 4-week mean the rate is down 1.9 points with a noise band of 2.7 points, so the week does not show a change. Newsletter signups were 13, against 11.2 on average: too few events for a rate.

**Revenue and retention as counts.** 3 payments for 420.00 EUR, against 2 payments for 240.00 EUR the week before; 3 of them from returning customers. With this volume no change reads as a trend.

## Search Console

The decline uses the same definition as seo-audit: clicks down at least 20% on a prior period with at least 10 clicks, cause position when the average position worsened by 2 or more.

Totals 2026-W41 vs 2026-W40: 72 clicks vs 124 (-41.9%), position 12.1 vs 9.7. Decline, cause: position.

| Query | Clicks | Prior | Change | Position | Prior | Cause |
|---|---:|---:|---:|---:|---:|---|
| `swanbase` | 30 | 50 | -20 | 3.8 | 1.7 | position |
| `pre-seed accelerator` | 8 | 16 | -8 | 10.9 | 8.8 | position |

| Page | Clicks | Prior | Change | Position | Prior | Cause |
|---|---:|---:|---:|---:|---:|---|
| `https://swanbase.example/` | 32 | 54 | -22 | 11 | 8.8 | position |
| `https://swanbase.example/program/` | 31 | 44 | -13 | 10.8 | 7.8 | position |
| `https://swanbase.example/blog/pre-seed-checklist/` | 4 | 13 | -9 | 13.6 | 11.4 | position |

## Correlations

Only the pairs fixed in advance are tested, on 42 days with the day-of-week pattern removed. None of them is a cause.

| Id | A | B | Lag (days) | Days | r | Read |
|---|---|---|---:|---:|---:|---|
| C1 | social.instagram.impressions | umami.visitors | 0 | 42 | 0.22 | weak |
| C2 | social.instagram.impressions | umami.visitors | 1 | 41 | -0.05 | weak |
| C3 | social.linkedin.impressions | umami.visitors | 0 | 42 | 0.06 | weak |
| C4 | social.linkedin.impressions | umami.visitors | 1 | 41 | -0.34 | weak |
| C5 | gsc.clicks | umami.visitors | 0 | 42 | 0.51 | correlated |
| C6 | gsc.clicks | umami.visitors | 1 | 41 | 0.43 | weak |
| C7 | umami.visitors | umami.event.apply_click | 0 | 42 | 0.03 | weak |
| C8 | umami.visitors | umami.event.apply_click | 1 | 41 | -0.13 | weak |
| C9 | umami.visitors | umami.event.newsletter_signup | 0 | 42 | -0.13 | weak |
| C10 | umami.visitors | umami.event.newsletter_signup | 1 | 41 | -0.06 | weak |
| C11 | umami.visitors | umami.event.invite_link_copied | 0 | 42 | -0.1 | weak |
| C12 | umami.visitors | umami.event.invite_link_copied | 1 | 41 | 0.02 | weak |

- C5: search clicks and visitors have a correlation of r = 0.51 on the same day, the only pair above the 0.5 threshold. Search is one of the ways people reach the site, so this correlation is expected.
- C3 and C4: LinkedIn impressions and visitors show a weak correlation (r = 0.06 on the same day, r = -0.34 one day later). In this window, the days with the most LinkedIn reach were not the days with the most visits.
- C7 to C12: conversions and visitors show weak correlations; with fewer than 30 events a week for most of them, a weak correlation here says little either way.

## Last run's experiments

| Id | Metric | Threshold | Observed | Verdict |
|---|---|---:|---:|---|
| E-20260930-1 | `social.linkedin.impressions` | >= 9000 per week | 14365 | met |
| E-20260930-2 | `umami.event.newsletter_signup` | >= 15 per week | 13 | running |
| E-20260930-3 | `new:umami.event.referral_signup` | >= 3 in total | n/a | not measurable |

- E-20260930-1, one carousel a week: met. LinkedIn impressions reached 14365 against a threshold of 9000. A met threshold goes with the change in time; it does not prove its effect, and site visits did not follow (see above).
- E-20260930-2, newsletter box under every article: running until 2026-10-18. 13 signups in its first week, against a threshold of 15 per week.
- E-20260930-3, invite link in the confirmation email: not measurable. The referral_signup event is not tracked yet, so the test has no data. E-20261014-3 starts with the tracking.

## Next sprint: three experiments

Handoff: `experiments-20261014.json`, for the sprint starting 2026-10-19. No cash spend; 7 hours in total.

#### E-20261014-1: Restore the previous program page title and meta description (acquisition)

- Hypothesis: We believe that restoring the program page title and meta description used before the rewrite will bring the average search position back toward its 4-week mean because the position started to worsen in the days after the rewrite while search impressions moved far less than clicks.
- Change: Put back the previous title and meta description of the program page, request indexing in Search Console, and change nothing else on the page until the experiment ends. Owner: seo-audit, channel: search.
- Metric: Average search position, baseline 12.1 (report week).
- Success: <= 10.5 average position per week, over 14 days from 2026-10-19.
- Readout: not assessed for a position metric.
- Cost: 0 EUR cash, 1 hour.

#### E-20261014-2: Program link on the last slide and in the first comment of each carousel (acquisition)

- Hypothesis: We believe that a program page link on the last slide and in the first comment of each carousel will turn more LinkedIn readers into site visitors because LinkedIn impressions more than doubled this week while site visitors stayed inside their noise band.
- Change: carousel-builder adds a closing slide that names the program page; the founder posts the tagged link as the first comment right after publishing, on every carousel of the sprint. Owner: carousel-builder, channel: linkedin.
- Metric: Visitors (umami), baseline 559.5 (4-week mean).
- Success: >= 640 visitors per week, over 14 days from 2026-10-19.
- Readout: the target is outside the noise band of the weekly mean over 14 days.
- Cost: 0 EUR cash, 3 hours.

#### E-20261014-3: Track invite signups, then rerun the invite link test (referral)

- Hypothesis: We believe that an invite link in the application confirmation email will bring referred signups because visitors already copy the invite link today without any prompt.
- Change: Fire a referral_signup event in Umami when a signup arrives through an invite link, check it on a test signup, then keep the invite link in the confirmation email until the experiment ends. Owner: founder, channel: email.
- Metric: Signups through an invite link, baseline none yet (metric to instrument).
- Success: >= 3 signups in total, over 14 days from 2026-10-19.
- Readout: metric to instrument first: no baseline to read against.
- Cost: 0 EUR cash, 3 hours.

## Methodology

- Sources: Umami by API (replayed fixture), Search Console by API (replayed fixture, weekly query and page rows), LinkedIn daily export and Instagram post export by CSV, revenue by payments CSV. Plausible and GA4: not configured.
- Numbers: `compute_pulse.py` with the shipped `pulse-rules.json` (a percentage needs at least 30 events, flat zone of z = 2, correlation threshold 0.5 on at least 28 days). The model wrote no figure.
- Checks: report numbers 0 BLOCK (`check_report.py`), experiments 0 BLOCK and 1 WARN, the tracking to add before E-20261014-3 (`check_experiments.py`), writing gate 0 BLOCK, `pulse.json` and the handoff valid against their schemas.
- Fresh-eyes review: not run (example run).

## Limitations

- Weekly visitors are daily unique visitors summed: one person visiting on two days counts twice.
- 14 metrics are under 30 events this week: counts only, no percentage.
- Plausible and GA4 are missing; the web numbers rest on Umami alone.
- Correlations come from 6 weeks of one site: they show what moved together, never what caused what.
- Search Console data arrives 2 to 3 days late; this run on a Wednesday has the full week.
