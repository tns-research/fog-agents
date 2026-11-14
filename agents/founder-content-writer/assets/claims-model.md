# Claims model of a post

How the `claims` of `posts-spec.json` map to the shared policy ([`../../../shared/skills/enforcing-claims-policy/SKILL.md`](../../../shared/skills/enforcing-claims-policy/SKILL.md)). `check_spec.py` applies this table; every row of the batch's ledger comes from it.

| `source` | Use for | Fields | What the script checks |
|----------|---------|--------|------------------------|
| `proof` | a number, a client, a result, a press mention or a ranking the founder approved | `proof_index` | the index exists; the item is usable for posts according to `../../../shared/scripts/proof.py` (a stale metric or a testimonial without consent is refused: `proof-not-usable`); every number of the claim is in that proof item with the same unit (no rounding, a count never becomes a percentage); the wording stays close, or a warning |
| `quote` | words from a verified market-signal quote | `passage_index` | the passage is a market-signal one; every number is in it; never kind `customer`, `testimonial`, `result`, `press` or `ranking` |
| `url` | a fact from a third-party page ingested with its `--url` | `passage_index` | the passage is a third-party one; every number is in it; the URL goes in the ledger |
| `passage` | a qualitative observation or anecdote of the founder | `passage_index` | the passage is a founder one; **no number** (a year from the passage may stay); never kind `number`, `customer`, `testimonial`, `press`, `ranking` or `result`; the claim shares words with its passage |
| `structure` | a count of the post's own list ("three things to check") | none, kind `post_count` | the number equals the items of the list |
| `none` | a number word that counts nothing ("half the battle") | `reason`, kind `idiom` | never a digit; shown as a warning and in the ledger for the founder to read |

## What the script looks for in the bodies, declared or not

| Finding | Rule |
|---------|------|
| `unsourced-number` | every digit and every number word sits inside a declared claim, or is a list marker at the start of a line, or is a year found in a cited passage or in the proof |
| `ranking-unsourced`, `crowd-claim-unsourced` | "the best", "#1", "most founders", "the majority of" sit inside a declared claim |
| `time-marker-not-in-source` | "yesterday", "last week", "in March" appear in a cited passage or in the proof |
| `client-not-in-source` | "a customer", "one of our users" appear only when a cited passage talks about that person |
| `quote-not-in-source` | words in quotation marks (three words or more) are inside a cited passage |
| `untraced-event` | a sentence that tells something that happened ("we signed", "I lost") shares words with a cited passage, the proof or the context. Without an event in it, the same sentence is an `untraced-sentence` warning: fine as the founder's opinion, and the reviewer reads it |
| `name-not-in-sources` | a capitalized word in the middle of a sentence is in a cited passage, in `project-context` or in `config.allowed_names`. Found only in the notes, it is a `third-party-name` warning: a tool is fine, a client needs the proof list |

## Dropped material

What the notes hold and the policy refuses goes under `dropped` in the spec, with the reason and what would make it usable. The founder reads that list in the report and decides what to add to `positioning.proof`. A number the founder really has is one line away from a post; an invented one never reaches a reader.
