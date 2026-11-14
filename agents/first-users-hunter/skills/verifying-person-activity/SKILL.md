---
name: verifying-person-activity
description: Proves that a person publishes now before anyone writes to them. Groups handles of one person only on evidence, collects their own recent public posts (HN, GitHub and Reddit by API; LinkedIn and X from post URLs found by web search), dates LinkedIn and X posts from the ids in their URLs, rejects tagged posts and homonyms, detects handles that no longer exist, and applies a weighted gate of at least two own posts in the window. Use at Steps 3 and 4 of first-users-hunter, or alone to recheck one person. Triggers on "is this person active", "dead account", "date this LinkedIn post", "last post", "activity check".
license: Apache-2.0
compatibility: Claude Code, Cursor, Codex CLI, Gemini CLI
metadata:
  version: "2.0"
allowed-tools: Read Write Bash
---

# verifying-person-activity

A message sent to an abandoned account is lost, and it skews every experiment metric. This skill makes "this person posts now" a fact a script computed, with the URLs behind it.

## Identities: one person, several handles

`candidates.py` groups signals by `<network>:<handle>` and merges two handles only when a source publishes the link itself (a Luma host's LinkedIn and X handles, a list row's LinkedIn URL). For other links, write `<run>/identities.json`:

```json
{
  "merge": [["hn:qforge_fictive", "linkedin:alex-dupuis-fictive"]],
  "evidence": {"hn:qforge_fictive": "https://news.ycombinator.com/user?id=qforge_fictive (about links the LinkedIn profile)"}
}
```

Evidence is a page that links the two handles (a profile "about", a personal site listing both, a post signed with both). A shared name is never evidence. The founder's own handles (`founder.handles`) and `exclude_handles` (organization accounts, competitors) are excluded.

## Collecting the posts

```bash
python3 scripts/collect.py activity --config <project>/first-users-hunter/config.json --run-dir <run>
```

| Network | How | Dead handle |
|---------|-----|-------------|
| `hn` | user API, then every story and comment by the author in the window (Algolia `tags=author_<user>`) | user API returns `null` |
| `github` | `users/<u>/events/public`: issues and pull requests opened, comments, discussions count 1; pushes 0.25; stars and forks 0 | 404 |
| `reddit` | OAuth `/user/<u>/overview` (needs the free app keys) | 404, or 403 for a suspended account |
| `linkedin`, `x` | `<run>/activity-manual.csv`: post URLs found with `site:linkedin.com/posts/<slug>` or `site:x.com/<handle>/status` | the founder reports "This account doesn't exist" in `notes` |
| `community` | rows the founder transcribed from screenshots (`date_source: founder`) | n/a |

For LinkedIn and X, list the person's own posts only: the slug after `/posts/` (LinkedIn) or the handle before `/status/` (X) must be theirs. A post where they are tagged, a repost by their company, or a homonym's post does not count; `check_activity.py` drops them anyway and says why. Replies on X are `reply` (0.25), reposts `repost` (0.25).

## Dates from ids

| Network | Formula | Where |
|---------|---------|-------|
| LinkedIn `activity-<id>`, `ugcPost-<id>`, `share-<id>`, `urn:li:activity:<id>` | Unix ms = `id >> 22` | `scripts/fuh_lib.py` `li_activity_datetime` |
| X `/status/<id>` | Unix ms = `(id >> 22) + 1288834974657` | `x_status_datetime` |
| HN, GitHub, Reddit | API fields `created_at_i`, `created_at`, `created_utc` | the collectors |

`python3 scripts/date_from_url.py <url> ...` prints date, time and owner. A date given by a CSV or a search snippet that disagrees with the id by more than `date_tolerance_days` is reported, and the id wins.

## The gate

```bash
python3 scripts/check_activity.py --run-dir <run> --config <project>/first-users-hunter/config.json
```

Rules in [`assets/criteria.json`](../../assets/criteria.json) > `activity`:

- Window: 30 days; 45 on LinkedIn, because search engines index a fraction of LinkedIn posts.
- Weighted posts: own post, comment, issue, discussion, event hosted 1; reply, repost, push 0.25. The person's own signal counts as one post. The same post reached twice (a signal and its API record) counts once.
- `active`: weighted total at least 2. `dead_handle`: every handle checked no longer exists (their posts no longer count). `not_proven`: anything else.
- `not_proven` is not "inactive": it means this run did not find the proof. The person leaves this run; nothing is sent to them. When the person matters, the founder can open their recent activity in their own browser and paste the post URLs into `activity-manual.csv`, then the check runs again.

## Done when

`<run>/activity.json` holds, per candidate: status, weighted posts, window, last active date, active networks, evidence URLs, ignored posts with the reason. Only `active` people reach `score_people.py`, and `verify_people.py` refuses any row whose activity differs from this file.

## Anti-patterns

- Writing "active" from a follower count, a profile headline or a job title.
- Counting a post where the person is tagged, or a homonym's post.
- Reading the date of a LinkedIn post from "2w" on the page or from a search snippet.
- Merging two handles because the names match.
- Retyping `weighted_posts` or `status` in the people file: copy them from the shortlist.
