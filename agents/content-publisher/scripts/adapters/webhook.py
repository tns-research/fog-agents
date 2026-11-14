"""webhook: POST each post to an automation URL (Make, n8n, Zapier, your server).

Set CONTENT_PUBLISHER_WEBHOOK_URL. The body is the provider-independent
payload (base.neutral_payload); media paths are local, so the receiving flow
must read the files from the same machine or the founder hosts them. Optional
CONTENT_PUBLISHER_WEBHOOK_TOKEN is sent as a Bearer token. The URL must be
https (plain http only to localhost). The response may
be JSON {"post_id": "...", "status": "scheduled"}. No status check: sync
leaves webhook items as scheduled until the founder marks them.
"""

from __future__ import annotations

import os
from typing import Any, Dict, List

from .base import Adapter, http


class WebhookAdapter(Adapter):
    name = "webhook"
    env = ("CONTENT_PUBLISHER_WEBHOOK_URL",)

    def urls(self) -> List[str]:
        return [os.environ.get("CONTENT_PUBLISHER_WEBHOOK_URL", "")]

    def schedule(self, item: Dict[str, Any], payload: Dict[str, Any], ctx: Dict[str, Any]) -> Dict[str, Any]:
        headers = {"Idempotency-Key": payload["idempotency_key"]}
        token = os.environ.get("CONTENT_PUBLISHER_WEBHOOK_TOKEN")
        if token:
            headers["Authorization"] = f"Bearer {token}"
        out = http("POST", os.environ["CONTENT_PUBLISHER_WEBHOOK_URL"], headers=headers, body=payload)
        out = out if isinstance(out, dict) else {}
        return {"post_id": out.get("post_id"), "status": out.get("status", "scheduled")}
