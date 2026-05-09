# FR startup channels

Curated list of French-speaking early-stage channels validated as of 2026-04. Use when `language: fr` or `geography: FR` is set in the agent config.

This list is **inspiration, not a copy-paste shortlist**. Every channel must still pass the six activity gates from `community-activity-signals.md` before entering the scoring shortlist. A channel listed here can have died between curation and the run.

---

## Online communities (FR)

| Channel | Platform | Vibe | Access | Notes |
|---------|----------|------|--------|-------|
| French Startups Slack | Slack (gated) | Active discussion, founder-heavy | Application via website | Stable since 2015. Strict no-pitch culture; help-first only. |
| Indie Hackers France | Slack / Telegram | Active, builder-focused | Open, intro required | French branch of Indie Hackers global. Ship-and-share culture. |
| Les Licorniens | Slack | Active, deep tech / SaaS | Application | Tier-1 community. High signal for B2B founders. |
| Xpedition Guilds | Slack | Active, multi-vertical | Application | Cross-functional founder + operator mix. |
| Startup Lyon | Discord | Local-flavored, regional | Open | Useful for FR regional founders, narrower than Paris-centric channels. |
| French Tech Discord (techcommunities.fr) | Discord index | Multi-server | Open per server | Index of regional French Tech Discords. |
| Bpifrance Hub | Web platform + events | Mixed activity | Founder portfolio access | Strong for funded startups; weaker for pre-seed. |
| Station F alumni Slack | Slack (alumni-only) | Active | Alumni-only | Strongest if founder is/was a Station F resident. |
| The Family alumni Slack | Slack (alumni-only) | Mixed | Alumni-only | Smaller than Station F but tight. |
| LiveMentor community | Discord / forum | Active for solo / freelance | Member or course alumni | Solopreneur and small-business angle. |

---

## Vertical / niche FR sources

| Source | Type | Use for |
|--------|------|---------|
| FrenchWeb | News + community | Discover trending topics in FR tech, identify discussion threads in comments. |
| Maddyness | News + events | Event lookup (parallel to Lu.ma for FR). |
| BFM Business / Tech newsletter | Newsletter | Signal of who's launching/raising; mention triggers for cold outreach. |
| Feeders.io / Welcome to the Jungle | Job board / company directory | Discover who works where (proxy for ICP mapping). |
| Le Forum (LinuxFr, etc.) | Vertical forum | For dev-tool / open-source founders. Niche but engaged. |

---

## IRL events (FR, recurring)

| Event | Frequency | Geography | Use for |
|-------|-----------|-----------|---------|
| VivaTech | Annual (June) | Paris | Visibility, density of founders, but enormous. Best for parallel dinners, not booth presence. |
| Salon Entreprendre | Annual | Various FR cities | Solopreneur and SME founder mix. |
| BFM Awards | Annual | Paris | High signal for funded founders. |
| Le Wagon Demo Day | Quarterly | Paris, Lyon, Bordeaux | Bootcamp graduates, often early founders. |
| Station F demo day | Periodic | Paris | Funded portfolio, harder to access without intro. |
| Bpifrance Inno Génération | Annual | Paris | Government-affiliated, large. |
| Lyon Startup Weekend | Annual | Lyon | Hands-on, builder energy. |
| Apéro Entrepreneurs (multiple cities) | Monthly | Paris, Lyon, Bordeaux, Marseille | Small, recurring, low-cost watering hole. |

For event recurrence, always check Lu.ma + Meetup + Eventbrite directly. The list above can be 6 months stale at any time.

---

## Newsletters and Substacks (FR founder audience)

- **Frenchpresso**, startup news digest. Reply rate to founder pitches via this audience is unusually high.
- **Maddyness Newsletter**, broad FR tech.
- **Geekflare FR / FrenchWeb Daily**, vertical depth.
- **Bpifrance Newsletter**, government/funding angle.

Sponsorship rates and subscriber counts move yearly; always check the current media kit before pitching.

---

## Regional and specialty Slacks

| Slack / Discord | Region / Theme | Notes |
|-----------------|----------------|-------|
| French Tech Bordeaux | Bordeaux | Active regional channel. |
| French Tech Toulouse | Toulouse | Aerospace / deep tech bias. |
| French Tech Marseille | Marseille | Smaller, growing. |
| Tech for Good France | Vertical | Impact / climate / social founders. |
| Femmes Entrepreneures | Vertical | Founder community for women, FR. |
| Indie Hackers Paris (in-person spinoff) | Paris meetup | Useful for IRL leg of channel mix. |

---

## What's NOT on this list

- Generic LinkedIn groups: the FR LinkedIn group ecosystem has degraded into self-promo since ~2022. Most fail Gate 5 of `community-activity-signals.md`.
- Paid masterminds: out of scope per zero-paid-SaaS rule.
- Personal-brand Slacks tied to a single influencer: too volatile, cannot be evaluated as a channel.
- Reddit-FR subs: r/Entrepreneur, r/france_business, exist but are very small (<5k active posters). List them as marginal-only after Gate 1 pass.

---

## How to use this list inside the agent

1. Treat as a candidate pool, not a shortlist.
2. Pass each candidate through `gating-active-communities` before scoring.
3. Score with `scoring-channels` using ICE.
4. The output channel list mixes EN-default channels with FR additions where `language: fr` or `geography: FR`. The FR additions are 30-50% of a French-targeted run.

---

## Maintenance

This list rots. Re-validate every 90 days:
- Are listed Slacks still alive? Run gates on each.
- Are events still recurring? Check Lu.ma + organizer site.
- Are newsletters still publishing? Check most recent issue date.

A channel that fails re-validation is moved to an "archive" section, not deleted, so future runs know it was once active.

---

## Source

Compiled from public FR startup directories (FrenchWeb, Maddyness, Bpifrance Hub), cross-referenced with founder-network word-of-mouth data (current as of 2026-04), and validated by ICE-scoring runs on three FR-targeted projects.
