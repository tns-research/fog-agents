# LinkedIn search patterns

Boolean query patterns for LinkedIn search and Sales Navigator, used in Step 5 (LinkedIn-adjacent profile mapping) of the agent workflow.

The agent does not log into LinkedIn or scrape it directly. These patterns are also reusable on Exa with `--include-domains linkedin.com` for the slice that's publicly indexed, and on personal sites / IndieHackers / Read.cv that mirror the same persona axes.

---

## Boolean syntax rules (LinkedIn-specific)

LinkedIn boolean is more restrictive than Google's:

| Rule | Detail |
|------|--------|
| Operators must be UPPERCASE | `AND`, `OR`, `NOT` only. Lowercase is treated as keywords. |
| Max ~15 operators per query | LinkedIn truncates beyond this and silently fails. |
| Phrase quotes | `"Head of Sales"` matches the exact phrase. Drop the quotes and it splits. |
| No wildcards | `engineer*` does not match `engineers`, `engineering`. Use OR list. |
| Parentheses for grouping | `("Head of X" OR "VP X") AND ("FinTech" OR "InsurTech")` |
| NOT must come before each excluded term | `NOT recruiter NOT consultant`, not `NOT (recruiter OR consultant)` (LinkedIn handles this fine but order matters) |
| Title field requires distinct field operator on Sales Nav | use the `title:` filter directly when available; boolean in keyword field is broader |

---

## Pattern library

### Pattern 1: target by role + vertical

```
("Head of Growth" OR "VP Growth" OR "Growth Manager")
AND ("SaaS" OR "B2B SaaS")
NOT "Recruiter"
NOT "Consultant"
```

Use when: target user is defined by a stable role pattern in a specific industry.

Refinement: add `AND ("seed" OR "Series A")` to filter by stage, or location filter to scope geography.

### Pattern 2: target by founder pattern

```
("Founder" OR "Co-Founder" OR "CEO")
AND ("SaaS" OR "tech startup")
AND ("2-10 employees" OR "11-50 employees")
NOT "Recruiter"
```

Use when: target is early-stage founder. Combine with company-size filter where Sales Nav exposes it.

### Pattern 3: target by skill cluster

```
("Product Manager" OR "Senior Product Manager")
AND ("Figma" OR "Linear" OR "Notion")
AND ("Series A" OR "Series B")
```

Use when: skill or tool footprint is a stronger persona signal than role title (common for technical roles).

### Pattern 4: target by current-pain language

```
("VP Sales" OR "Head of Sales")
AND ("missing pipeline" OR "outbound problem" OR "sales productivity")
```

Use when: persona is defined by a stated pain. Mine cold-outreach Sales Navigator post-snippet view, or Exa-search public posts for the pain phrase.

### Pattern 5: target by alumni / community

```
("Founder" OR "CEO")
AND ("Y Combinator" OR "Techstars" OR "Station F")
NOT "Investor"
```

Use when: founder identity is rooted in a cohort. Combine with vertical filter.

### Pattern 6: target by switching language

```
("CMO" OR "Head of Marketing")
AND ("just left HubSpot" OR "switched from HubSpot" OR "moved off HubSpot")
```

Use when: the target is users actively switching from a competitor. Mostly produces public posts (HN, Twitter, IH) rather than profiles.

---

## How to use these patterns inside the agent

The agent does not log into LinkedIn. It produces:

1. A list of 3 to 5 boolean patterns the founder can paste directly into LinkedIn search or Sales Navigator.
2. A parallel set of Exa queries that mirror the same boolean intent on the public web (personal sites, IndieHackers, podcast guest pages, conference speaker pages):

```bash
exa search '"Head of Growth" "SaaS" -recruiter' \
  --include-domains indiehackers.com,about.me,read.cv \
  --num-results 20 --type neural \
  --json > /tmp/profiles.json
```

The Exa version of the search is what produces the **public profile list** in the report. The LinkedIn boolean is what the founder runs themselves with their own session.

---

## Anti-patterns to refuse

- **Building a 30-operator boolean**. Past ~15 operators LinkedIn silently truncates. Split into two narrower searches instead.
- **Lowercase operators**. `and`, `or`, `not` are treated as keywords. Always uppercase.
- **Quoted variable phrases**. `"head of growth"` is fine; `"head of growth at"` (with at) is too rigid. Drop trailing prepositions.
- **Stacking many NOT terms**. Diminishing returns past 3-4 NOTs. Prefer narrower positive matches.
- **Treating the boolean as the deliverable**. The boolean is the tool. The deliverable is a profile list with rationale per profile.

---

## Source

Boolean conventions adapted from LinkedIn Sales Navigator help docs (2025-2026), Recruiter community boolean libraries, and Boolean Black Belt patterns. Persona patterns calibrated for founder-targeted B2B SaaS use cases.
