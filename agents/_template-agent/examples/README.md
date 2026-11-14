# examples/

Optional fictional or anonymized runs of this agent. Single biggest reduction in LLM hallucination about output format.

| Example | What it shows | Command |
|---------|---------------|---------|
| `<project>-<label>-<YYYYMMDD>/` | the inputs of the run and the deliverable it produces | how to rebuild it |

## Conventions

- One folder per run, `<project>-<label>-<YYYYMMDD>/`, holding its inputs and its deliverable, or a single file `<agent-name>-example-<context-shortname>-<YYYYMMDD>.md`.
- Contents: a complete output that matches `assets/output-template.md` exactly.
- Anonymization rules:
  - No founder / customer / company names. Use placeholders like `Acme SaaS`, `Founder A`, `Customer #1`.
  - No URLs to specific real properties (use `https://example.com`).
  - E-mail addresses only on reserved test domains (`example.com`, `example.org`, `example.net`, the `.example`, `.test` and `.invalid` TLDs), and the slug of a LinkedIn `/in/` profile URL says "fictive", "fictional" or "example": `scripts/validate_stack.py` refuses anything else in `examples/`, `tests/fixtures/` and `scripts/fixtures/`.
  - Real linguistic patterns and structural shape preserved (the example is for format reference, not a marketing showcase).
- One example per common scenario the agent serves (e.g. one EN B2B SaaS run, one FR creator-economy run for `cold-outreach-builder`).

If anonymizing a real run is too heavy, write synthetic-but-realistic data from scratch.
