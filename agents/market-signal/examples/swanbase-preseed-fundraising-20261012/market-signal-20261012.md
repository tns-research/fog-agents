# Market signal: pre-seed fundraising for first-time founders

Project `swanbase`, built 2026-10-12, window 2026-07-14 to 2026-10-12 (91 days), language en, geography global. Valid until 2027-01-10.

Every number below comes from `stats.json` (scripts/compute_signals.py). Every quote was found again, word for word, in the stored corpus by scripts/verify_quotes.py.

## Summary

Fictional example: every post, author, id and URL in this corpus is invented, and any resemblance to real people, posts or companies is coincidental. First-time founders in this window talk about getting a meeting more than about any other part of the raise. Warm introductions work as the gate: practitioners tell founders to skip cold email, and founders without a network say they cannot get meetings even with paying customers. The second escalated pain is the proof bar, where practitioners contradict each other on how much traction a pre-seed round needs. Accelerators appear both as a way in front of investors and as programmes founders doubt.

Escalated pains: `pain_traction_bar` (10 authors, 3 communities); `pain_investor_access` (9 authors, 2 communities). Rule: at least 5 distinct authors across at least 2 communities, speakers counted: user, practitioner.

## Sources and health

65 records collected, 30 relevant after reading, 26 counted voices, 21 quotes verified.

| Collector job | Source | Status | Records | Capped | Note |
|---|---|---|---|---|---|
| `reddit-startups-preseed` | reddit | ok | 12 | yes |  |
| `reddit-startups-warm-intro` | reddit | ok | 12 | yes |  |
| `reddit-ycombinator-raise` | reddit | ok | 10 | yes |  |
| `reddit-venturecapital-preseed` | reddit | ok | 6 | no |  |
| `hn-warm-intro` | hn | ok | 9 | no |  |
| `hn-pre-seed` | hn | ok | 8 | yes |  |
| `se-money-investors` | se | ok | 3 | no |  |
| `discourse-nocode-funding` | discourse | ok | 6 | yes |  |
| `appstore-tablesplit-us` | appstore | empty | 0 | no | the iTunes review feed answered no entries; it does this intermittently, retry later or with another --country |

Records by source: discourse 6 (9 %), hn 17 (26 %), reddit 39 (60 %), se 3 (5 %). Counted voices by source: hn 3 (12 %), reddit 23 (88 %).

Sentiment of counted voices: mixed 3 (12 %), negative 11 (42 %), neutral 8 (31 %), positive 4 (15 %), out of 26. Labels are the model's reading of each record; the split is a count of those labels.

## Pains

| Pain | Escalated | Authors | Communities | Voices | By source | First seen | Last seen | Trend | Volume |
|---|---|---|---|---|---|---|---|---|---|
| `pain_traction_bar`: Not knowing which proof is enough for a pre-seed yes, while practitioners disagree on the bar | yes | 10 | 3 | 10 | reddit 10 | 2026-09-19 | 2026-10-07 | unknown | lower_bound |
| `pain_investor_access`: Getting in front of investors without a network: warm introductions act as the gate | yes | 9 | 2 | 9 | reddit 9 | 2026-07-24 | 2026-10-10 | unknown | lower_bound |
| `pain_pitch_story`: Turning an early company into one story an investor can repeat | no | 4 | 1 | 4 | reddit 4 | 2026-09-26 | 2026-10-06 | unknown | lower_bound |
| `pain_vc_misalignment`: Pre-seed investors bet on a few winners and expect the rest to fail, which founders read as misalignment | no | 4 | 3 | 4 | reddit 4 | 2026-07-16 | 2026-10-10 | unknown | lower_bound |
| `pain_intro_black_box`: Introductions disappear: the connector never learns what happened | no | 3 | 1 | 3 | hn 3 | 2026-07-28 | 2026-07-30 | falling | complete |

Trend compares the two halves of the window and reads `unknown` when a collector feeding the pain hit its cap: collectors keep the newest records, so the halves would be biased. Volume `lower_bound` means more records exist than were collected.

Weak signals (under the threshold, kept for transparency, never as findings): `pain_pitch_story` (4 authors, 1 community); `pain_vc_misalignment` (4 authors, 3 communities); `pain_intro_black_box` (3 authors, 1 community).

Rejected pains:

- Warm introductions to find first clients, vendors or a cofounder: Same words, different market: these threads are about sales and hiring, not the raise. Labelled not relevant.
- Fundraising mechanics for novices: One Stack Exchange question in the previous run, none in this one.

## Quotes

### Not knowing which proof is enough for a pre-seed yes, while practitioners disagree on the bar

> Honest advice: you aren’t ready for funding. Not even pre-seed.

`q_not_ready`, r/venturecapital, 2026-09-19, practitioner, 63 characters: [permalink](https://www.reddit.com/r/venturecapital/comments/fictivet08/raising_pre_seed_for_a_music_app/fictive28/)

> The round that comes before is the FFF round (friends, family and fools)

`q_fff`, r/venturecapital, 2026-09-19, practitioner, 72 characters: [permalink](https://www.reddit.com/r/venturecapital/comments/fictivet08/raising_pre_seed_for_a_music_app/fictive28/)

> Raising a pre-seed at $500k ARR is still way above market I think

`q_above_market`, r/startups, 2026-10-07, practitioner, 65 characters: [permalink](https://www.reddit.com/r/startups/comments/fictivet28/first_time_founder_started_raising_what_now/fictive58/)

> Even with signed LOIs from big companies it’s hard to raise.

`q_loi`, r/ycombinator, 2026-10-05, practitioner, 60 characters: [permalink](https://www.reddit.com/r/ycombinator/comments/fictivet25/is_it_worth_eight_years_to_launch_a_hardware_product/fictive54/)

> Traction doesn’t have to mean revenue, but revenue is king.

`q_revenue_king`, r/startups, 2026-10-06, practitioner, 59 characters: [permalink](https://www.reddit.com/r/startups/comments/fictivet28/first_time_founder_started_raising_what_now/fictive56/)

### Getting in front of investors without a network: warm introductions act as the gate

> My startup has a working product with paying customers and I can't even get meetings with VCs.

`q_no_meetings`, r/startups, 2026-10-02, user, 94 characters: [permalink](https://www.reddit.com/r/startups/comments/fictivet22/anyone_else_feel_the_raise_is_about_sparkle/fictive48/)

> You need a hook to get through the door with VCs, and usually that hook is some "sparkle".

`q_sparkle`, r/startups, 2026-10-02, user, 90 characters: [permalink](https://www.reddit.com/r/startups/comments/fictivet22/anyone_else_feel_the_raise_is_about_sparkle/fictive48/)

> I'm not rich, and neither is my family. I have zero connections to VCs or to big money.

`q_zero_connections`, r/startups, 2026-09-27, user, 87 characters: [permalink](https://www.reddit.com/r/startups/comments/fictivet14/moving_forward_without_investors_or_a_network/fictive37/)

> Warm intros only work if the mutual has already seen real traction.

`q_mutual_traction`, r/startups, 2026-09-28, practitioner, 67 characters: [permalink](https://www.reddit.com/r/startups/comments/fictivet13/advice_on_warm_intros_to_pre_seed_investors/fictive39/)

> A pedigree background buys you warm intros, cheaper trust and a safety net

`q_pedigree`, r/startups, 2026-09-29, practitioner, 74 characters: [permalink](https://www.reddit.com/r/startups/comments/fictivet19/does_founder_pedigree_matter_for_a_first_round/fictive40/)

> Skip the cold emails.

`q_skip_cold`, r/startups, 2026-10-01, practitioner, 21 characters: [permalink](https://www.reddit.com/r/startups/comments/fictivet21/tips_to_reach_investors_if_you_are_outside_the_hubs/fictive46/)

> If anyone here likes the project and happens to know a pre-seed investor who would be a good fit, a warm intro would mean a lot.

`q_ask_intro`, r/startups, 2026-09-24, user, 128 characters: [permalink](https://www.reddit.com/r/startups/comments/fictivet13/advice_on_warm_intros_to_pre_seed_investors/fictive35/)

> Warm intros are overrated IMO, and not required.

`q_warm_overrated`, r/venturecapital, 2026-10-10, practitioner, 48 characters: [permalink](https://www.reddit.com/r/venturecapital/comments/fictivet31/how_do_i_get_in_front_of_top_funds/fictive62/)

### Turning an early company into one story an investor can repeat

> pre-seed? a one pager is plenty.

`q_one_pager`, r/startups, 2026-09-30, practitioner, 32 characters: [permalink](https://www.reddit.com/r/startups/comments/fictivet17/how_should_a_pre_seed_deck_open/fictive43/)

> Begin with the one sentence an investor can repeat to a partner: who is hurting, what you do, and the strongest single proof you have today

`q_one_sentence`, r/startups, 2026-09-30, practitioner, 139 characters: [permalink](https://www.reddit.com/r/startups/comments/fictivet17/how_should_a_pre_seed_deck_open/fictive44/)

> At pre-seed, investors buy one wedge, not a group of companies.

`q_one_wedge`, r/startups, 2026-09-26, practitioner, 63 characters: [permalink](https://www.reddit.com/r/startups/comments/fictivet15/my_deck_tries_to_cover_three_markets/fictive36/)

### Pre-seed investors bet on a few winners and expect the rest to fail, which founders read as misalignment

> For an investor, pre-seed is a roulette table: they know most of these startups will fail.

`q_roulette`, r/startups, 2026-09-24, practitioner, 90 characters: [permalink](https://www.reddit.com/r/startups/comments/fictivet09/what_actually_gets_a_b2b_tool_funded/fictive34/)

> VCs are not really on your side as a founder.

`q_not_aligned`, r/venturecapital, 2026-07-16, user, 45 characters: [permalink](https://www.reddit.com/r/venturecapital/comments/fictivet04/the_dark_side_of_venture_money/fictive25/)

### Introductions disappear: the connector never learns what happened

> I make quite a few intros, and I almost never hear what happened unless I ask, awkwardly, weeks later.

`q_intro_never`, Hacker News, 2026-07-30, user, 102 characters: [permalink](https://news.ycombinator.com/item?id=90026933)

### Not tied to a pain

> You're WAY over indexing on Hatchery Twelve.

`q_overindex`, r/startups, 2026-09-27, user, 44 characters: [permalink](https://www.reddit.com/r/startups/comments/fictivet14/moving_forward_without_investors_or_a_network/fictive37/)

> I think Cohort Zero is a bad program, especially the way they run their regional cohorts.

`q_program_bad`, r/ycombinator, 2026-09-30, practitioner, 89 characters: [permalink](https://www.reddit.com/r/ycombinator/comments/fictivet11/winter_batch_megathread/fictive45/)

## Hooks, objections, angles

> I can't even get meetings with VCs

`hook_no_meetings`, verbatim, 34 characters, cites q_no_meetings

> Warm intros only work if the mutual has already seen real traction.

`hook_mutual_traction`, verbatim, 67 characters, cites q_mutual_traction

> Which proof gets a first-time founder a first pre-seed meeting?

`hook_which_proof`, analyst line, goes through the claims gate, 63 characters, cites q_not_ready, q_above_market, q_loi

> you aren't ready for funding. Not even pre-seed.

`obj_not_ready`, objection (anxiety), cites q_not_ready

> Warm intros are overrated IMO, and not required.

`obj_warm_overrated`, objection (habit), cites q_warm_overrated

> I think Cohort Zero is a bad program

`obj_program_doubt`, objection (anxiety), cites q_program_bad

> You're WAY over indexing on Hatchery Twelve.

`obj_overindex`, objection (habit), cites q_overindex

| Angle | Pain | Force | Awareness | Funnel | Headline quote | Support | Contrast | Formats |
|---|---|---|---|---|---|---|---|---|
| `angle_access_gate` | `pain_investor_access` | push | problem_aware | tofu | `q_no_meetings` (94 characters) | q_zero_connections, q_pedigree | cold email to a fund's inbox | carousel, static_ad, cold_outreach |
| `angle_proof_bar` | `pain_traction_bar` | anxiety | problem_aware | mofu | `q_loi` (60 characters) | q_above_market, q_revenue_king | waiting for more traction before talking to anyone | carousel, landing_page |
| `angle_mutual_traction` | `pain_investor_access` | pull | solution_aware | bofu | `q_mutual_traction` (67 characters) | q_skip_cold | asking weak ties for introductions | cold_outreach, static_ad |

- `angle_access_gate`: The most repeated pain, in founders' own words, and it names the moment that hurts: no meeting.
- `angle_proof_bar`: Practitioners contradict each other on the bar; a sourced answer is useful content before any offer.
- `angle_mutual_traction`: Founders who already know intros matter want the condition that makes an intro work.

## Persona and forces

**First-time founder raising a first round without investor connections** (primary). Pre-seed, first company, posting in r/startups and r/venturecapital, often with early revenue or letters of intent.

- Push: `q_no_meetings`, `q_zero_connections`
- Pull: `q_mutual_traction`
- Anxiety: `q_not_ready`, `q_roulette`
- Habit: absent in this corpus
- Not for: Founders with strong traction who reach funds directly. They get meetings without introductions; the access pain is not theirs. (q_warm_overrated)

Force labels across counted voices: anxiety 9, habit 1, pull 7, push 8.

## Existing solutions

- Hatchery Twelve (direct, mixed): 1 record by 1 author; quotes q_overindex
- Cohort Zero (direct, negative): 1 record by 1 author; quotes q_program_bad
- friends and family round (status_quo, mixed): 1 record by 1 author; quotes q_fff
- cold email (status_quo, mixed): 1 record by 1 author; quotes q_skip_cold, q_warm_overrated

## Language bank

No phrase reached the threshold (3 records by 3 authors among counted voices, query words excluded).

## Changes since the last run

Previous window 2026-04-15 to 2026-07-13. Distinct authors, then per 30 days.

- `pain_vc_misalignment`: new (lower bound), 0 (0.0) to 4 (1.3)
- `pain_intro_black_box`: new, 0 (0.0) to 3 (1.0)
- `pain_traction_bar`: rising (lower bound), 3 (1.0) to 10 (3.3), newly escalated
- `pain_founder_salary`: disappeared (lower bound), 3 (1.0) to 0 (0.0)
- `pain_investor_access`: stable (lower bound), 7 (2.3) to 9 (3.0)
- `pain_pitch_story`: stable (lower bound), 2 (0.7) to 4 (1.3)
- Collector `reddit-ycombinator-raise`: quota to ok
- Alternatives named for the first time: Cohort Zero, Deckpeek, Hatchery Twelve, SAFE, cold email, friends and family round

## Recommendations

1. Test founder-facing copy that leads with getting the first investor meeting, in the founders' words, against copy that leads with the programme content. False if: The access-led variant converts no better on the same traffic, or the next watch run shows the access pain falling. Quotes: q_no_meetings, q_zero_connections.
2. Publish a sourced piece on what proof pre-seed investors ask for, since practitioners in the corpus contradict each other on the bar. False if: Readers' replies say the bar was already clear to them, or the piece draws less engagement than the account's usual posts. Quotes: q_loi, q_above_market, q_revenue_king.
3. Answer the programme doubts on the application page with what the programme can show, before using introductions as a selling point. False if: Applicants never raise programme quality or introductions in their questions. Quotes: q_program_bad, q_overindex, q_warm_overrated.

## Methodology

- Collection: one collector per source (scripts/collect.py, parallel lanes per source), window 2026-07-14 to 2026-10-12, corpus `runs/20261012/corpus.jsonl` (65 records, sha256 `7df688c4669e`).
- Coding: the model read every record and wrote one label per record (relevance, speaker, pains, sentiment, forces, awareness, alternatives named).
- Counting: scripts/compute_signals.py; a pain escalates at 5 distinct authors and 2 communities; one author posting several times counts once.
- Quotes: cited by record id and passage, verified by scripts/verify_quotes.py: 21 of 21 pass, 0 with a warning.
- Sidecar: built and validated by scripts/build_handoff.py and scripts/validate_sidecar.py against assets/market-signal.schema.json.

## Limitations

- Fictional example: the corpus, the recorded API answers, the authors, ids and URLs were written to show the agent's output and describe no real post, person or company.
- English sources only; no French community was collected in this run.
- Reddit comes from the Arctic Shift archive: deleted comments are absent and the most recent days may be missing.
- The App Store feed returned no review for Tablesplit in this run, so there is no review mining.
- Hacker News search for the exact phrase pre-seed returns mostly hiring threads; Stack Exchange has no active startup site.
- Collector `appstore-tablesplit-us` ended empty: the iTunes review feed answered no entries; it does this intermittently, retry later or with another --country.
- Capped collectors (newest records kept, volumes are lower bounds): discourse-nocode-funding, hn-pre-seed, reddit-startups-preseed, reddit-startups-warm-intro, reddit-ycombinator-raise.
- Public discourse over-represents people who complain in public; silence in the corpus is not absence of the pain.

*Generated by `market-signal` (scripts/build_handoff.py) from `runs/20261012/corpus.jsonl`. Quotes are public strangers' words about a problem, never testimonials.*
