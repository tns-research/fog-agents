# LinkedIn and X posts without scraping a profile

Profile pages (`linkedin.com/in/...`, `linkedin.com/company/...`) sit behind a login wall, and LinkedIn's user agreement forbids scraping them (https://www.linkedin.com/legal/user-agreement, section 8.2). `scripts/cache_page.py` refuses them. Public posts are another matter: a post URL is public, search engines index many of them, and the URL itself carries two facts a dossier needs.

## Finding posts

Use the `web_search` capability with the person's name on the posts path, for example `site:linkedin.com/posts "<first name> <last name>"`, or with a topic. Search engines index only part of LinkedIn posts: finding none proves nothing about the person's activity, it only means there is no post to open on.

## The date is in the id

A post URL holds an activity id: `.../posts/<slug>_<words>-activity-<id>-<suffix>`, also `urn:li:activity:<id>`, `ugcPost-<id>` and `share-<id>`. The first 41 of its 64 bits are a Unix time in milliseconds:

```text
created_at = (id >> 22) / 1000   (seconds since 1970-01-01 UTC)
```

X (Twitter) status ids follow the same layout with another epoch: `((id >> 22) + 1288834974657) / 1000`.

`li_activity_date()` and `x_status_date()` in `scripts/outreach_lib.py` implement both. `verify_dossiers.py` uses them: a fact of type `post`, or dated with `date_source: post_id`, must match the id within one day. The date never depends on a search snippet, which is often missing or approximate.

## The owner is in the slug

The segment between `/posts/` and the first `_` is the public slug of the author, the same as in `linkedin.com/in/<slug>`. When a fact says `owner: self`, `verify_dossiers.py` compares that slug with the prospect's `linkedin_url`: this rejects homonyms and posts where the person is only tagged or mentioned.

## Reading the post

Fetch the post URL (it renders a public page for many posts) or store its text from another provider with `cache_page.py --from-file`. When the page needs a login, the post cannot be cited: keep only what another public page shows.
