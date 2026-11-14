"""Collectors of first-users-hunter: one module per free source, same contract
(see common.py). collect.py runs them; each also runs alone with --help."""

COLLECTORS = ["hn", "github", "reddit", "luma", "notion", "folk", "registry_fr", "manual"]

# Network of a handle -> collector that can check its activity.
ACTIVITY_COLLECTOR = {
    "hn": "hn",
    "github": "github",
    "reddit": "reddit",
    "linkedin": "manual",
    "x": "manual",
    "community": "manual",
}
