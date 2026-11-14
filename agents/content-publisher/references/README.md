# references/

| File | Read by | What it holds |
|------|---------|---------------|
| [`providers.md`](providers.md) | approving-and-scheduling, contributors adding an adapter | Every publishing route: the shipped adapters, their environment and payload, and the documented routes for Buffer, Typefully and native APIs through the `command` adapter |

Platform limits live in [`../assets/platform-limits.json`](../assets/platform-limits.json), each with its source URL and check date: `scripts/variants.py` reads them. When a platform's help page disagrees with the file, the help page wins: update the number, its URL and `checked`.

## Sources behind the rules

- X weighted count, 280 per post, URLs counted 23, emoji 2: https://docs.x.com/fundamentals/counting-characters
- X, four photos per post: https://help.x.com/en/using-x/posting-gifs-and-pictures
- Character limits of LinkedIn (post 3000, first comment 1250), Instagram (2200), Threads (500, counted by the API in UTF-8 bytes), Bluesky (300): https://support.buffer.com/articles/character-limits-for-each-social-network-mNDqsEV9Nf
- Instagram, five hashtags per post or reel (Instagram's @creators account, December 2025): https://www.instagram.com/p/DSalTolEbvf/
- Text shown before "see more": LinkedIn about 210 characters on desktop (https://contentin.io/glossary/character-limit), Instagram about 125 (https://charactercounter.com/instagram). Warnings only.

## Prior art

- The approval-before-scheduling queue, one text per network, links moved out of the body and the spacing of posts per network are a generic transposition of a production queue run by the stack's maintainers for the example brand. Nothing of its content, accounts or media is in this repo.
