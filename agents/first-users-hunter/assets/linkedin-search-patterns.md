# LinkedIn search patterns

Two uses at Step 2 of the agent workflow:

1. **Public posts with a signal** (the part the agent runs): web search on `linkedin.com/posts` and `x.com/<handle>/status` for the words a person writes when the need is live. These URLs carry a post id, so the date and the author come from the URL itself.
2. **Boolean queries for the founder** (optional): profile searches the founder runs in their own LinkedIn or Sales Navigator session. A profile found this way has no signal yet: it becomes a person only after one of their own dated posts is found.

The agent never logs into LinkedIn and never fetches profile pages.

---

## Public posts with a signal

Query shapes for any `web_search` provider (host web search included):

| Signal | Query |
|--------|-------|
| ask | `site:linkedin.com/posts "any recommendation" "<role or problem word>"`, `site:linkedin.com/posts "looking for a" "<tool or program word>"` |
| switch | `site:linkedin.com/posts "alternative to <incumbent>"`, `site:x.com "switching from <incumbent>"` |
| complaint | `site:x.com "<incumbent>" "so frustrating"`, `site:linkedin.com/posts "tired of" "<problem word>"` |
| question | `site:x.com "how do you" "<problem word>" "?"` |
| trigger | `site:linkedin.com/posts "we just raised" "pre-seed"`, `site:linkedin.com/posts "first hire" "<role>"` |

Then, per result URL:

- keep it only if it carries a post id (`activity-<id>`, `ugcPost-<id>`, `share-<id>`, `/status/<id>`);
- `python3 scripts/date_from_url.py <url>` gives the date and the author (LinkedIn slug, X handle); drop it when the date is outside the window of its type;
- the author slug is the person: a post where the person you want is only tagged belongs to someone else;
- fetch the post text with the `scrape` capability and add a row to `manual-signals.csv` (see `skills/collecting-signals/SKILL.md`).

**Provider note, Tavily.** Tavily's search endpoint takes `include_domains`, `time_range`, `start_date`, `end_date` and `search_depth` (basic costs 1 credit, advanced 2; [API reference](https://docs.tavily.com/documentation/api-reference/endpoint/search)). Send the phrase as `query` with `include_domains: ["linkedin.com"]` and a `time_range`, then keep only URLs under `linkedin.com/posts/`: the filter covers the whole domain, profiles and company pages included. The rest of the list above applies unchanged: the date comes from the post id, never from the snippet or a date field of the answer, and a profile page is never opened. Credits drawn are not cash in any budget of this stack.

The same search with `site:linkedin.com/posts/<slug>` or `site:x.com/<handle>/status` lists a person's own recent posts for the activity check (`activity-manual.csv`). Search engines index a fraction of LinkedIn posts: zero results means "not proven", never "inactive".

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
| NOT before each excluded term | `NOT recruiter NOT consultant` |
| Title field requires distinct field operator on Sales Nav | use the `title:` filter directly when available; boolean in keyword field is broader |

---

## Boolean patterns for the founder's own LinkedIn search

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
NOT Recruiter
```

Use when: target is early-stage founder. Company size (2-10, 11-50 employees) is a Sales Navigator filter, not a keyword: set it in the filter panel, never in the boolean.

### Pattern 3: target by skill cluster

```
("Product Manager" OR "Senior Product Manager")
AND ("Figma" OR "Linear" OR "Notion")
AND ("Series A" OR "Series B")
```

Use when: skill or tool footprint is a stronger persona signal than role title (common for technical roles).

### Pattern 4: target by current-pain language

Pain phrases rarely appear in profiles; they appear in posts. Run them as post searches (section "Public posts with a signal" above), not as profile booleans.

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

Use when: the target is users actively switching from a competitor. Better as a post search (`site:linkedin.com/posts "switched from HubSpot"`, HN, X) than as a profile boolean.

---

## How these patterns are used

1. The agent runs the post searches and keeps only dated posts with a signal (Step 2).
2. It may hand 3 to 5 booleans to the founder for their own session. Profiles the founder finds this way go through the same path: find one of their own dated posts, or they stay out.

---

## Anti-patterns to refuse

- **Building a 30-operator boolean**. Past ~15 operators LinkedIn silently truncates. Split into two narrower searches instead.
- **Lowercase operators**. `and`, `or`, `not` are treated as keywords. Always uppercase.
- **Quoted variable phrases**. `"head of growth"` is fine; `"head of growth at"` (with at) is too rigid. Drop trailing prepositions.
- **Stacking many NOT terms**. Diminishing returns past 3-4 NOTs. Prefer narrower positive matches.
- **Treating a profile as a signal**. A title says who someone is, not that they need anything now. The deliverable is people with a dated signal.

---

## Source

Boolean conventions adapted from LinkedIn Sales Navigator help docs (2025-2026), Recruiter community boolean libraries, and Boolean Black Belt patterns. Persona patterns calibrated for founder-targeted B2B SaaS use cases.
