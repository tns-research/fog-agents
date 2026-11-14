#!/usr/bin/env python3
"""
collectors/registry_fr.py: French company creations, recherche-entreprises.api.gouv.fr.

Free public API of the French administration (Sirene and RNE data), no key.
It has no creation-date filter and sorts by relevance: the collector queries
by text, activity section and place, reads up to "pages" pages (5 at most),
then keeps companies created inside the trigger window and still active
(filter on the client side). Narrow queries (a postcode, an activity code)
find recent creations; a broad word often returns none in the window. One `trigger` signal per natural-person
director: name and role only. Birth date, nationality and address fields of
the API are never read or stored.

A registry row says a company exists, nothing about its product or its need.
It never qualifies a person alone in practice: the person has no handle, so
the activity check finds nothing until the model finds their own public posts
(manual-signals.csv, activity-manual.csv) and merges the identities.

Config block (config.json > sources.registry_fr):
  {"enabled": true,
   "queries": [{"id": "fr_software_paris", "q": "logiciel", "section_activite_principale": "J",
                "departement": "75", "per_page": 25, "pages": 3}]}

Health tested 2026-10-12: /search 200, fields date_creation and dirigeants present.
Exit codes: 0 ok, 1 the source failed, 2 usage error.
"""

from __future__ import annotations

import os
import re
import sys
from datetime import timedelta
from typing import Any, Dict, List

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from collectors.common import day_of, run_cli, signal  # noqa: E402

NAME = "registry_fr"
ACTIVITY_NETWORKS: List[str] = []
SEARCH = "https://recherche-entreprises.api.gouv.fr/search"
PAGE_URL = "https://annuaire-entreprises.data.gouv.fr/entreprise/{}"
MAX_PAGES = 5  # the API is rate limited per IP: a few pages per query is enough
PARAMS = ("q", "section_activite_principale", "activite_principale", "departement", "code_postal",
          "region", "categorie_entreprise", "nature_juridique", "tranche_effectif_salarie")

EXAMPLE_CONFIG = {
    "enabled": True,
    "queries": [{"id": "fr_software_paris", "q": "logiciel", "section_activite_principale": "J",
                 "departement": "75", "per_page": 25}],
}


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", (text or "").lower()).strip("-")


def collect_signals(cfg: Dict[str, Any], fetch, today, criteria) -> List[Dict[str, Any]]:
    since = (today - timedelta(days=criteria["signal_types"]["trigger"]["max_age_days"])).isoformat()
    out: List[Dict[str, Any]] = []
    for q in cfg.get("queries") or []:
        results: List[Dict[str, Any]] = []
        for page in range(1, min(int(q.get("pages", 1)), MAX_PAGES) + 1):
            params = {k: q[k] for k in PARAMS if q.get(k)}
            params.update({"per_page": int(q.get("per_page", 25)), "page": page, "etat_administratif": "A"})
            data = fetch.json("GET", SEARCH, params=params)
            results += data.get("results") or []
            if page >= int(data.get("total_pages") or 1):
                break
        for co in results:
            created = day_of(co.get("date_creation"))
            if not created or created < since or co.get("etat_administratif") not in (None, "A"):
                continue
            siren = co.get("siren") or ""
            name = co.get("nom_complet") or co.get("nom_raison_sociale") or siren
            naf = co.get("activite_principale") or ""
            for d in co.get("dirigeants") or []:
                if d.get("type_dirigeant") != "personne physique":
                    continue
                person = " ".join(x for x in [(d.get("prenoms") or "").split(" ")[0].title(),
                                              (d.get("nom") or "").title()] if x)
                if not person:
                    continue
                role = d.get("qualite") or ""
                text = (f"{name} (SIREN {siren}), created {created}, activity code {naf}. "
                        f"Director: {person}, {role}.")
                out.append(signal(
                    NAME, "registry_fr", f"{siren}:{_slug(person)}", "", PAGE_URL.format(siren), created,
                    "registry", text, criteria, signal_type="trigger", authored=False, author_name=person,
                    role=role, company=name, community="French company registry", query_id=q.get("id", ""),
                    title=f"Company created: {name}",
                ))
    return out


if __name__ == "__main__":
    sys.exit(run_cli(sys.modules[__name__], sys.argv[1:], __doc__))
