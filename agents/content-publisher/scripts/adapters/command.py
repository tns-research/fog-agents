"""command: hand each post to any program the founder already uses.

Set CONTENT_PUBLISHER_COMMAND to a command line. It receives the
provider-independent payload (base.neutral_payload) as JSON on stdin and
prints one JSON object on stdout: {"post_id": "...", "status": "scheduled"}.
Exit 0 means accepted; any other exit code is a provider error with stderr as
the message. This is the route for Buffer, Typefully, a native API script or a
shell wrapper (see references/providers.md). The status check calls the same
command with {"action": "status", "id": ..., "post_id": ...} and reads
{"status": "scheduled" | "published" | "failed"}.
"""

from __future__ import annotations

import json
import os
import shlex
import subprocess
from typing import Any, Dict, Optional

from .base import Adapter, ProviderError, ProviderUnavailable


class CommandAdapter(Adapter):
    name = "command"
    env = ("CONTENT_PUBLISHER_COMMAND",)

    def available(self) -> Optional[str]:
        # A local command needs no network: offline mode does not block it.
        if not os.environ.get("CONTENT_PUBLISHER_COMMAND"):
            return "command: set CONTENT_PUBLISHER_COMMAND to the program that posts (JSON on stdin)"
        return None

    def _run(self, doc: Dict[str, Any]) -> Dict[str, Any]:
        cmd = shlex.split(os.environ["CONTENT_PUBLISHER_COMMAND"])
        try:
            r = subprocess.run(cmd, input=json.dumps(doc, ensure_ascii=False), capture_output=True, text=True, timeout=300)
        except FileNotFoundError:
            raise ProviderUnavailable(f"command not found: {cmd[0]}")
        if r.returncode != 0:
            raise ProviderError(f"command exited {r.returncode}: {(r.stderr or r.stdout).strip()[-300:]}")
        try:
            return json.loads(r.stdout or "{}")
        except ValueError:
            raise ProviderError(f"command printed no JSON: {r.stdout.strip()[:200]}")

    def schedule(self, item: Dict[str, Any], payload: Dict[str, Any], ctx: Dict[str, Any]) -> Dict[str, Any]:
        out = self._run(payload)
        return {"post_id": out.get("post_id"), "status": out.get("status", "scheduled")}

    def status(self, item: Dict[str, Any], ctx: Dict[str, Any]) -> Optional[str]:
        out = self._run({"action": "status", "id": item["id"], "post_id": (item.get("provider") or {}).get("post_id")})
        return out.get("status")
