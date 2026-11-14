"""The adapter interface.

An adapter turns one approved queue item (one post on one network) into a
provider request. Three methods:

  build_payload(item, ctx) -> dict   pure, no network: what would be sent
  schedule(item, payload, ctx) -> {"post_id": str | None, "status": "scheduled" | "published"}
  status(item, ctx) -> "scheduled" | "published" | "failed" | None (unknown)

ctx holds: queue_dir (Path), settings (dict), now (datetime), outbox (Path).

Rules every adapter follows:
  - keys come from the environment, never from the queue or the repo;
  - a missing key or no network raises ProviderUnavailable (pubqueue.py exits 4,
    the item stays approved);
  - a provider refusal raises ProviderError (the item goes to failed with the message);
  - every request carries an idempotency key, so a retry never posts twice;
  - URLs are https (plain http only for localhost, 127.0.0.1 or ::1), and a
    redirect to another host drops the Authorization header;
  - media files are read through common.media_file, which refuses any path
    outside the project folder;
  - with CONTENT_PUBLISHER_OFFLINE=1 in the environment, http() refuses to open a
    connection: the tests run with it.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import urlsplit

import common

LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1"}


class ProviderUnavailable(Exception):
    """No key, no network, offline mode, or unknown adapter."""


class ProviderError(Exception):
    """The provider answered with an error."""


def offline() -> bool:
    return os.environ.get("CONTENT_PUBLISHER_OFFLINE", "") not in ("", "0", "false")


def url_problem(url: str) -> Optional[str]:
    """None for an https URL (or plain http to this machine), else why it is refused:
    a key sent over plain http to another host travels in clear text."""
    try:
        parts = urlsplit(url or "")
    except ValueError:
        return f"invalid URL {url!r}"
    if not parts.hostname:
        return f"invalid URL {url!r}: no host"
    if parts.scheme == "https":
        return None
    if parts.scheme == "http" and parts.hostname in LOCAL_HOSTS:
        return None
    return f"{parts.scheme or 'no'}:// URL refused for {parts.hostname}: use https (plain http only to localhost)"


class SafeRedirect(urllib.request.HTTPRedirectHandler):
    """Follow a redirect, but drop the Authorization header when it leaves
    the original scheme, host and port (urllib keeps it by default)."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):  # type: ignore[override]
        new = super().redirect_request(req, fp, code, msg, headers, newurl)
        if new is not None:
            old, nxt = urlsplit(req.full_url), urlsplit(new.full_url)
            if (old.scheme, old.hostname, old.port) != (nxt.scheme, nxt.hostname, nxt.port) or url_problem(new.full_url):
                new.remove_header("Authorization")
        return new


_OPENER = urllib.request.build_opener(SafeRedirect)


def http(method: str, url: str, headers: Optional[Dict[str, str]] = None, body: Any = None,
         raw: Optional[bytes] = None, timeout: int = 60) -> Any:
    """JSON over HTTPS with the standard library. Raises ProviderUnavailable
    on a refused URL, offline or on a connection error, ProviderError on an
    HTTP error."""
    bad = url_problem(url)
    if bad:
        raise ProviderUnavailable(bad)
    if offline():
        raise ProviderUnavailable(f"offline mode (CONTENT_PUBLISHER_OFFLINE): no request to {url.split('?')[0]}")
    data = raw if raw is not None else (json.dumps(body).encode("utf-8") if body is not None else None)
    hdrs = {"Accept": "application/json", **(headers or {})}
    if body is not None and raw is None:
        hdrs.setdefault("Content-Type", "application/json")
    req = urllib.request.Request(url, data=data, method=method, headers=hdrs)
    try:
        with _OPENER.open(req, timeout=timeout) as r:
            content = r.read()
    except urllib.error.HTTPError as e:
        detail = e.read()[:300].decode("utf-8", "replace")
        raise ProviderError(f"{method} {url.split('?')[0]} -> {e.code}: {detail}")
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        raise ProviderUnavailable(f"{method} {url.split('?')[0]}: {e}")
    if not content:
        return {}
    try:
        return json.loads(content)
    except ValueError:
        return {"raw": content[:300].decode("utf-8", "replace")}


def neutral_payload(item: Dict[str, Any], ctx: Dict[str, Any]) -> Dict[str, Any]:
    """Provider-independent description of one post: the shape the dry-run
    outbox, the command adapter and the webhook adapter use."""
    queue_dir: Path = ctx["queue_dir"]
    return {
        "id": item["id"],
        "network": item["network"],
        "text": item["text"],
        "first_comment": item.get("first_comment"),
        "reply": item.get("reply"),
        "link": item.get("link"),
        "media": [{"path": str(common.media_file(queue_dir, m["path"])), "type": m["type"], "alt": m.get("alt", ""),
                   "title": m.get("title", "")} for m in item.get("media") or []],
        "scheduled_for": item["slot"],
        "timezone": ctx["settings"]["timezone"],
        "idempotency_key": idempotency_key(item),
    }


def idempotency_key(item: Dict[str, Any]) -> str:
    return f"content-publisher-{item['id']}-{item['content_hash'][:12]}-{item['slot']}"


class Adapter:
    name = "base"
    env: tuple = ()           # environment variables the adapter reads
    real = True               # False only for dry-run: real adapters need --live

    def urls(self) -> List[str]:
        """Endpoints the adapter sends its key or the posts to (checked by available())."""
        return []

    def available(self) -> Optional[str]:
        """None when usable, else the one-line reason it is not."""
        missing = [v for v in self.env if not os.environ.get(v)]
        if missing:
            return f"{self.name}: set {', '.join(missing)} in the environment"
        for u in self.urls():
            bad = url_problem(u)
            if bad:
                return f"{self.name}: {bad}"
        if offline():
            return f"{self.name}: offline mode (CONTENT_PUBLISHER_OFFLINE)"
        return None

    def build_payload(self, item: Dict[str, Any], ctx: Dict[str, Any]) -> Dict[str, Any]:
        return neutral_payload(item, ctx)

    def schedule(self, item: Dict[str, Any], payload: Dict[str, Any], ctx: Dict[str, Any]) -> Dict[str, Any]:
        raise NotImplementedError

    def status(self, item: Dict[str, Any], ctx: Dict[str, Any]) -> Optional[str]:
        return None
