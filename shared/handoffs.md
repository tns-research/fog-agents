# Handoffs between agents

Agents read each other's outputs through plain files in the founder's project. No agent calls another one. Every handoff is optional: **if the file exists, the consumer uses it and says so in the chat and in its report; if it does not, the consumer runs exactly as it does standalone.**

## Where artifacts live

Every agent writes into its own folder of the founder's project (see "Output location" in each `AGENT_<NAME>.md`):

```
<your-projects-root>/<project-slug>/
├── project-context/                 # shared business + brand context (read by every agent)
├── market-signal/
│   ├── market-signal-<YYYYMMDD>.md
│   ├── market-signal-<YYYYMMDD>.json      # handoff sidecar, schema_version 2.0 (schema below)
│   └── runs/<YYYYMMDD>/corpus.jsonl       # the stored corpus every quote comes from
├── first-users-hunter/
│   ├── first-users-<YYYYMMDD>.md
│   ├── people-<YYYYMMDD>.jsonl            # the verified people, one per line
│   ├── prospects-<YYYYMMDD>.csv           # handoff prospect list (schema below)
│   ├── handoff-<YYYYMMDD>/dossiers/, cache/  # one cold-outreach-builder dossier per person
│   ├── first-touches-<YYYYMMDD>.md
│   └── ledger.csv                         # people listed or approached, read by the next run
├── cold-outreach-builder/
├── static-ads-builder/
├── carousel-builder/
├── landing-page-analyzer/
├── seo-audit/
├── short-video-builder/
│   └── <label>-<YYYYMMDD>/export/<id>.mp4  # 9:16 shorts + qa.json
├── founder-content-writer/
│   └── <label>-<YYYYMMDD>/posts.json      # founder posts, content-publisher's post spec
├── content-publisher/
│   └── queue.json                         # written only by scripts/pubqueue.py
├── growth-pulse/
│   └── experiments-<YYYYMMDD>.json        # three AARRR experiments, seeds the next sprint
└── growth-sprint/
    └── <sprint id>/sprint.json, state.json
```

**Picking the file.** When several dated files exist, a consumer uses the one with the most recent `<YYYYMMDD>` in its name, tells the user which file it picked and its date, and flags in its report any file older than 90 days (market language and prospect lists go stale). It does not stop to ask.

**Reading defensively.** A consumer reads only the fields it needs, ignores unknown fields, and treats a missing field as absent. A file that does not parse is reported once and ignored.

## Who reads what

| Producer artifact | Consumer | What the consumer does with it |
|-------------------|----------|--------------------------------|
| `market-signal-<YYYYMMDD>.json` | `cold-outreach-builder` | Seeds the ICP language scan (pain phrases, objections, status quo) and the hook angles with real quotes and their URLs. |
| `market-signal-<YYYYMMDD>.json` | `static-ads-builder` | Feeds angles, headlines and objection-handling concepts with customers' own words. |
| `market-signal-<YYYYMMDD>.json` | `carousel-builder` | Feeds angle proposals and hooks; a quote slide may cite a quote with its public source. |
| `market-signal-<YYYYMMDD>.json` | `landing-page-analyzer` | Passed as `customer_quotes` to the copy rewrites so H1, CTA and value-prop alternatives reuse real wording. |
| `market-signal-<YYYYMMDD>.json` | `first-users-hunter` | Each quote whose author is a person becomes a candidate `complaint` signal, entered through the manual path with its permalink and date. |
| `market-signal-<YYYYMMDD>.json` | `founder-content-writer` | A post may rest on a verified quote: the passage is checked inside `text_verbatim`, the permalink and the date go in its report, the quote is never a testimonial. |
| `prospects-<YYYYMMDD>.csv` and `handoff-<YYYYMMDD>/` | `cold-outreach-builder` | Default `prospect_list` when the user gives none; the dossiers and cached pages of `handoff-<YYYYMMDD>/` are copied into its run folder, so the signal arrives as a dated, sourced fact. |
| `carousel-builder/<label>-<YYYYMMDD>/` (`captions.md`, `export/`) | `content-publisher` | `agents/content-publisher/scripts/import_carousel.py` drafts the post and its variants per network. |
| `founder-content-writer/<label>-<YYYYMMDD>/posts.json` | `content-publisher` | Taken as is by `pubqueue.py add`: every post is already checked against its limits, link rules and writing gate. A person approves each item there. |
| static ads, short videos, text posts | `content-publisher` | Entered by hand against `agents/content-publisher/assets/post-spec.schema.json`. |
| `experiments-<YYYYMMDD>.json` | `growth-sprint` | Default goal of the next sprint when the founder names none. |
| `experiments-<YYYYMMDD>.json` (previous run) | `growth-pulse` | The next pulse judges last run's experiments against the data. |
| `seo-audit/config.json` | `growth-pulse` | Its `gsc_bands.decline` override applies to the Search Console declines of the pulse. |
| every agent's outputs | `growth-sprint` | Read only to check a step on disk against the agent's schema (`agents/growth-sprint/assets/agents.json`). |

`founder-content-writer` also compares its openings with the texts of `content-publisher/queue.json` and with its own `project-context/memory/posts.jsonl`, read-only for the queue.

`seo-audit` writes refresh briefs (`briefs/<slug>.md`, one per existing URL to rewrite) that a writer, human or agent, picks up; it reads no other agent's file.

## Rules for reusing market-signal quotes

Quotes are the verbatim words of public strangers about a problem (cross-cutting convention C5 in `agents/_template-agent/AGENT_TEMPLATE.md`).

- Keep them verbatim, in their original language. Tag a translation `[translated]` and keep the original next to it.
- Carry the `permalink` and the `date` along wherever a quote is used, at least in the consumer's report.
- Use them as **language**: pain phrasing, objection wording, headline raw material.
- Never present one as a testimonial of the founder's product, never imply its author is a customer, never attach it to a company or a face. Product proof comes only from `positioning.proof` (see [`skills/enforcing-claims-policy/SKILL.md`](./skills/enforcing-claims-policy/SKILL.md)).
- `author_hash` is a pseudonym for counting distinct people. Never resolve it to a handle and never show it.
- A hook with `verbatim: false` is an analyst line built on quotes: the consumer treats it as its own copy and runs it through its claims gate.

## market-signal sidecar: `market-signal-<YYYYMMDD>.json`

Written by `agents/market-signal/scripts/build_handoff.py` at the end of a run, never by hand, next to the markdown report. UTF-8 JSON, `schema_version` `"2.0"`. Contract: [`../agents/market-signal/assets/market-signal.schema.json`](../agents/market-signal/assets/market-signal.schema.json) (JSON Schema, the stack's stdlib validator subset). Reference instance: [`../agents/market-signal/examples/swanbase-preseed-fundraising-20261012/market-signal-20261012.json`](../agents/market-signal/examples/swanbase-preseed-fundraising-20261012/market-signal-20261012.json).

What the producer guarantees, checked by script before the file is written:

- every `quotes[].text_verbatim` was found word for word in the record `record_id` of the stored corpus (`corpus.path`, relative to the sidecar, with its `sha256`), and its `date` is inside `window`;
- every count (`pains[].mention_count`, `distinct_authors`, `distinct_communities`, `stats`) was computed by `compute_signals.py` from the corpus and the labels, never typed;
- every id reference resolves and every id is unique; a hook marked `verbatim: true` and every objection text sit inside one of the quotes they cite;
- `valid_until` is after `date`;
- each hook's `char_count` is the length of its text, each angle's `headline_char_count` equals its headline quote's `char_count`, and its `pain_escalated` equals the pain's `escalated`;
- no bare number in the analyst's prose: pain summaries, angle `why`, hooks with `verbatim: false`, persona `name` and `context`, and recommendations without `source_urls` (years pass); `build_handoff.py` also checks the report summary and `limitations[]`.

`validate_sidecar.py` runs these checks (schema, ids, verbatim, window, angles, prose; then, by default, the corpus: its sha256 and every quote found again in its record with the same permalink and date; with `--stats`, every pain count against `stats.json`). Validate a file (consumer side, corpus not needed):

```bash
python3 agents/market-signal/scripts/validate_sidecar.py <project>/market-signal/market-signal-<YYYYMMDD>.json --no-corpus
```

### Fields

| Field | What it holds |
|-------|---------------|
| `schema_version`, `agent`, `project`, `date`, `market`, `language`, `geography` | identity of the run |
| `window` (`since`, `until`, `days`), `valid_until` | the collection window; consumers treat the file as fresh until `valid_until` (default date + 90 days) and flag it after |
| `corpus` (`path`, `sha256`, `records`) | the evidence: `runs/<YYYYMMDD>/corpus.jsonl` |
| `stats` | records collected and relevant, counted voices, quotes verified, shares by source, sentiment counts and shares, force counts, `escalation_rule`, `capped_jobs` |
| `source_health[]` | per collector job: `job_id`, `source`, `target`, `status` (`ok`, `empty`, `error`, `quota`), `records`, `capped`, `message` |
| `pains[]` | `pain_id`, `summary`, `kind` (`pain`, `meta_problem`, `desire`), `force`, `awareness_stage`, `existing_solution`, `escalated`, `mention_count`, `distinct_authors`, `distinct_communities`, `communities`, `by_source`, `source_shares`, `first_seen`, `last_seen`, `by_month`, `trend` (`rising`, `falling`, `flat`, `unknown`), `volume` (`complete`, `lower_bound`), `quote_ids` |
| `quotes[]` | `quote_id`, `record_id`, `text_verbatim`, `char_count`, `language`, `permalink`, `date`, `source`, `community`, `kind`, `author_hash`, `speaker` (`user`, `practitioner`, ...), `sentiment`, `pain_id`, `persona_id`, `usable_as` (`headline`, `support`, `hook`, `objection`, `outreach_opener`, `quote_slide`), `verified: true`, `warnings` |
| `hooks[]` | `hook_id`, `text`, `verbatim`, `char_count`, `pain_id`, `quote_ids` (at least one) |
| `objections[]` | `objection_id`, `text` (the buyer's words), `force` (`anxiety`, `habit`), `pain_id`, `quote_ids` |
| `angles[]` | `angle_id`, `pain_id`, `pain_escalated`, `force`, `awareness_stage`, `funnel_stage` (`tofu`, `mofu`, `bofu`), `headline_quote_id`, `headline_char_count`, `support_quote_ids`, `contrast` (status quo or named alternative), `formats` (`carousel`, `static_ad`, `cold_outreach`, `landing_page`), `why` |
| `existing_solutions[]` | `name`, `type` (`direct`, `indirect`, `status_quo`), `sentiment`, `mentions` (records and distinct authors, or null), `quote_ids` |
| `personas[]` | `persona_id`, `name` (descriptive title, never a made-up person), `context`, `primary`, `pain_ids`, `jtbd_forces` (`push`, `pull`, `anxiety`, `habit` as quote id lists; empty = absent in the corpus), `hook_ids`, `anti_personas` |
| `language_bank[]` | phrases said by several authors (`records`, `distinct_authors`, `pain_id`), query words excluded |
| `weak_signals[]`, `rejected_pains[]` | pains under the threshold; pains looked for and not kept, with the reason |
| `recommendations[]` | `text`, `falsified_if`, `quote_ids`, `source_urls` |
| `limitations[]`, `changes` | what the corpus cannot show; in watch mode the diff against the previous run (`changes.pains[]` with `status` new, rising, falling, disappeared, stable) |
| `marketing_copy` | derived from the angles, no new text: `candidate_headlines` (the `text_verbatim` of each angle's headline quote, with `source_quote_id`), `candidate_subheads` (the same for each support quote), `objection_responses` (always empty: objections live in `objections[]`) |
| `usage` | the reuse rule above, in one string |

### What each consumer reads first

| Consumer | Reads |
|----------|-------|
| `cold-outreach-builder` | escalated `pains`, `objections`, `hooks` with `verbatim: true`, quotes with `usable_as` `outreach_opener`, `angles` whose `formats` hold `cold_outreach` |
| `static-ads-builder` | `angles` with their `funnel_stage` (TOFU, MOFU, BOFU) and `headline_char_count` against the headline slot, `objections` for objection-handling concepts |
| `carousel-builder` | `angles` whose `formats` hold `carousel`, `hooks`, quotes with `usable_as` `quote_slide` (shown with their public source) |
| `landing-page-analyzer` | quotes with `usable_as` `headline` or `support` as `customer_quotes`, `objections`, `marketing_copy` |
| `first-users-hunter` | `quotes` with their `permalink` and `date`, entered as candidate `complaint` signals through its manual path |
| `founder-content-writer` | `quotes` with `verified: true` and their `permalink`, `date`, `speaker`; the `escalated` flag of their pain; `valid_until` |

Field rules for consumers:

- Lead with `pains[].escalated: true`. A pain or an angle on a weak pain (`pain_escalated: false`) is a hypothesis to test, not a finding.
- `volume: "lower_bound"` and `trend: "unknown"` mean a collector hit its cap: do not quote the count as the size of the market.
- A quote's `speaker` other than `user` or `practitioner` is not the persona's voice.
- Readers stay defensive: ignore unknown fields, treat a missing optional field as absent.

### A file that is not `schema_version` 2.0

`validate_sidecar.py` rejects any other `schema_version`: nothing says its quotes were checked against a stored corpus. A consumer does not reuse its numbers and quotes nothing from it as verified; at most it reads it as background language, with a warning in its report. `founder-content-writer` refuses it outright. Re-run market-signal for a verified handoff.

## founder-content-writer batch: `posts.json`

Written by `agents/founder-content-writer/scripts/build_batch.py`, never by hand, in `<project>/founder-content-writer/<label>-<YYYYMMDD>/`. Contract: content-publisher's own [`../agents/content-publisher/assets/post-spec.schema.json`](../agents/content-publisher/assets/post-spec.schema.json), `kind: text`, networks `linkedin` and `x`, `source.agent: founder-content-writer`, `source.path` pointing to the batch's `posts-spec.json`.

What the producer guarantees, checked by script before the file is written:

- every post cites at least one passage found word for word in the ingested raw material, whose sha256 has not changed, or inside a verified market-signal quote;
- every number and declared claim traces to `positioning.proof`, a sourced passage or the cited passages;
- content-publisher's own `variants.py lint` passes on this file, writing gate included;
- no opening repeats inside the batch, in `project-context/memory/posts.jsonl`, in `content-publisher/queue.json` or in the founder's past posts of the voice pack.

Consumer side:

```bash
python3 agents/content-publisher/scripts/pubqueue.py add <project>/founder-content-writer/<label>-<YYYYMMDD>/posts.json --queue <project>/content-publisher/queue.json --project <project>
```

Every item enters as `to_review`. The producer never queues, approves or publishes.

The producer's memory, `<project>/project-context/memory/posts.jsonl` (contract [`../agents/founder-content-writer/assets/past-post.schema.json`](../agents/founder-content-writer/assets/past-post.schema.json)), holds one line per post and network: the opening, the hook type, the angle, and for a rejected post the founder's words and the decision it produced.

## first-users-hunter prospect list: `prospects-<YYYYMMDD>.csv`

Written by `agents/first-users-hunter/scripts/export_handoff.py` from the verified `people-<YYYYMMDD>.jsonl`, never by hand; it refuses to export while `verify_people.py` reports an error. UTF-8, comma-separated, RFC 4180 quoting, header row first, one row per person. The prospect columns come first, in this order:

| Column | Required | Content |
|--------|----------|---------|
| `prospect_id` | yes | Stable id within the file, e.g. `p001` |
| `first_name` | yes | As shown on the public profile |
| `last_name` | no | As shown on the public profile |
| `role` | yes | Title or role pattern |
| `company` | no | Company or project name, empty for independents |
| `company_url` | no | Company site |
| `profile_url` | yes | Public page the person was found on (LinkedIn, IndieHackers, personal site, podcast page) |
| `email` | no | Only an address the person published for professional contact on a public page, with that page as `source_url`. Never guessed from a naming pattern. Usually empty. |
| `linkedin_url` | no | LinkedIn profile when known |
| `channel` | yes | Top channel this person maps to (e.g. `linkedin`, `reddit`, `email`, `event`) |
| `fit_rationale` | yes | One sentence: why they fit the target user |
| `source_url` | yes | Page that supports the fit rationale |
| `language` | no | `en`, `fr`, ... |
| `geography` | no | Country code or city |
| `found_on` | yes | `YYYY-MM-DD` |

Then the signal columns, in this order: `person_key`, `signal_type`, `signal_date`, `signal_url`, `signal_excerpt`, `signal_community`, `last_active_at`, `activity_status`, `active_networks` (semicolon-separated), `score`, `score_breakdown` (JSON), `first_touch_channel`, `first_touch_network`, `first_touch_draft`, `second_touch_channel`, `second_touch_draft`, `status`. A consumer that only knows the prospect columns ignores them.

Next to the CSV, the same script writes `handoff-<YYYYMMDD>/dossiers/<person_id>/prospect.json` (one cold-outreach-builder dossier per person, its signal as a dated fact with its URL and verbatim excerpt) and `handoff-<YYYYMMDD>/cache/` (the cached pages those facts point to, in cold-outreach-builder's cache layout). On the consumer side:

```bash
python3 agents/cold-outreach-builder/scripts/run_dossiers.py prepare --leads <project>/first-users-hunter/prospects-<YYYYMMDD>.csv --run-dir <run>
cp -R <project>/first-users-hunter/handoff-<YYYYMMDD>/dossiers <project>/first-users-hunter/handoff-<YYYYMMDD>/cache <run>/
```

Consumers map these columns directly. `cold-outreach-builder` needs `email` for the email channel and `linkedin_url` or `profile_url` for the LinkedIn channel; rows missing the needed contact field are kept in its report under "Skipped: no contact" and excluded from the sequencer export.
