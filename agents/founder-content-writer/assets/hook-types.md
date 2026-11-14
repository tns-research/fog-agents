# Hook types and angle types

The vocabulary of `posts-spec.json` ([`posts-spec.schema.json`](posts-spec.schema.json)). A batch uses each hook type and each angle type at most once per three posts, rounded up: `check_spec.py` counts them.

## Hook types: what the first line does

| `hook_type` | The first line | Needs | Checked by script |
|-------------|----------------|-------|-------------------|
| `decision` | states something the founder stopped, started or changed | a founder passage where that decision is told | a founder passage is cited |
| `confession` | states a mistake the founder made | a founder passage where the founder says so | a founder passage is cited |
| `scene` | opens on one moment: a call, a day, an exchange, with the details the founder gave | a founder passage holding that moment | a founder passage is cited, time markers come from it |
| `contrarian` | contradicts a belief the audience holds, and the rest of the post says why | a stance the founder actually took in the material | |
| `observation` | names a pattern the founder keeps seeing | the founder's passage; no count, no "most people" without a source | crowd claims need a passage or a URL |
| `question` | asks a question the reader really asks | an objection or a question found in the material | the first line holds a question mark |
| `number` | opens on a number | an item of `positioning.proof` or a sourced passage | the first line holds a number with a declared claim |
| `customer_words` | opens on the words of someone in the market | a verified market-signal quote, kept verbatim | a market-signal passage is cited |
| `how_to` | promises a method the post then gives | steps the founder actually described | |

Pick the type the material offers, never the other way round. A voice note with no decision in it yields no `decision` hook.

## Angle types: what the post is for

| `angle_type` | The reader leaves with |
|--------------|------------------------|
| `lesson` | one thing the founder learned, with the event that taught it |
| `method` | steps they can apply this week |
| `story` | what happened, in order, with its outcome if the founder gave one |
| `market_reading` | what people in the market say and what it means for them |
| `behind_the_scenes` | how the company works, shown through one concrete moment |
| `position` | a stance the founder holds, with the reason |
| `objection` | an honest answer to what stops people from buying or trying |

## Structures

| `structure` | Shape |
|-------------|-------|
| `take_then_method` | the stance, why, what to do |
| `problem_cause_action` | the problem as the reader lives it, what causes it, one action |
| `story_then_lesson` | the moment, what followed, the one thing to keep |
| `checklist` | a short promise, then a list whose count the post announces correctly |
| `before_after` | how it was, what changed, how it is |
| `single_idea` | one idea, developed once; the usual shape on X |
