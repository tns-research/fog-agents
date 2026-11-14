---
name: enforcing-claims-policy
description: Gates every piece of copy an agent writes (emails, headlines, ad lines, title and meta rewrites, outreach templates) against the project-context claims policy. Any proof, customer name, metric, testimonial, award or ranking must come from the allowed claims in project-context (positioning.proof items that shared/scripts/proof.py finds usable for the copy's scope: fresh, sourced, consent granted) or from a source URL recorded in the deliverable; otherwise it is removed or rewritten proof-free, and every refused proof item is listed with its reason. Produces a claims ledger. Use before finalizing any copy. Triggers on "check claims", "is this proof real", "social proof", "testimonial", "stat", "case study".
license: Apache-2.0
compatibility: Claude Code, Cursor, Codex CLI, Gemini CLI
metadata:
  version: "1.1"
allowed-tools: Read Write
---

# enforcing-claims-policy

The stack's anti-fabrication gate for copy. A reader cannot tell an invented number from a real one, which is exactly why an agent must never produce one. This skill runs on every draft before it reaches a deliverable.

The policy text itself lives in `voice.claims_policy` of `project-context/context.json` (schema: `agents/project-context/assets/context-schema.json`). Default when absent: "no invented stats, every metric must trace to a URL or be omitted". The evidence the founder approved lives in `positioning.proof[]`, read through [`../../scripts/proof.py`](../../scripts/proof.py) (next section). Both are loaded by [`../loading-project-context/SKILL.md`](../loading-project-context/SKILL.md) (carousel-builder still uses its own `resolve-project-context` copy).

---

## Usable proof only

`positioning.proof[]` holds two shapes. A plain string is the short format: no kind, no source, no date. An object carries `id`, `claim`, `kind` (`metric`, `testimonial`, `customer`, `press`, `award`, `feature`), `source` (URL or project file, `docs/deck.pdf#p7` for a page of a deck), `date` (of the fact), optional `valid_days`, and `consent` for a testimonial or a customer. Rules per kind: [`../../../agents/project-context/assets/proof-kinds.json`](../../../agents/project-context/assets/proof-kinds.json).

**Rule: only the items `usable(item, scope, today)` accepts enter a copy, and the reason of every refusal is written in the deliverable.** `scope` is the use of the copy: `ads`, `carousel`, `posts`, `outreach`, `site` or `video`. `usable()` refuses:

- a stale fact: `date` + `valid_days` (default per kind: metric 180 days, customer 365, testimonial 730) is past. The number was true then; it is not a claim about now;
- a testimonial or a customer whose `consent.status` is not `granted`, whose consent has no date or no `by`, or whose `consent.scope` does not hold the copy's scope;
- an item with no `source` or no `date` when its kind needs one (every kind but `feature`), a date in the future, a malformed object.

A plain string stays usable, with a warning in the report: suggest converting it to an object with its source and date.

With a shell, from the repo root:

```bash
python3 shared/scripts/proof.py check <project>/project-context/context.json --scope ads   # usable, warning or refused, with the reason
```

From a script, `from proof import load_proof, usable, proof_text` (add `shared/scripts` to the import path): `proof_text(item)` is the claim to compare the copy against. Without Python, apply the three refusals above by hand and say "Proof check: manual" in the report.

---

## What counts as a claim

Treat each of these as a claim that needs a source:

- A number about the product or its results: users, customers, revenue, growth, percentages, time or money saved, "N x faster".
- A customer, partner or investor name, a logo, or "used by <segment>".
- A testimonial, review, rating or quote attributed to a user of the product.
- A press mention, award, certification or compliance label.
- A ranking or superlative presented as fact ("#1", "the leading", "the fastest").
- A number about the market or the prospect's world ("most founders...", "80% of teams...").

Not claims: a named product feature, the price model from `offer`, the promise from `positioning.promise` phrased as a promise, a question, a mechanism explained in plain words.

---

## Allowed sources

A claim may appear only if one of these is true:

1. **Allowed claim.** It restates a usable item of `positioning.proof[]` (section above). Use it as written: no rounding up, no extrapolation, no changing "pilot users" into "customers". A refused item is not an allowed claim, even if the number is true today: the founder updates its date or records the consent, then re-runs.
2. **Sourced URL.** It comes from a public page fetched or cited in this run, and the URL is written next to it in the deliverable (report, ledger or sidecar). Market-level numbers always need this.
3. **Founder observation** (qualitative only). A first-hand observation the user typed in this conversation, with no number and no third-party name, used as an observation ("we keep seeing teams rebuild this report by hand"). Record it in the ledger as `user-provided`.

Anything else is removed. If the founder mentions a new metric or customer in chat, do not use it: suggest adding it to `project-context` with its source, then re-run.

### Quotes from market-signal

Verbatim quotes mined by `market-signal` are the words of public strangers about a problem. Reuse them as **language** (pain phrasing, objection wording, headline raw material). Never present them as testimonials of the product, never imply the author is a customer, never attach them to a company name.

---

## Procedure

1. **Extract.** List every claim in the draft (headline, body, subject line, CTA, alt text, image text).
2. **Match.** For each claim, find its source: a usable `positioning.proof` item for this copy's scope, a URL from this run, or a `user-provided` observation.
3. **Decide.**
   - Source found → keep, add a ledger row.
   - No source → delete the claim, or rewrite the line proof-free: explain the mechanism, state the promise as a promise, or ask a question. Never swap in a vaguer invented claim ("many teams", "hundreds of founders").
4. **Check banned words.** Remove every `voice.banned_words` item from the final copy.
5. **Ledger.** Write the claims ledger into the deliverable.

---

## Output: claims ledger

```markdown
## Claims ledger

| Claim (as written) | Used in | Source |
|--------------------|---------|--------|
| <claim text> | <message 4 / H1 alt B / ad 03> | positioning.proof[1] (waitlist, metric of 2026-09-30) |
| <claim text> | <...> | <https://source.example/page> |
| <observation text> | <...> | user-provided (qualitative) |

Dropped: <claim> (no source), <claim> (not in positioning.proof)

Proof refused for <scope>: positioning.proof[2] pilot-2024 (stale: metric of 2024-05-01, valid 180 days), positioning.proof[3] lena-quote (consent covers carousel, posts, not ads)
```

When a draft holds no claim at all, write "No claims used." The "Proof refused" line lists every item `usable()` refused for the scope, whether or not the draft tried to use it, so the founder knows what to refresh. The ledger is short on purpose: its job is to let the founder verify every line in under a minute.

---

## Example copy in assets

Numbers and names inside this repo's example emails, headlines and templates illustrate structure only. They are never content: an agent must not reuse them, adapt them, or treat them as a license to write a number of the same shape.

---

## Failure modes

- **No `positioning.proof` and no source URLs** → every line is written proof-free. This is a valid outcome, never a reason to invent.
- **A template or skill step asks for proof that does not exist** → the proof-free fallback defined in that step wins over the template.
- **The founder insists on an unsourced number** → keep it out of the deliverable, list it under "Dropped" with the reason, and tell the founder how to add it to `project-context` with a source.
- **The founder insists on a refused proof item** (stale, no consent for this use) → same: out of the copy, listed under "Proof refused" with its reason and the fix (new measurement and date, or the consent with its scope).
