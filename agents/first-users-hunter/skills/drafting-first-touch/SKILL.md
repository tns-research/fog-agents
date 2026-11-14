---
name: drafting-first-touch
description: Writes the first two touches for one person with a dated public signal, after reading the whole thread the signal sits in. Touch 1 answers where the person spoke (a reply or comment that adds something, no pitch, no link); touch 2 is a DM, a connection note or an event introduction with at most one small ask. Applies a blocking review grid (signal cited with its URL, no proof outside the claims ledger, full sentences, the person's language, network length limits) and drops people with no real overlap instead of forcing a link. Use at Step 6 of first-users-hunter for each shortlisted person. Triggers on "first message", "what do I say", "reply to this post", "DM", "connection note".
license: Apache-2.0
compatibility: Claude Code, Cursor, Codex CLI, Gemini CLI
metadata:
  version: "2.0"
allowed-tools: Read Write Bash
---

# drafting-first-touch

The person said something in public. The first touch answers that, where they said it, so they meet the founder as someone useful in their own thread. The offer comes later, and only when the person's words call for it.

## Inputs

- One line of `<run>/shortlist.jsonl`: identities, the signal (type, URL, thread URL, date, verbatim text), activity, score.
- The whole thread: cache it before reading with `python3 scripts/cache_page.py --cache <run>/cache <thread_url>` (or `--url <thread_url> --from-file <text>` when another provider fetched it). Add every URL read to `pages_read`.
- The offer and the proof: project-context (`what_it_is`, `offer.core`, `positioning.proof`), nothing else. `voice.banned_words` apply.
- Work in waves of three sub-agents, one person each, when the harness has them; otherwise one person after the other in the same session. The end of each task is a row in `people-<YYYYMMDD>.jsonl`.

## Step 1: read before writing

Write down, for yourself:

- what the person asked or said, in one sentence, and what the replies already gave them;
- the language they write in (the touches use it) and, in French, the form of address they use (`tu` or `vous`);
- where touch 1 can go: under the signal (HN, Reddit, GitHub, LinkedIn and X comments), or nowhere public (a closed group: touch 1 is then the group reply the founder posts there);
- the one fact of the offer that meets their need, if there is one. **If none, drop the person** with the reason ("asks for a waitlist tool; the offer is an accelerator"): a forced link reads as a pitch.

## Step 2: fit

`fit.reason`: one sentence in your words on why this person fits the target user, `fit.source_url` the page that shows it (often the signal itself), `fit.excerpt` optional verbatim words of that page. `verify_people.py` checks the excerpt against the cache.

## Step 3: touch 1, where they spoke

`first_touch.channel: reply_in_thread` (or `connection_note`, `dm`, `event_intro` when no public reply is possible: an event host, a registry person found on LinkedIn).

- It answers the person's actual point: a concrete angle, a question that moves their problem forward, a counter-example. 1 to 4 sentences.
- No link, no calendar, no "let's hop on a call". No compliment opener ("great post"), no "I'm X from Y" opener.
- The offer is named only when the person asked for exactly what it is ("can anyone recommend a program in Paris that works before the round" and the offer is that program), in one plain clause, with the facts of project-context.
- No claim about the sender's past results, clients or numbers unless it is in `positioning.proof`. No number at all without a source.
- Length: X replies 280 characters, LinkedIn connection notes 200, other channels per `assets/criteria.json > touch_limits`.

## Step 4: touch 2, after touch 1 went out

`second_touch` is optional. Channel: `dm` or `connection_note` on the network where the person is most active, `email` only to an address they published, `event_intro` for an event (what to say in the room). It recalls touch 1 in a clause, says who the sender is in one clause, and may hold **one small ask** that serves the person or validates the problem ("would a short call on where you are in the raise help?"). At most one link. The signature, when there is one, is `{{sender_first_name}}`; no other placeholder survives.

## Step 5: review grid (blocking)

Apply [`assets/first-touch-rubric.md`](../../assets/first-touch-rubric.md) to each row, then run:

```bash
python3 scripts/verify_people.py <project>/first-users-hunter/people-<YYYYMMDD>.jsonl --run-dir <run>
```

It blocks: an excerpt not in the cached page, a link in touch 1, a length over the network limit, a placeholder left, a dash, the same touch 1 for two people, an email not on its page. The writing gate then runs on `first-touches-<YYYYMMDD>.md` after export. Fix the draft, never the checks.

## Example (fictional person, from the example run)

Signal (Ask HN, 2026-10-03): "Any advice on where pre-seed founders in Europe actually find their first real users? I am based in Paris and starting to feel stuck."

Touch 1 (HN reply): "Your four users came through friends of friends, so one question first: do they share a specialty or a city? If they do, the next ten probably read the same newsletter or belong to the same association, and that is where you can ask in public. Happy to think through the clinic angle here if you share more."

Touch 2 (LinkedIn connection note, 165 characters): "Hello, I answered your Ask HN comment on first users for small clinics. I work at swanbase, a growth marketing accelerator for European startups. Glad to swap notes."

## Anti-patterns

- Opening on the sender instead of the person's point.
- Paraphrasing the signal in the message without being in its thread: the person cannot tell what you answer.
- One template with the name swapped: `verify_people.py` refuses identical touches, and a near-identical one fails the rubric.
- Quoting a public complaint back to its author in a way that exposes them.
- An invented common ground ("we work with many founders like you").
- Dropping the language or the register the person uses.
