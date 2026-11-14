# Subject Line Patterns

Rules and templates for cold-email subject lines. The subject decides whether the email is opened.

Pairs with `copywriting-en/SKILL.md` and `banned-patterns.md`.

---

## Hard rules

- **33 to 50 characters.** Android Gmail truncates the subject at 33 characters. Front-load the hook in the first 33.
- **Lowercase first letter** unless naming a proper noun. Capitalized subjects look like marketing.
- **No emoji** in cold email. Emoji in cold email drops opens in B2B.
- **No ALL CAPS.** Triggers spam filters and reads as desperation.
- **No clickbait** ("YOU WON'T BELIEVE"). Reads as scam.
- **No "Quick question"** or "Quick favor". Cliché. Often filtered.
- **One thought.** No subject with two ideas separated by a comma.

---

## Subject styles (A / B / C)

For Email 1 of every sequence, generate three variants in different styles. Test 50/50 on the first batch and pick the winner for the rest.

### Style A: question

A direct question the reader can answer in their head before opening.

Patterns:
- `<their company> + <topic>?`
- `worth comparing on <topic>?`
- `<specific role-action> at <their company>?`

Examples:
- `acme's onboarding plan?`
- `worth comparing on activation?`
- `pricing experiment at <company>?`

### Style B: stat

A surprising number or data point relevant to the ICP. The number must be an allowed claim (`positioning.proof`) or carry a source URL in the report; otherwise use style A or C. The example numbers below illustrate the shape only.

Patterns:
- `<number> <unit> <topic>`
- `<n>x <metric> in <timespan>`

Examples (every `<...>` slot is filled from `positioning.proof` or a sourced fact, never invented):
- `<n> customers in <timespan>`
- `<sourced figure> on the bump email`
- `<n> SaaS, same activation gap`

### Style C: direct

A specific, low-key statement of the email's content.

Patterns:
- `<topic> for <their company>`
- `<specific noun> for <their role>`
- `<artifact name> attached`

Examples:
- `activation playbook for acme`
- `12-point checklist attached`
- `notes from your last post`

---

## Subject by message purpose

| Message | Subject style | Example |
|---------|---------------|---------|
| 1. Initial hook | A or C | `acme's onboarding plan?` |
| 2. Bump | reuse with `Re:` | `Re: acme's onboarding plan?` |
| 3. Value drop | C | `12-point checklist attached` |
| 4. Proof or perspective | B with an allowed claim, else A or C | `<allowed claim, shortened>` or `how the activation gap forms` |
| 5. Direct ask | C, short | `15 minutes Thursday?` |
| 6. Breakup | C, short | `closing the loop` |

---

## Personalization in subject

A subject built on the prospect's verified fact (written per person for tier A, a short token for tier B) shows the prospect, before opening, that the message is about them. Examples:

- `your post on <topic>?` (uses `{{topic_from_post}}`)
- `<their named tool> migration?` (uses `{{tool_they_use}}`)
- `your <hire name>'s onboarding?` (uses `{{recent_hire}}`)

The token must reference a verified fact of the dossier. If the token cannot be filled per prospect, fall back to the template's subject for that prospect; the export never ships a broken token and the lint blocks any that remains.

---

## Banned subject patterns

- `Quick question`
- `Quick favor`
- `Hi {{first_name}}` (no signal)
- `Following up` (no context)
- `Let's connect` (LinkedIn vocabulary leaking into email)
- `I hope this finds you well` (truncates to "I hope this finds y..." on mobile)
- `[BREAKING]`, `[URGENT]`, `[ACTION REQUIRED]` brackets
- Any subject with `!` or `?!`
- Anything in ALL CAPS
- Any emoji

---

## A/B/C variant rule

Email 1 ships with three subject variants (A, B, C). The sending tool splits 33/33/33 on the first batch (recommended ≥30 prospects per variant for any signal).

After the first batch, the agent's report names the winner and ships the rest with that subject. The losing variants stay logged for future reference; the agent never declares a winner without ≥30 sends per variant.

---

## Length check

A subject ≤33 characters is safe across all email clients. A subject >50 characters is truncated on most clients. Between 33 and 50, the subject is fully visible in desktop clients but truncated on mobile Gmail.

When in doubt, cut. The shortest viable subject usually wins.

---

## Notes

These patterns are language-agnostic in spirit. For FR-specific adjustments (accent encoding, longer average length), see `copywriting-fr/SKILL.md`.

A personalized subject only helps when the personalization is concrete and verifiable. A token that resolves to "your work" or "your company" adds nothing. Measure the effect on the founder's own replies, never quote an outside uplift.
