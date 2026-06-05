# Example run: project-context (synthetic)

Anonymized, synthetic-but-realistic run for a fictional product **Acme Invoices**. Shows the two artifacts a real run writes into `<project-root>/acme/project-context/`.

Input given to the agent:

```
URL: https://acme.com   Language: en   web_enrichment: auto
```

---

## brand.json (after the brand checkpoint)

```json
{
  "bg": "#0b1020",
  "text_primary": "#ffffff",
  "accent": "#f5a623",
  "accent_secondary": "#7c3aed",
  "font_heading": "'Instrument Serif', Georgia, serif",
  "font_body": "'Inter', sans-serif",
  "logo_path": "project-context/assets/logo.png"
}
```

The agent first wrote `brand-candidate.json` with confidence scores, rendered `brand-debug/brand-preview.png`, and the founder corrected `accent` from a mis-detected `#e8e8e8` (a near-white background swatch) to the real CTA orange `#f5a623` before approving.

---

## context.json (after the context checkpoint)

```json
{
  "project_slug": "acme",
  "url": "https://acme.com",
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
    "promise": "Get paid 2x faster without chasing anyone",
    "proof": ["1,200 designers on the waitlist (acme.com/about)", "Indie Hackers feature (link on file)"]
  },
  "voice": {
    "tone": "founder",
    "language": "en",
    "banned_words": ["revolutionary", "game-changer"],
    "claims_policy": "no invented stats, every metric must trace to a URL or be omitted"
  }
}
```

Note how `positioning.proof` keeps a source next to each claim. A "avg 11 days faster payment" line the founder mentioned verbally was **dropped** because no source could be produced, per `voice.claims_policy`.

---

## context.md (excerpt)

```markdown
# Project context: Acme Invoices

- URL: https://acme.com
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
