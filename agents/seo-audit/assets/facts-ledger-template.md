# Facts ledger: <project>

The only source a writer may use for a fact, a number, a name or a date in a brief, a new article or a refresh. One row per fact. A fact without a URL and an access date is not admissible. The published article is the source of truth for its own worked examples: a refresh changes one of them only with a newer row here.

| ID | Fact (as it may be written) | Value | Source URL | Accessed | Used in |
|----|-----------------------------|-------|------------|----------|---------|
| F01 | <fact> | <value> | <https://...> | YYYY-MM-DD | <brief id or article URL> |

## Rules

- Product proof (customers, metrics, awards) comes from `positioning.proof` in `project-context/context.json` or from a source URL, never from a competitor page or a SERP snippet.
- A number older than the source recency cutoff of the topic is flagged in the "Fact" column ("2023 figure").
- A row removed or replaced keeps its ID with "superseded by F07" in the Fact column, so briefs that cite it can be found.
