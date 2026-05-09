# E-E-A-T audit checklist

E-E-A-T (Experience, Expertise, Authoritativeness, Trust) is Google's quality framework, expanded with the first "E" (Experience) in December 2022 and now central to 2026 ranking and AI-citation behavior. The March 2026 core update explicitly penalized 55% of monitored sites with weak E-E-A-T.

Used by `auditing-geo-aeo/SKILL.md` Step F as a foundational signal check, and by `mapping-content-clusters/SKILL.md` to evaluate whether a pillar can credibly hold topical authority.

---

## The four signals

### Experience - first-hand involvement

Has the author actually done the thing they're writing about? Specifics that prove first-hand experience:

| Check | What to look for |
|-------|------------------|
| First-person account | "I tested X for 3 months..." rather than "X is a tool that..." |
| Specific numbers | "I sent 240 invoices in 2025", concrete, dated |
| Original screenshots | UI screenshots from the author's actual usage, dated |
| Dated events | "In Q2 2025, I switched from..." |
| Limitations honestly named | "X works for solo freelancers but breaks at 5+ team members because..." |

Pages with no first-hand markers are pure secondary content. Treated as low-Experience.

### Expertise - qualified to speak

Author credentials that are verifiable.

| Check | What to look for |
|-------|------------------|
| Named author | Real name, not "Editorial Team" or "Admin" |
| Bio with credentials | Education, prior roles, specific years of experience |
| Persistent author page | `/author/<slug>` URL on the domain, linkable |
| External profile links | LinkedIn, Twitter/X, personal site (sameAs schema) |
| Topic-relevant credentials | A finance writer with finance background, not a generic content marketer |
| Publication history | Other articles on related topics by the same author, on this site or elsewhere |

### Authoritativeness - the site/author is recognized

Whether the broader web treats this content/author as authoritative.

| Check | What to look for |
|-------|------------------|
| Backlinks from authoritative sources | Domain has been cited by recognized industry sites |
| Wikipedia mentions | The brand or author appears on Wikipedia |
| Press mentions | Linked press coverage on the domain (linked, not screenshotted) |
| Organization schema with sameAs | Brand entity established with official social links |
| Speaker / author at named events | Conference talks, named podcast appearances |
| Industry certifications | Official designations where applicable (CPA, MD, CFA, etc.) |

### Trustworthiness - the foundation

| Check | What to look for |
|-------|------------------|
| HTTPS, no mixed content | Basic table stakes |
| Visible contact info | Real email, phone, or office address |
| Visible privacy + terms pages | Linked from footer |
| About page with team | Real photos, real bios, not stock |
| No misleading claims | No "guaranteed results", no fabricated stats |
| Clear ownership / publisher | Who runs this site? |
| Refund / return policies | For commercial sites |
| Disclosed conflicts of interest | Affiliate disclosure where applicable |

---

## Per-page audit (run for each top-priority ranking page)

```yaml
eeat_audit:
  url: ...
  experience:
    first_person_voice: yes/no
    specific_numbers: yes/no
    original_screenshots: yes/no
    dated_events: yes/no
    score: 0-4
  expertise:
    named_author: yes/no
    bio_with_credentials: yes/no
    persistent_author_page: yes/no
    sameAs_links: count
    score: 0-4
  authoritativeness:
    backlinks_from_authority: count
    press_mentions: count
    organization_schema: yes/no
    score: 0-3
  trustworthiness:
    contact_info_visible: yes/no
    privacy_terms: yes/no
    about_page_quality: low|med|high
    affiliate_disclosure: yes/no/na
    score: 0-4
  total: 0-15
  diagnosis: "Bottleneck = Expertise (no author bio). Fix priority HIGH."
  next_actions:
    - "Add named author with bio at top of article"
    - "Create /author/sarah-lin with credentials + sameAs"
    - "Add dated 'I tested X' anecdote in intro"
```

---

## Site-level audit (run once per audit)

| Check | Pass condition |
|-------|----------------|
| /about page exists | Yes, with team photos and bios |
| /authors directory | At least one persistent author page |
| Organization schema on home | Present, with sameAs to LinkedIn + at least 2 other profiles |
| Editorial standards page | Visible link from footer (rare for founder sites, flag for creation) |
| Last-updated dates on all articles | Present and truthful |
| External backlink profile | Spot-check via Open Pagerank or similar; min 5 referring domains for credibility |

---

## Common patterns and diagnoses

| Symptom | Bottleneck | Fix |
|---------|------------|-----|
| Founder personally writes everything but isn't credited | Expertise (gap is just visibility) | Add bylines + author page; cheap fix |
| Content is summary of secondary sources | Experience | Add first-hand specifics; harder fix |
| Site is anonymous (no team page, no contact) | Trust | Build out about page; medium fix |
| Site is new with no backlinks | Authoritativeness | Time-and-effort issue; surface as 6-month roadmap, not 7-day fix |
| Site has all signals but content is thin | All four collapsed because content fails everywhere | Re-audit content depth before E-E-A-T efforts |

---

## Anti-patterns to refuse

- **Auto-generating fake author pages.** AI-generated bios for fictional experts are a violation; they will be caught. Use real authors.
- **Stock photos for team members.** Reverse image search catches them. Real photos or no photos.
- **Padding bios with vague credentials.** "Industry expert with 10+ years of experience" is not a credential; it's filler. Specific roles, named companies.
- **Citing your own pages as "expert sources".** Self-citation is not E-E-A-T. External authoritative citations are.
- **Treating E-E-A-T as a Google-only concept.** AI engines (Perplexity, ChatGPT) weight similar signals. The audit serves both surfaces.

---

## Source

Compiled from Google Quality Rater Guidelines (December 2022 + 2024 + 2026 updates), Search Engine Land's E-E-A-T post-March-2026 analyses, and the Sistrix / SEMrush studies on the March 2026 core update. Calibrated for founder-stage sites where formal credentials are often modest but first-hand experience is high.
