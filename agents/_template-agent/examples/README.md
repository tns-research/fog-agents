# examples/

Optional anonymized real runs of this agent. Single biggest reduction in LLM hallucination about output format.

## Conventions

- Filename: `<agent-name>-example-<context-shortname>-<YYYYMMDD>.md`
- Contents: a complete output that matches `assets/output-template.md` exactly.
- Anonymization rules:
  - No founder / customer / company names. Use placeholders like `Acme SaaS`, `Founder A`, `Customer #1`.
  - No URLs to specific real properties (use `https://example.com`).
  - Real linguistic patterns and structural shape preserved (the example is for format reference, not a marketing showcase).
- One example per common scenario the agent serves (e.g. one EN B2B SaaS run, one FR creator-economy run for `cold-outreach-builder`).

If anonymizing a real run is too heavy, write synthetic-but-realistic data from scratch.
