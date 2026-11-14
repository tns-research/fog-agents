"""zernio: schedule through the Zernio API (https://docs.zernio.com), optional.

Environment:
  ZERNIO_API_KEY             required, Bearer key
  ZERNIO_ACCOUNT_<NETWORK>   account id per network (ZERNIO_ACCOUNT_LINKEDIN,
                             ZERNIO_ACCOUNT_X, ZERNIO_ACCOUNT_INSTAGRAM, ...).
                             When unset, GET /accounts is read and the one
                             account of that platform is used; with several,
                             the adapter stops and asks for the variable.
  ZERNIO_BASE_URL            default https://zernio.com/api/v1 (https only;
                             plain http only to localhost)

One queue item becomes one Zernio post with one platform entry:
  - LinkedIn: customContent = body, platformSpecificData.firstComment = the
    first comment (the link), documentTitle when the media is a PDF;
  - X, Threads, Bluesky with a link: platformSpecificData.threadItems = [body
    with media, reply with the link] (two posts at most, never a longer thread);
  - Instagram: the caption only (the link is in the bio).
Media are uploaded at send time (POST /media/presign, then PUT); in the
payload built offline they show as "upload:<path>" placeholders.
Field names follow https://docs.zernio.com/guides/platform-settings; check
them there when Zernio changes its API.
"""

from __future__ import annotations

import mimetypes
import os
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional

import common

from .base import Adapter, ProviderError, ProviderUnavailable, http, idempotency_key, offline, url_problem

PLATFORM = {"linkedin": "linkedin", "x": "twitter", "instagram": "instagram", "threads": "threads", "bluesky": "bluesky"}
STATUS = {"published": "published", "failed": "failed", "error": "failed", "partial": "failed",
          "scheduled": "scheduled", "pending": "scheduled", "publishing": "scheduled", "draft": "scheduled"}


class ZernioAdapter(Adapter):
    name = "zernio"
    env = ("ZERNIO_API_KEY",)

    def base(self) -> str:
        return os.environ.get("ZERNIO_BASE_URL", "https://zernio.com/api/v1").rstrip("/")

    def urls(self) -> List[str]:
        return [self.base()]

    def _headers(self, extra: Optional[Dict[str, str]] = None) -> Dict[str, str]:
        return {"Authorization": f"Bearer {os.environ['ZERNIO_API_KEY']}", **(extra or {})}

    # -------------------------------------------------------------- payload (offline)
    def build_payload(self, item: Dict[str, Any], ctx: Dict[str, Any]) -> Dict[str, Any]:
        net = item["network"]
        media = [{"type": m["type"], "url": f"upload:{m['path']}"} for m in item.get("media") or []]
        entry: Dict[str, Any] = {
            "platform": PLATFORM[net],
            "accountId": os.environ.get(f"ZERNIO_ACCOUNT_{net.upper()}") or f"<ZERNIO_ACCOUNT_{net.upper()}>",
            "customContent": item["text"],
        }
        psd: Dict[str, Any] = {}
        if net == "linkedin":
            if item.get("first_comment"):
                psd["firstComment"] = item["first_comment"]
            doc = next((m for m in item.get("media") or [] if m["type"] == "document"), None)
            if doc:
                psd["documentTitle"] = doc.get("title") or item["id"].split(".")[0]
        elif net in ("x", "threads", "bluesky") and item.get("reply"):
            first: Dict[str, Any] = {"content": item["text"]}
            if media:
                first["mediaItems"] = media
            psd["threadItems"] = [first, {"content": item["reply"]}]
        if psd:
            entry["platformSpecificData"] = psd
        return {
            "content": item["text"],
            "mediaItems": media,
            "platforms": [entry],
            "scheduledFor": f"{item['slot']}:00",
            "timezone": ctx["settings"]["timezone"],
        }

    # -------------------------------------------------------------- network
    def _account(self, net: str) -> str:
        env = os.environ.get(f"ZERNIO_ACCOUNT_{net.upper()}")
        if env:
            return env
        accounts = http("GET", f"{self.base()}/accounts", headers=self._headers()).get("accounts", [])
        found = [a.get("_id") for a in accounts if a.get("platform") == PLATFORM[net]]
        if len(found) == 1:
            return found[0]
        if not found:
            raise ProviderError(f"no {PLATFORM[net]} account connected on Zernio")
        raise ProviderUnavailable(f"{len(found)} {PLATFORM[net]} accounts on Zernio: set ZERNIO_ACCOUNT_{net.upper()}")

    def _upload(self, path: Path, item_id: str) -> str:
        ctype = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        pre = http("POST", f"{self.base()}/media/presign", headers=self._headers(),
                   body={"filename": f"{item_id}-{path.name}", "contentType": ctype})
        if offline():
            raise ProviderUnavailable("offline mode")
        bad = url_problem(pre.get("uploadUrl") or "")
        if bad:
            raise ProviderError(f"upload {path.name}: {bad}")
        req = urllib.request.Request(pre["uploadUrl"], data=path.read_bytes(), method="PUT", headers={"Content-Type": ctype})
        try:
            with urllib.request.urlopen(req, timeout=300):
                pass
        except Exception as e:  # noqa: BLE001
            raise ProviderError(f"upload {path.name}: {e}")
        return pre["publicUrl"]

    def schedule(self, item: Dict[str, Any], payload: Dict[str, Any], ctx: Dict[str, Any]) -> Dict[str, Any]:
        body = payload
        urls: List[Dict[str, Any]] = []
        for m in item.get("media") or []:
            urls.append({"type": m["type"], "url": self._upload(common.media_file(ctx["queue_dir"], m["path"]), item["id"])})
        body["mediaItems"] = urls
        entry = body["platforms"][0]
        entry["accountId"] = self._account(item["network"])
        for t in (entry.get("platformSpecificData") or {}).get("threadItems", [])[:1]:
            if urls:
                t["mediaItems"] = urls
        res = http("POST", f"{self.base()}/posts", headers=self._headers({"Idempotency-Key": idempotency_key(item)}), body=body)
        post = res.get("post") or {}
        return {"post_id": post.get("_id"), "status": STATUS.get(post.get("status", "scheduled"), "scheduled")}

    def status(self, item: Dict[str, Any], ctx: Dict[str, Any]) -> Optional[str]:
        pid = (item.get("provider") or {}).get("post_id")
        if not pid:
            return None
        res = http("GET", f"{self.base()}/posts/{pid}", headers=self._headers())
        return STATUS.get(((res.get("post") or res).get("status") or ""), None)
