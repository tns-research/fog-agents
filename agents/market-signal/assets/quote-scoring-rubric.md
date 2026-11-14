# Quote selection rubric

Which verified quotes to pick, and for what use. Used at Step 4 by `skills/extracting-psychographic-profile/SKILL.md`.

Admission is not a judgement call: `scripts/verify_quotes.py` admits a quote only when its passage is found word for word in a stored record dated inside the window, with a url. This rubric ranks the quotes that pass, and every field it reads exists in the corpus or the labels. A field the source does not provide (account age, karma) is never estimated: it is absent and plays no part.

## One admission rule

A quote can ship when all of these hold. The first three are checked by script; the last two rest on the labels and are the model's to hold.

1. The passage is in the record, contiguous, unchanged (`verify_quotes.py`).
2. The record's date is inside the window (`verify_quotes.py`).
3. The record has a url (`verify_quotes.py`).
4. The record is labelled `relevant: true` (`labels.jsonl`).
5. The speaker is `user` or `practitioner`. A `vendor`, `press` or `other` record can be quoted only as such (say so where it is used), never as the voice of the persona.

## Ranking the admitted quotes

| Criterion | Read from | Prefer |
|-----------|-----------|--------|
| Speaker | `labels.jsonl` `speaker` | `user` over `practitioner` for pain language; `practitioner` for the norms of the market (what investors expect, what works) |
| Specificity | the text | names a tool, an amount, a time spent, a step, an edge case; "it is annoying" ranks last |
| Intensity | the text | a strong verb or a concrete cost; high intensity makes headlines, low intensity makes body copy |
| Resonance | `score` against `community_medians` in `stats.json` | above the community median when the source has a score (Reddit, Stack Exchange, Discourse); Hacker News comments and App Store reviews have none, which is neutral |
| Spread | `author_hash` | quotes of several authors per pain over several quotes of one author |
| Length | `char_count` after the build | `headline` under about 90 characters; longer ones are `support` or `quote_slide` |
| Recency | `date` | the newer of two equivalent quotes |

## Uses

| `usable_as` | Fits |
|-------------|------|
| `headline` | says the pain alone, short, no context needed |
| `support` | proof under a headline, can be longer |
| `hook` | opens a post or a message: a question people ask, a sharp admission |
| `objection` | a reason not to act, in the buyer's words |
| `outreach_opener` | language a cold message can mirror (never quoted at the person) |
| `quote_slide` | a carousel slide that shows the quote with its public source |

## Privacy

Neither the corpus nor the sidecar stores a handle: records carry only `author_hash`, a pseudonym, and texts have contact details and profile links replaced by placeholders. A consumer never resolves it, never shows a handle, never attaches a quote to a company or a face. A quote is the words of a public stranger about a problem: language for copy, never a testimonial of the founder's product ([`../../../shared/handoffs.md`](../../../shared/handoffs.md)).

## Anti-patterns to refuse

- Picking quotes to reach a count: the value is the filter. Fifteen good quotes beat thirty weak ones.
- Several quotes of one author to make a pain look common: the counts already say how many people.
- Quoting a vendor's pitch or a journalist's paraphrase as the persona's voice.
- Translating before choosing: choose in the original language, translate at use, keep the original.
