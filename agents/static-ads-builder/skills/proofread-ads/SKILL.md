---
name: proofread-ads
description: Blind proofread of every rendered ad. A reviewer that never saw ads.json copies every word visible on every PNG (headline, small print, button, logo wordmark, and the words printed on products, labels, packaging, signs or screens inside photos and plates), then scripts/proofread.py diffs the transcript word by word against the spec and the declared visible_text of each media. Any misspelt, missing, extra or unreadable word blocks delivery (TEXT_MISMATCH, ASSET_TEXT_MISMATCH, TEXT_UNREADABLE, NOT_PROOFREAD). Use at Step 6 of static-ads-builder, after QA passes, and on any image the founder made in their own tool. Triggers on "check the text", "typos on the ads", "label is wrong", "proofread".
license: Apache-2.0
compatibility: Claude Code, Cursor, Codex CLI, Gemini CLI
metadata:
  version: "2.0"
allowed-tools: Read Write Bash(python3:*)
---

# proofread-ads

`qa.py` proves the HTML holds the spec's words. It cannot prove what the pixels show: a glyph a font lacks, a word hidden behind a shape, and above all the text printed on a photo, a product or a generated background. An image model can render a jam label as "DÉLICESSE" for "DÉLICATESSE" and "NAISSIS" for "VANILLE", and a DOM check never sees it. This step reads every word, labels included.

## 1. Packet

`scripts/pipeline.py` writes `<run>/proofread/packet.md` (the reviewer rules and the list of PNGs) and `transcript.template.json`. Alone:

```bash
python3 scripts/proofread.py packet <run>/renders
```

The packet holds no expected text: the read is blind.

## 2. Reviewer

Take the first available (capability `critic`, [`../../../../shared/tools.md`](../../../../shared/tools.md)) and say which one ran:

| Order | Reviewer | How |
|-------|----------|-----|
| 1 | Fresh sub-agent | started with `packet.md` only; it opens each PNG at full size and writes `proofread/transcript.json` |
| 2 | Blank session or second model CLI | same packet, read-only; the agent saves its answer as `transcript.json` |
| 3 | Same model, sequential | only when 1 and 2 are unavailable: transcribe every PNG before reopening `ads.json`, in a separate pass; the report says "Proofread: same model" |
| 4 | Founder | the template and the contact sheet, "copy every word you see, labels included" |

Transcript, one object per PNG:

```json
[{"file": "acme_01_tofu_anti-category_bold-statement_4x5.png", "text": "every word seen, any order", "unreadable": false, "notes": ""}]
```

A word the reviewer cannot read with certainty sets `unreadable: true` with a note; a guess is worse than a flag.

## 3. Diff

```bash
python3 scripts/proofread.py check <run>/html <run>/proofread/transcript.json
```

Expected words per render: the DOM copy of the spec (headline, bullets, proof, source line, CTA...), the `visible_text` of each media, and the logo wordmark. Comparison: Unicode NFC, case and accents kept, edge punctuation ignored, typographic and straight apostrophes equal, word order free. Output `<run>/proofread/proofread.json`, one verdict per render:

| Verdict | Meaning | Fix at the source |
|---------|---------|-------------------|
| `TEXT_OK` | every expected word seen, nothing else | none |
| `TEXT_MISMATCH` | a copy word differs, is missing, or an extra word appears | a missing word is usually hidden or clipped: check `qa.json` and the PNG, fix the spec or the style; an extra word comes from a media whose `visible_text` was not declared |
| `ASSET_TEXT_MISMATCH` | a word printed on a media differs from what was declared | look at the real object: if the media is wrong (a generated plate or a retouched packshot), replace it with the real file or regenerate the plate through the spend gates; if the declaration was wrong, correct `visible_text` after checking the real object |
| `TEXT_UNREADABLE` | the reviewer could not read some text | make it larger or higher contrast, or a human checks that render |
| `NOT_PROOFREAD` | no transcript entry for a render | transcribe it |

Every verdict but `TEXT_OK` blocks delivery. After a fix, re-render and re-proofread the changed renders only (a new transcript entry for each).

## 4. Founder-made images

When the founder builds an ad in Canva, Figma or with an image model and drops the PNG, add it to `renders/` under the ad's name and proofread it the same way: the spec still says which words it must show.

## Report

Section "Proofread": the reviewer used, `n/n TEXT_OK`, and one line per BLOCK found and how it was fixed. Copy `status` into the run log `checks.proofread`.
