# FR startup channels

Curated list of French-speaking early-stage channels, last reviewed 2026-04 as a whole, not entry by entry: no entry carries its own verification date yet, and some have died since (see the Archive section). Use when `language: fr` or `geography: FR` is set in the agent config.

This list is **inspiration, not a copy-paste shortlist**. Every channel must still pass the six activity gates from `community-activity-signals.md` before entering the scoring shortlist. A channel listed here can have died between curation and the run.

---

## Online communities (FR)

| Channel | Platform | Vibe | Access | Notes |
|---------|----------|------|--------|-------|
| French Startups Slack | Slack (gated) | Founder-heavy | Application via website | Read the posting rules before any message; help-first only. |
| Indie Hackers France | Slack / Telegram | Active, builder-focused | Open, intro required | French branch of Indie Hackers global. Ship-and-share culture. |
| Les Licorniens | Slack | Deep tech / SaaS | Application | B2B founder focus; check activity with the gates. |
| Xpedition Guilds | Slack | Active, multi-vertical | Application | Cross-functional founder + operator mix. |
| Startup Lyon | Discord | Local-flavored, regional | Open | Useful for FR regional founders, narrower than Paris-centric channels. |
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

For event recurrence, always check Lu.ma + Meetup + Eventbrite directly. The list above can be stale at any time.

---

## Newsletters and Substacks (FR founder audience)

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

- Generic LinkedIn groups: many are link-drop feeds with no replies and fail Gate 5 of `community-activity-signals.md`. Check before listing one.
- Paid masterminds: out of scope per zero-paid-SaaS rule.
- Personal-brand Slacks tied to a single influencer: too volatile, cannot be evaluated as a channel.
- Reddit-FR subs such as r/france_business exist but are small. List them as marginal-only after Gate 1 pass. (r/Entrepreneur is English-speaking and global: it belongs to the EN-default pool, not to this list.)

---

## How to use this list inside the agent

1. Treat it as a list of places to look for signals, not a shortlist. A channel enters the map when people with dated signals spoke there (`channels.json`).
2. Most entries are closed groups (Slack, Discord, Telegram): nothing in them is readable from outside. When one matters, ask the founder to join and drop screenshots of the last week (`skills/gating-active-communities/SKILL.md`); signals seen there go to `manual-signals.csv` with `date_source: founder`.
3. Discovery that needs no list, for FR and neighbouring EU countries:
   - Luma city pages (`sources.luma.places`: `paris`, `lyon`, `berlin`, `amsterdam`, `barcelona`...): hosts of events on the topic are `event` signals.
   - The French company registry (`sources.registry_fr`): companies created in the last 60 days, by activity code and department; a seed until the director's own posts are found.
   - Public Notion and folk lists that communities publish ([`references/public-list-endpoints.md`](../references/public-list-endpoints.md)): seeds.
   - Web search on public LinkedIn posts in French (`site:linkedin.com/posts "je cherche" "<problem word in French>"`).
4. Gate each community where people were found, then score with `scoring-channels`. How many FR channels make the cut depends only on the gates and the scores, never on a quota.

---

## Maintenance

This list rots. Re-validate every 90 days:
- Are listed Slacks still alive? Run gates on each.
- Are events still recurring? Check Lu.ma + organizer site.
- Are newsletters still publishing? Check most recent issue date.

A channel that fails re-validation is moved to the Archive section below, not deleted, so future runs know it was once active.

---

## Archive

| Channel | Date checked | Why archived |
|---------|--------------|--------------|
| French Tech Discord index (techcommunities.fr) | 2026-10-10 | Site did not respond. |
| Frenchpresso (frenchpresso.fr, frenchpresso.com) | 2026-10-10 | Both domains parked; no newsletter found. |

---

## Source

Compiled from public FR startup directories (FrenchWeb, Maddyness, Bpifrance Hub) and founder word of mouth, as of 2026-04. No entry has been scored on a recorded run: treat each one as a lead to verify with the gates, not as a validated channel.
