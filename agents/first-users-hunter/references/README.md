# References

## Free sources and their endpoints

Every collector is a local script on a free endpoint; details, health and keys in `skills/collecting-signals/SKILL.md`. Other providers per capability: [`shared/tools.md`](../../../shared/tools.md).

| Source | Endpoint | Docs |
|--------|----------|------|
| Hacker News | `hn.algolia.com/api/v1/search_by_date`, `hacker-news.firebaseio.com/v0/user/<id>.json` | https://hn.algolia.com/api, https://github.com/HackerNews/API |
| GitHub | `api.github.com/search/issues`, `users/<u>/events/public`, GraphQL for discussions | https://docs.github.com/rest/search/search, https://docs.github.com/rest/activity/events |
| Reddit | OAuth `client_credentials`, `oauth.reddit.com` | https://github.com/reddit-archive/reddit/wiki/OAuth2 |
| Luma | public city and event pages (`__NEXT_DATA__`) | https://luma.com/discover |
| Notion and folk public lists | XHR endpoints | [`public-list-endpoints.md`](public-list-endpoints.md) |
| French company registry | `recherche-entreprises.api.gouv.fr/search` | https://recherche-entreprises.api.gouv.fr/docs/ |

Not used, because they fail from a server: anonymous Reddit JSON (403), read.cv (402, site closed), Discord channel URLs (login page).

## Dates from post ids

- LinkedIn: the first 41 bits of an activity, ugcPost or share id are a Unix time in milliseconds, `(id >> 22) / 1000`.
- X: status ids are snowflakes, `((id >> 22) + 1288834974657) / 1000`.

Both in `scripts/fuh_lib.py`, command line `scripts/date_from_url.py`.

## Inspiration

- **Paul Graham**: *Do Things That Don't Scale* (2013). Hand-recruit your first users one at a time.
- **Lenny Rachitsky**: early-stage acquisition playbook (2022). The first-100-users patterns of Notion, Superhuman, Figma.
- **Rob Walling**: *The Stairstep Approach*: start where your audience already is, don't invent a channel.

## Outreach principles (applied by `skills/drafting-first-touch/SKILL.md`)

1. **Answer what they said, where they said it.** Touch 1 is a reply in the signal's thread.
2. **No pitch in touch 1.** The offer is named only when the person asked for exactly it.
3. **Specific.** Reference something they actually wrote, with its URL in the file.
4. **One small ask, in touch 2 at most.**
5. **Network length.** X replies 280 characters, LinkedIn connection notes 200.
