# References

## CLIs

Default providers, all optional; alternatives per capability are in [`shared/tools.md`](../../../shared/tools.md).

| CLI | Used for | Repo |
|-----|----------|------|
| `exa` | ICP language scan | https://github.com/the20100/cli-skills/tree/main/exa |
| `firecrawl` | fetching public pages for the dossiers (any `scrape` provider works; `scripts/cache_page.py` stores the text) | https://github.com/the20100/cli-skills/tree/main/firecrawl |

The agent is sequencer-agnostic: it pushes nowhere and writes `sequence-export.csv` (see `scripts/README.md`) for you to import into the tool of your choice.

## Frameworks and books

- **Robert Cialdini**: *Influence* (2021) and *Pre-Suasion* (2016): 7 levers (reciprocity, commitment, authority, liking, scarcity, unity, social proof).
- **Mailshake**: cold email playbook (subject lines, cadence, CTAs).
- **Rob Fitzpatrick**: *The Mom Test*: how to write outreach that gets a real signal back.
- **Will Allred & Jason Bay (Outbound Squad)**: modern B2B outbound principles.

## Banned patterns (in this stack)

- "Pas pour [X]" framing in French copy. Always rewrite as direct positive assertion.
- "I hope this finds you well." Banned. Replace with specific opener.
- "Synergy", "leverage", "revolutionize", "game-changer", "10x". Banned.
- Tracking pixels in cold email. Hurts deliverability and crosses a trust line.
- Generic templates like "I noticed you're a {{role}} at {{company}}." Always pair with a real observation.

## Tone guides

For French outreach to founders:
- Vouvoiement by default. Tutoiement only when the prospect's own public writing uses it with peers, recorded in the dossier (`register`, `register_source_url`); see `assets/persona-tu-vous-policy.md`.
- Casual but specific (no slang, no fake closeness).
- Founder-to-founder, never marketer-to-prospect.

## In this folder

- [`linkedin-public-posts.md`](linkedin-public-posts.md): dates and owners read from public post URLs, why profile pages are never scraped.
- [`fr-copywriting-rules.md`](fr-copywriting-rules.md): the French copy rules.

## APIs

- **Exa**: https://docs.exa.ai/
- **Firecrawl**: https://docs.firecrawl.dev/
- **CSV format**: RFC 4180, https://www.rfc-editor.org/rfc/rfc4180
