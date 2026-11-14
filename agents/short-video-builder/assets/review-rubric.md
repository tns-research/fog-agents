# Review rubric

Used by the model's own review (render-and-review, step 3) and by the fresh reviewer ([`../../../shared/skills/reviewing-with-fresh-eyes/SKILL.md`](../../../shared/skills/reviewing-with-fresh-eyes/SKILL.md)). Score each criterion 0, 1 or 2 per short, and name the frame or the second for anything under 2. Ship at 0 errors in `export/qa.json` and no criterion under 2; after three rounds, ship with the open items listed first in the report.

| # | Criterion | 2 | 1 | 0 |
|---|-----------|---|---|---|
| 1 | Hook | the first sentence is the strongest opening of the excerpt and is heard within the first second; frame one is the speaker | the hook is right but slow, or the first frame is weak | opens on a greeting, a filler, a card or a fade |
| 2 | Standalone | a stranger follows it with no context: no dangling "this", no unexplained name | one reference needs the talk to make sense | the point depends on what came before |
| 3 | Caption truth | every caption word matches what is said; names, figures and acronyms right | one minor word off | a wrong name, a wrong figure, or a nonsense word on screen |
| 4 | Framing | the face stays in frame, calm holds and slow glides, the right person when several are visible | one moment near the edge, or one glide too fast | face cut, wrong person, or a nervous camera |
| 5 | Captions on screen | groups short, the line stays put, only the colour moves, readable at feed size, never over the eyes for long | one long group or one tight spot | flicker, blinks, split words, overlapping lines, unreadable |
| 6 | Cut points | starts and ends on sentence edges; the last sentence lands | the end trails a little | cuts mid-sentence or mid-word |
| 7 | Sound | even level across shorts, no click at the cut, voice clear, end fades | level slightly off or a small click | clipped, inaudible, or a hard cut on a word |
| 8 | End and package | end card (when asked) after the last word over moving picture, colours and text right; title and post pass the writing gate and the claims check | one weak line in the copy | a frozen silent card, an intro card, an unsourced claim |

Total out of 16 per short. Under 13, or any 0, is a FAIL for the fresh reviewer.

How to look: `review/first-frames.png` first (every short's opening, at feed size), then each `review/<id>/sheet-feed.png` (as the viewer sees it), `sheet.png` (details), `captions-strip.jpg` (caption behaviour frame by frame), and the MP4 itself when the host can play it.
