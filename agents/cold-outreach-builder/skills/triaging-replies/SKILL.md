---
name: triaging-replies
description: Closes the loop after the founder sends a sequence. Reads the replies the founder exported (a CSV from the sequencer or the inbox, .eml files, an .mbox), classifies each one as positive, negative, out of office, off topic or bounce with the sentence that triggered the class, updates the outreach state (sequences stopped, contacts suppressed, out-of-office contacts paused until their return), lists the next actions, and drafts the answers for the founder to validate. Ambiguous replies are read by the model, whose class must quote the reply. Use at Step 11 of cold-outreach-builder and at the start of every later run. Triggers on "replies", "who answered", "follow-ups", "inbox export", "next actions".
license: Apache-2.0
compatibility: Claude Code, Cursor, Codex CLI, Gemini CLI
metadata:
  version: "2.0"
---

# triaging-replies

A sequence without reply handling recontacts people who said no and lets the people who said yes wait. This skill keeps one state file per project and moves every contact through it from what the replies say.

State: `<project>/cold-outreach-builder/state/state.json`, managed by [`../../scripts/outreach_state.py`](../../scripts/outreach_state.py). Replies: [`../../scripts/ingest_replies.py`](../../scripts/ingest_replies.py). Cues: [`../../assets/reply-rules.json`](../../assets/reply-rules.json). No connector to a mailbox or a sending tool: the founder exports, the scripts read files.

## When the founder imports a sequence

```bash
python3 scripts/outreach_state.py init --state <state.json>          # once per project
python3 scripts/outreach_state.py register --state <state.json> \
  --export <run>/sequence-export.csv --sequence-id outreach-<YYYYMMDD> --start-date <first send day>
```

`register` records every row with its planned step dates. It refuses (exit 1) a contact already in an open sequence or suppressed; `--force` only on the founder's explicit decision. When the founder's tool confirms what went out: `mark-sent --sequence-id <id> --through-step <n> --date <day>`.

## When replies come in

1. The founder exports the replies: the sequencer's reply CSV, or the inbox as `.eml` files or an `.mbox`.
2. Ingest:

   ```bash
   python3 scripts/ingest_replies.py --state <state.json> --csv <replies.csv> --eml <folder> \
     --report <project>/cold-outreach-builder/replies-<YYYYMMDD>.md
   ```

   The script removes the quoted history (lines starting with `>`, everything after "On ... wrote:" or "Le ... a écrit :"), then classifies:

   | Class | Cue | State |
   |-------|-----|-------|
   | `bounce` | mailer-daemon, delivery failure, 550 5.1.1 | `bounced`, suppressed (the recipient is read from the bounce body) |
   | `out_of_office` | auto-reply headers or absence wording | `paused` until the return date found in the reply, else 7 days |
   | `negative` | not interested, not a priority | `replied_negative`, suppressed |
   | `negative` + unsubscribe | remove me, stop, ne plus recevoir | `unsubscribed`, suppressed |
   | `off_topic` | wrong person, left the company, referral | `off_topic`, the founder reads it |
   | `positive` | interested, happy to chat, send it, a time | `replied_positive`, answer due |

   A closed sequence cancels its remaining steps: tell the founder to stop them in the sending tool too (most tools stop on reply by themselves; bounces and out-of-office replies need a check).
3. **Read every `needs_review` reply.** No cue matched, or cues of several classes matched ("not now, but happy to talk in spring"). Read the reply and decide. Write an override that quotes the reply word for word:

   ```json
   [{"message_id": "r-hal-1", "class": "positive", "quote": "happy to chat in the spring once the round is closed"}]
   ```

   Re-run with `--overrides <file>`. An override whose quote is not in the reply is rejected (exit 1): the class must rest on what the person wrote. An unsubscribe request found by reading adds `"unsubscribe": true`.
4. `unmatched` replies come from an address the state does not know (a colleague, a forward): list them for the founder, change nothing.

## Next actions

```bash
python3 scripts/outreach_state.py due --state <state.json> --out <project>/cold-outreach-builder/followups-<YYYYMMDD>.md
```

Five lists, computed without the model: answer (positive, they wrote last), read (off topic), resume (back from absence), check the sequencer sent the steps now due, close (every step sent, no reply).

For each "answer" entry, draft a reply for the founder to validate: it answers what they wrote, in their language and register, proposes one next step (a time, the artifact they asked for), and passes the same gates as the sequence (writing gate, claims). The agent never sends it. When the founder has answered, `outreach_state.py answered --contact <email>`.

## Reading results across runs

`outreach_state.py summary --by sequence|tier|angle` prints, per group, contacts, contacts sent, and replies per class. It names no winner. Compare classified replies, never opens (no tracking pixel in this stack), and write the sample size next to every rate: a difference of a few replies between two groups of a few dozen is noise. The founder decides when a group is large enough.

## Failure modes

- **A reply CSV with other column names** → the script detects the common ones (from, email, sender; date; subject; body, text, message, reply). Rename the columns of an unusual export rather than editing the script.
- **The same export ingested twice** → messages already processed (by id) are skipped.
- **A bounce wave** (many bounces in one send) → stop the sequence, check the list source and the sender with `check_sender.py`; never re-validate addresses by probing SMTP from this machine.
- **The founder corrects a class** → write the override with the quote; if the correction is a pattern, propose it as a project decision (keeping-project-memory) and, when it is a cue, add it to `<project>/cold-outreach-builder/reply-rules.json`.
