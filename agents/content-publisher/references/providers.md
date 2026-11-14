# Publishing providers

content-publisher talks to providers through one interface (`scripts/adapters/base.py`). Each adapter gets one approved item (one post on one network) and returns a provider post id. Keys come from the environment, never from `queue.json`, `config.json` or the repo. Every URL that receives a key is https (plain http is accepted only for localhost, 127.0.0.1 and ::1), and a redirect to another host drops the `Authorization` header. Media paths resolve inside the project folder or the item is refused. The founder picks the provider; none is required.

## The provider-independent payload

What `dry-run` writes in `outbox/<id>.json` (`would_send`), what `command` receives on stdin and what `webhook` POSTs:

```json
{
  "id": "pitch-deck-order.x",
  "network": "x",
  "text": "the body, no URL",
  "first_comment": null,
  "reply": "The full pitch deck guide: https://...",
  "link": "https://...",
  "media": [{ "path": "/abs/path/slide-01.jpg", "type": "image", "alt": "...", "title": "" }],
  "scheduled_for": "2026-10-20T09:00",
  "timezone": "Europe/Paris",
  "idempotency_key": "content-publisher-pitch-deck-order.x-<hash>-2026-10-20T09:00"
}
```

- `first_comment` is set on LinkedIn only; `reply` on X, Threads and Bluesky when the post has a link. Instagram gets neither: its caption points to the bio.
- The receiver must post the reply (or comment) right after the post, as a reply to it, and never more than these two posts.
- Same `idempotency_key` twice means the same post: the receiver must not post it again.

## Shipped adapters

### dry-run (default)

Sends nothing. Writes the payload above plus `zernio_view`, the request the Zernio adapter would build. Use it to read what will go out, to post by hand (then `pubqueue.py mark <id> --published`), and in tests.

### zernio

API documentation: https://docs.zernio.com (platform fields: https://docs.zernio.com/guides/platform-settings).

| Variable | Use |
|----------|-----|
| `ZERNIO_API_KEY` | Bearer key, required |
| `ZERNIO_ACCOUNT_LINKEDIN`, `ZERNIO_ACCOUNT_X`, `ZERNIO_ACCOUNT_INSTAGRAM`, `ZERNIO_ACCOUNT_THREADS`, `ZERNIO_ACCOUNT_BLUESKY` | account id per network; without it the adapter reads `GET /accounts` and uses the single account of that platform, and stops when there are several |
| `ZERNIO_BASE_URL` | default `https://zernio.com/api/v1`; https only (plain http only to localhost) |

Request per item: `POST /posts` with `content`, `mediaItems` (uploaded first through `POST /media/presign` then `PUT`), one `platforms` entry (`platform`: `linkedin`, `twitter`, `instagram`, `threads`, `bluesky`; `accountId`; `customContent`), `scheduledFor` and `timezone`, header `Idempotency-Key`.

- LinkedIn: `platformSpecificData.firstComment` holds the link; a PDF adds `documentTitle`.
- X, Threads, Bluesky with a link: `platformSpecificData.threadItems` = `[{content: body, mediaItems}, {content: reply}]`, two items, never more.
- Instagram: no `platformSpecificData`.

Status: `GET /posts/<id>`, `published` and `failed` mapped, everything else stays `scheduled`. X bills API calls to the account owner through Zernio (see Zernio's pricing page): every X post has a cost there.

### command

`CONTENT_PUBLISHER_COMMAND="python3 /path/to/my_publisher.py"`. The program reads the payload as JSON on stdin and prints `{"post_id": "...", "status": "scheduled"}` (or `"published"`). Exit code other than 0 is a provider error, stderr is the message. For `sync`, it receives `{"action": "status", "id": ..., "post_id": ...}` and prints `{"status": "scheduled" | "published" | "failed"}`. Local, no network needed by the adapter itself.

### webhook

`CONTENT_PUBLISHER_WEBHOOK_URL`, https only (plain http only to localhost), and optional `CONTENT_PUBLISHER_WEBHOOK_TOKEN`, sent as Bearer. POSTs the payload; an answer `{"post_id": ...}` is recorded. Media paths are local: the receiving flow runs on the same machine or the founder hosts the files. No status check: `mark` records the outcome.

## Routes through `command` (not shipped as adapters)

These services work through a small program behind `CONTENT_PUBLISHER_COMMAND` that maps the payload above to their API. Read their current documentation before writing it; this repo does not test them.

| Provider | Documentation | Mapping notes |
|----------|---------------|---------------|
| Buffer | https://buffer.com/developers/api | one update per channel; first comment where the channel supports it, otherwise post the reply yourself |
| Typefully | https://typefully.com/docs/api | drafts and scheduling for X, LinkedIn, Threads, Bluesky; send the reply as the second post of a two-post draft |
| LinkedIn Posts API | https://learn.microsoft.com/en-us/linkedin/marketing/community-management/shares/posts-api | post, then the first comment through the comments API on the returned post URN |
| X API v2 | https://docs.x.com/x-api/posts/creation-of-a-post | post, then a reply with `reply.in_reply_to_tweet_id` |
| Instagram Graph API | https://developers.facebook.com/docs/instagram-platform/content-publishing | media container per image, carousel container, publish; caption only |
| Threads API | https://developers.facebook.com/docs/threads/posts | post, then a reply with `reply_to_id` |
| Bluesky (AT Protocol) | https://docs.bsky.app/docs/advanced-guides/posts | `app.bsky.feed.post` record, the reply with `reply.root` and `reply.parent` |

A route used often enough deserves its own adapter: a file in `scripts/adapters/`, a class with `build_payload`, `schedule` and `status`, registered in `adapters/__init__.py`, a payload test in `selftest.py` that runs offline, and a row in the table of `scripts/README.md`.
