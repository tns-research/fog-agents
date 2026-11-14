# First Users Hunter: swanbase-example (preview)

**Date:** 2026-10-12 | **Idea:** a Paris accelerator that works with first-time founders all year, from the first prototype to the first round | **Target user:** pre-seed founders, Paris or Europe | **Geography:** FR

All people below are fictional (example data).

## Summary

Four people asked in public, in the last three weeks, for what swanbase does or host the room where those founders meet, and each posts now. Three of the four spoke on Ask HN and LinkedIn; the strongest signal is an Ask HN request from a solo founder in Paris (2026-10-03). This week: post the two HN replies and the LinkedIn comment, then register for the 2026-10-20 breakfast.

## People

| # | Person | Signal (type, date) | Where | Verbatim excerpt | Active (weighted, last) | Score | Why they fit | Touch 1 |
|---|--------|---------------------|-------|------------------|-------------------------|------:|--------------|---------|
| p001 | qforge_fictive (HN) | [ask, 2026-10-03](https://news.ycombinator.com/item?id=99000101) | Ask HN | "Any advice on where pre-seed founders in Europe actually find their first real users? I am based in Paris and starting to feel stuck." | 4 in 45 d (HN and LinkedIn), 2026-10-08 | 27 | solo pre-seed founder, MVP live, Paris | reply in the HN thread |
| p002 | Camille Roux | [ask, 2026-09-28](https://www.linkedin.com/posts/camille-roux-fictive_preseed-paris-activity-7510249942548603456-AbCd) | LinkedIn | "Can anyone recommend a program in Paris that works with founders before the round, not after?" | 3 in 45 d, 2026-10-05 | 23 | two co-founders in Paris raising a pre-seed round | comment on the post |
| p003 | mtrace_fictive (HN) | [ask, 2026-09-20](https://news.ycombinator.com/item?id=99000110) | Ask HN | "I am now looking for a cofounder with a sales background but every intro feels like a job interview." | 3 in 30 d, 2026-10-01 | 23 | solo pre-seed founder with paying users | reply in the HN thread |
| p004 | Ines Marchal | [event, 2026-10-20](https://luma.com/solo-founders-breakfast-fictive) | Paris Builders Mornings (Luma) | "Solo founders breakfast: finding your first users" | 3 in 45 d (LinkedIn and the event), 2026-10-12 | 19 | hosts the room where solo founders in Paris meet | LinkedIn connection note |

The LinkedIn date of p002 is decoded from the post id (`activity-7510249942548603456` gives 2026-09-28 08:12 UTC). `verify_people.py`: 4 people, 0 errors.

Touches: `first-touches-20261012.md` (rebuilt by `export_handoff.py`). Example, p001 touch 1: "Your four users came through friends of friends, so one question first: do they share a specialty or a city? If they do, the next ten probably read the same newsletter or belong to the same association, and that is where you can ask in public. Happy to think through the clinic angle here if you share more."

## Dropped people

| Person | Stage | Reason |
|--------|-------|--------|
| lumen-sketch-fictive (GitHub) | drafting | asks for a waitlist tool for beta testers; an accelerator does not answer that need |
| bastien-morel-fictive | candidates | stale: ask of 2026-06-10, 124 days old, max 45 |
| samuel-petit-fictive | candidates | listed in a public directory, no signal of their own |
| ghost-builder-fictive (GitHub) | activity | `dead_handle`: the account no longer exists |
| nledger_fictive (HN) | activity | `not_proven`: 1 weighted post in the window |
| nadia_ships_fictive (X) | activity | `not_proven`: 1 post and 2 replies, 1.5 weighted |
| Hugo Lemaire (registry) | activity | `not_proven`: company created 2026-09-22, no public handle found |
| leo_builds_fictive (X) | collection | the date in the CSV disagreed with the post id: row refused |

## Channel map (from the people)

| Community | Network | People with signals | Strong types | Gate decision |
|-----------|---------|--------------------:|-------------:|---------------|
| Ask HN | hn | 2 | 2 | not run in this offline example (public archive: Algolia `tags=ask_hn`) |
| LinkedIn posts | linkedin | 1 | 1 | n/a (a network, not a community) |
| Paris Builders Mornings | luma | 1 | 0 | n/a (an event series) |

With one community holding two people, the experiment plan of a real run would start there: three substantive replies in Ask HN threads over 14 days, primary metric replies per touched person counted from `ledger.csv`.

## Claims ledger

| Claim (as written) | Used in | Source |
|--------------------|---------|--------|
| "a Paris accelerator that works with first-time founders all year, from the first prototype to the first round" | p002 touch 1 | project-context `what_it_is` (here `config.json` `idea`) |
| "a Paris accelerator for first-time founders" | p001 touch 2, p004 touch 1 | same |

**Dropped:** none.

## Source health

| Source | Signals | Activity checks | Status |
|--------|--------:|----------------:|--------|
| hn | 3 | 3 handles | ok (fixture) |
| github | 2 | 2 handles, 1 not found | ok (fixture) |
| reddit | 0 | 0 | skipped: disabled until REDDIT_CLIENT_ID is set |
| luma | 1 | n/a | ok (fixture) |
| notion | 2 seeds | n/a | ok (fixture) |
| folk | 0 | n/a | skipped: disabled |
| registry_fr | 1 seed | n/a | ok (fixture) |
| manual | 3 | 4 handles | ok; 1 row refused (date against post id) |

## Handoff

`prospects-20261012.csv` (4 rows) and `handoff-20261012/` (4 dossiers, 4 cached pages). cold-outreach-builder's `verify_dossiers.py`: 4 ok, 4 facts verified.
