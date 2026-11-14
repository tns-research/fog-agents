# Regression fixture: the 2026-04-28 test run

The five LinkedIn messages of the April test run of cold-outreach-builder (French, `channel: linkedin`), rendered for one prospect and laid out as a `sequence-export.csv`. The model's own review shipped them as clean; `lint_outreach.py` must block them.

Anonymized: the prospect is fictional (name, company, LinkedIn slug), the sender's real first name is replaced by a fictional one, the equity figure of the original offer line is removed, the names of third-party programs are replaced by a generic phrase, and the cohort size, the open seats and the workshop name are replaced by fictional values. Everything else (wording, punctuation, the unfilled `{{link}}`, the missing source for the observation) is as the run wrote it.

The original dashes are stored as the escape text backslash, u, 2014 (six ASCII characters) because the repo forbids the dash itself; `tests/run_tests.py` turns them back into dashes before linting.

Expected (checked by `tests/run_tests.py`): exit 1, at least 5 BLOCK, among them `em-dash` (6), `unsourced-number`, `unfilled-variable`, `no-sourced-fact`, `too-long-chars`, `disclaimer-pitch` and `fausse-rarete`.
