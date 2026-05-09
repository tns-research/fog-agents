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

A surprising number or data point relevant to the ICP.

Patterns:
- `<number> <unit> <topic>`
- `<n>x <metric> in <timespan>`

Examples:
- `0 to 50 customers in 90 days`
- `40% lift on the bump email`
- `30 SaaS, same activation gap`

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
| 4. Social proof | B | `30 SaaS, same activation gap` |
| 5. Direct ask | C, short | `15 minutes Thursday?` |
| 6. Breakup | C, short | `closing the loop` |

---

## Personalization in subject

A subject with a `{{specific_observation}}` token outperforms a generic subject by 30 to 50 percent in well-targeted ICPs. Examples:

- `your post on <topic>?` (uses `{{topic_from_post}}`)
- `<their named tool> migration?` (uses `{{tool_they_use}}`)
- `your <hire name>'s onboarding?` (uses `{{recent_hire}}`)

The token must reference a verifiable public artifact. If the token cannot be filled per prospect, fall back to a generic subject for that prospect; never ship a broken token.

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

The 30 to 50 percent reply-rate uplift from personalized subjects is conditional on the personalization being concrete and verifiable. A token that resolves to "your work" or "your company" adds nothing.
