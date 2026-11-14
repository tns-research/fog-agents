"""dry-run: the default adapter. Sends nothing.

schedule() writes <outbox>/<item id>.json with the exact provider-independent
payload that would be sent, and the Zernio payload as a second view, so the
founder can read what each network will receive. status() reports an item as
published once its slot has passed: a simulation, said so in the history.
"""

from __future__ import annotations

import json
from typing import Any, Dict, Optional

from .base import Adapter
from .zernio import ZernioAdapter


class DryRunAdapter(Adapter):
    name = "dry-run"
    env = ()
    real = False

    def available(self) -> Optional[str]:
        return None

    def schedule(self, item: Dict[str, Any], payload: Dict[str, Any], ctx: Dict[str, Any]) -> Dict[str, Any]:
        outbox = ctx["outbox"]
        outbox.mkdir(parents=True, exist_ok=True)
        doc = {
            "adapter": self.name,
            "note": "dry run: nothing was sent. 'would_send' is the provider-independent payload; "
                    "'zernio_view' is the request the zernio adapter would build from it.",
            "would_send": payload,
            "zernio_view": ZernioAdapter().build_payload(item, ctx),
        }
        path = outbox / f"{item['id']}.json"
        path.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return {"post_id": f"dry-{item['content_hash'][:10]}", "status": "scheduled"}

    def status(self, item: Dict[str, Any], ctx: Dict[str, Any]) -> Optional[str]:
        from datetime import datetime
        slot = datetime.strptime(item["slot"], "%Y-%m-%dT%H:%M")
        return "published" if slot <= ctx["now"] else "scheduled"
