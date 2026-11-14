# Example run: project-context (synthetic)

Anonymized, synthetic-but-realistic run for a fictional product **Acme Invoices**. Shows the two artifacts a real run writes into `<project-root>/acme/project-context/`.

Input given to the agent:

```
URL: https://acme.example   Language: en   web_enrichment: auto
```

---

## brand.json (after the brand checkpoint)

```json
{
  "schema_version": "2.0",
  "name": "Acme Invoices",
  "source_url": "https://acme.example",
  "as_of": "2026-06-04",
  "mode": "dark",
  "colors": {
    "bg": "#0b1020",
    "text": "#ffffff",
    "accent": "#f5a623",
    "accent_secondary": "#7c3aed",
    "on_accent": "#0b1020"
  },
  "fonts": {
    "display": { "family": "Instrument Serif", "fallback": "Georgia, serif", "source": "google_fonts" },
    "body": { "family": "Inter", "fallback": "sans-serif", "source": "google_fonts" }
  },
  "logos": {
    "on_dark": {
      "wordmark": { "path": "assets/logos/wordmark-on-dark.svg", "format": "svg", "ink": "#ffffff" }
    },
    "on_light": {
      "wordmark": { "path": "assets/logos/wordmark-on-light.svg", "format": "svg", "ink": "#0b1020" }
    }
  },
  "logo_text": "Acme Invoices"
}
```

The agent first wrote `brand-candidate.json` with confidence scores and `brand-draft.json`, rendered `brand-debug/brand-board.jpg`, and the founder corrected `colors.accent` in the draft from a mis-detected `#e8e8e8` (a near-white background swatch) to the real CTA orange `#f5a623` before approving. `--finalize` then wrote `brand.json` (excerpt above: harvested `assets`, `logo_audit`, `warnings` and `extensions` left out).

---

## context.json (after the context checkpoint)

```json
{
  "project_slug": "acme",
  "url": "https://acme.example",
  "one_liner": "Invoicing that pays freelance designers on time.",
  "what_it_is": "A freelance invoicing tool that automates reminders and holds funds in escrow until work ships, so designers get paid without chasing clients.",
  "category": "freelance invoicing tools",
  "icp": {
    "who": "Solo designers and small studios billing 2k-15k per project",
    "pains": ["late payments", "awkward reminder emails", "cashflow gaps between projects"],
    "jobs": ["get paid faster", "look professional", "stop chasing clients"]
  },
  "offer": {
    "core": "Automated invoicing plus payment reminders",
    "price_model": "Freemium, 1 percent per paid invoice",
    "differentiators": ["escrow", "no monthly fee", "designer-first templates"]
  },
  "positioning": {
    "against": "generic accounting suites that are too heavy for solo designers",
    "promise": "Get paid without chasing anyone",
    "proof": [
      { "id": "waitlist", "claim": "1,200 designers on the waitlist", "kind": "metric", "source": "https://acme.example/about", "date": "2026-05-28" },
      { "id": "indie-hackers", "claim": "Featured on Indie Hackers", "kind": "press", "source": "https://example.com/indie-hackers-feature", "date": "2026-05-12" }
    ]
  },
  "voice": {
    "tone": "founder",
    "language": "en",
    "banned_words": ["revolutionary", "game-changer"],
    "claims_policy": "no invented stats, every metric must trace to a URL or be omitted"
  }
}
```

Note how each `positioning.proof` item carries its kind, its source and the date of the fact. A "avg 11 days faster payment" line the founder mentioned verbally was **dropped** because no source could be produced, per `voice.claims_policy`. For the same reason the promise carries no multiplier ("2x faster" would be a claim of its own, and it has no source).

---

## context.md (excerpt)

```markdown
# Project context: Acme Invoices

- URL: https://acme.example
- Slug: acme
- Last updated: 2026-06-04

## One-liner
Invoicing that pays freelance designers on time.

## Who it's for (ICP)
- Who: solo designers and small studios billing 2k-15k per project
- Pains: late payments; awkward reminder emails; cashflow gaps
...

## Voice
- Tone: founder
- Claims policy: no invented stats, every metric must trace to a URL or be omitted.
```

Downstream, when the founder runs `static-ads-builder`, its Step 0 reads this folder and skips re-asking any of it. Brief copy inherits the banned words and the claims policy automatically.
