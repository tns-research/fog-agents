# Founder posts: brindlefen, 2026-10-26

**Batch:** `workshop-notes` · **Language:** en · **Audience address:** n/a (no default for this language) · **Status:** partial: fresh-eyes review not run

Five posts from your voice note and your call notes, plus one verified forum quote. The lost deal stays out: its number and its client name are not in your proof list.

**Next step:** content-publisher takes `founder-content-writer/workshop-notes-20261026/posts.json` as is: `python3 agents/content-publisher/scripts/pubqueue.py add <project>/founder-content-writer/workshop-notes-20261026/posts.json --queue <project>/content-publisher/queue.json --project <project>`, then a person approves each item. This agent never queues, approves or publishes.

---

## 1. Posts

### `import-on-day-one` (decision, lesson, problem_cause_action)

Angle: Asking for a customer file during the first call kills the conversation, so start from the work already in front of the workshop.

**LinkedIn** (493/3000)

```text
We stopped asking workshops to import their customer list on day one.

Every time we asked for it during the first call, the conversation died. Nobody in a repair workshop keeps that list in one place: part of it sits in a paper ledger, part of it in the owner's phone.

So we start with the repairs already hanging on the wall, and the list builds itself as the bikes come through.

If your onboarding asks for a file before it gives anything back, check at which call the conversation stops.
```

**X** (217/280)

```text
Nobody in a repair workshop keeps a customer list in one place. Part of it sits in a paper ledger, part of it in the owner's phone. So we start with the repairs already hanging on the wall, and the list builds itself.
```

Comes from:

- voice-note, line 5: "We stopped asking workshops to import their customer list on day one. Every time we asked for it during the first call the conversation died, because nobody in a repair workshop keeps that list in one place."
- voice-note, line 5: "Now we start with the repairs already hanging on the wall and the list builds itself as the bikes come through."

### `calendar-nobody-wanted` (confession, story, story_then_lesson)

Angle: I built a calendar for mechanics because I assumed how they plan, and watching them work showed the assumption was wrong.

**LinkedIn** (356/3000)

```text
I spent weeks on a calendar view for bike mechanics, then threw it away in July.

I had assumed mechanics plan their day. They look at the wall, they look at which bike is closest to done, and they pick that one.

Nobody asked for the calendar back.

If you build for people who work with their hands, check what they look at before they pick the next job.
```

**X** (198/280)

```text
Weeks of work on a calendar view, because I assumed mechanics plan their day. They look at the wall and pick the bike closest to done. I threw the calendar away in July and nobody asked for it back.
```

Comes from:

- voice-note, line 7: "I spent weeks on a calendar view because I assumed mechanics plan their day."
- voice-note, line 7: "They look at the wall, they look at which bike is closest to done, and they pick that one. I threw the calendar away in July and nobody asked for it back."

### `phone-they-would-pay-to-remove` (observation, position, take_then_method)

Angle: The ringing phone is the pain mechanics name first, and it is why our status texts leave without anyone touching a screen.

**LinkedIn** (422/3000)

```text
Mechanics keep telling me the phone is the problem they would pay to remove.

It rings while their hands are covered in grease, so they stop answering once the first bikes are on the stands. Then the customer walks in angry, asking if the bike is ready.

Status texts go out automatically when a repair moves to done, without anyone touching a screen with greasy hands.

The page that explains how is in the first comment.
```

**X** (217/280)

```text
The phone rings while a mechanic's hands are covered in grease, so it stops getting answered. Then the customer walks in angry. Our status texts leave when the repair moves to done. How it works is in the first reply.
```

Link, placed by content-publisher: https://brindlefen.example/status-texts

Comes from:

- voice-note, line 9: "The thing I keep hearing from mechanics is that the phone is the problem they would pay to remove. It rings while their hands are covered in grease, so they stop answering once the first bikes are on the stands."
- call-notes, line 5: "He cares that the text goes out when the bike moves to the finished hook, without anyone touching a screen with greasy hands."

### `pilot-first-week-slower` (number, behind_the_scenes, before_after)

Angle: The first week of a new tool can feel slower for a workshop, and the owner only noticed the change when the phone calmed down.

**LinkedIn** (453/3000)

```text
18 independent workshops ran the Brindlefen pilot between June and September 2026, and one owner told me how the start felt.

The first week felt slower, because the team was entering bikes they would normally just remember.

The second week was when the status texts started going out on their own, and the phone calmed down enough that he noticed it.

Then he asked for a way to say a part is on order, because that is the question customers ask most.
```

Comes from:

- call-notes, line 3: "The owner told me the first week felt slower, because the team was entering bikes they would normally just remember."
- call-notes, line 3: "The second week was when the status texts started going out on their own, and the phone calmed down enough that he noticed it."
- call-notes, line 7: "What he asked for next: a way to say a part is on order, because that is the question customers ask most."

### `forum-hour-a-day` (customer_words, market_reading, single_idea)

Angle: A mechanic's own words on a public forum name the cost of the status question better than we could.

**LinkedIn** (343/3000)

```text
"I lose an hour a day telling people their bike isn't ready yet"

A mechanic wrote that on a public forum. The sentence holds the whole job: the repair is going fine, and the work stops anyway to answer a question the customer could read on a screen.

If you sell to a trade, read what people in it write when they are not talking to a vendor.
```

**X** (159/280)

```text
"I lose an hour a day telling people their bike isn't ready yet"

A mechanic wrote that on a public forum. The repair is going fine, and the work stops anyway.
```

Comes from:

- market-signal: https://forum.example/t/shop-phone/123 (2026-10-02): "I lose an hour a day telling people their bike isn't ready yet"

## 2. Claims ledger

| Claim (as written) | Used in | Source |
|--------------------|---------|--------|
| Every time we asked for it during the first call, the conversation died | import-on-day-one: linkedin | voice-note, line 5 (user-provided, qualitative) |
| threw it away in July | calendar-nobody-wanted: linkedin | voice-note, line 7 (user-provided, qualitative) |
| I threw the calendar away in July and nobody asked for it back | calendar-nobody-wanted: x | voice-note, line 7 (user-provided, qualitative) |
| Status texts go out automatically when a repair moves to done | phone-they-would-pay-to-remove: linkedin | positioning.proof[1] |
| Mechanics keep telling me the phone is the problem they would pay to remove | phone-they-would-pay-to-remove: linkedin | voice-note, line 9 (user-provided, qualitative) |
| 18 independent workshops ran the Brindlefen pilot between June and September 2026 | pilot-first-week-slower: linkedin | positioning.proof[0] |
| The first week felt slower, because the team was entering bikes they would normally just remember | pilot-first-week-slower: linkedin | call-notes, line 3 (user-provided, qualitative) |
| I lose an hour a day telling people their bike isn't ready yet | forum-hour-a-day: linkedin, x | market-signal: https://forum.example/t/shop-phone/123 (2026-10-02) |

Dropped, because no allowed source covers it. Add it to `positioning.proof` with its source if you want it in a post:

- "We also lost the Fictivelo deal, forty-two stands": the number and the client name are not in positioning.proof, and the founder does not want to name them. Fix: add the lesson to positioning.proof without the name if you want the post.

## 3. Checks

- **Sources:** 10 passages found word for word in 3 files with unchanged hashes.
- **Claims:** 8 declared, every number traced (2 items in `positioning.proof`).
- **Writing gate:** 0 BLOCK.
- **Network rules:** content-publisher's `variants.py lint` on `posts.json`: pass.
- **Openings:** compared inside the batch and against 0 past posts (none on record).
- **Voice:** no voice pack. 0 active decisions applied.
- **Warnings kept:** 3.
  - `untraced-sentence` import-on-day-one.linkedin: 'If your onboarding asks for a file before it gives anything back, check at which call the ' echoes no cited passage: fine as the founder's opinion, check it is one
  - `untraced-sentence` forum-hour-a-day.linkedin: 'The sentence holds the whole job: the repair is going fine, and the work stops anyway to a' echoes no cited passage: fine as the founder's opinion, check it is one
  - `untraced-sentence` forum-hour-a-day.linkedin: 'If you sell to a trade, read what people in it write when they are not talking to a vendor' echoes no cited passage: fine as the founder's opinion, check it is one

## 4. Fresh-eyes review

```text
fresh-eyes: reviewer=not run
verdict: none
settled by: none
changed: nothing, deliverable unreviewed
```

## Methodology

- Providers: copy_lint local, critic not run.
- Inputs: voice-note (voice_note), call-notes (notes), market-signal (market_signal). Project context: loaded.
- Report: `founder-content-writer` batch `workshop-notes-20261026`.

## Limitations

- Fresh-eyes review: not run. This batch is unreviewed.
- No past post on record (memory/posts.jsonl, queue.json, voice exemplars): openings were compared inside this batch only.
- No voice pack at project-context/voice/voice.json: the founder's voice was not measured, only the writing gate, the banned words of context.json and the default address form ran. Run project-context with the founder's own texts to add it.
- The scripts prove that a passage exists, that numbers and names trace to a source and that the rules hold. Whether a sentence stays faithful to its passage is the reviewer's and the founder's call.
