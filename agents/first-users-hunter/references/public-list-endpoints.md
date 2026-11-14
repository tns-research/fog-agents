# Reading public Notion and folk lists without a key

Many community directories (accelerator alumni, founder lists, "who is hiring" boards, investor lists) are published as a Notion page or a shared folk view. Both render in the browser from XHR calls: a scrape tool or `curl` on the page URL returns an empty shell. The same calls work without a session. Implemented in `scripts/collectors/notion.py` and `scripts/collectors/folk.py`; this page explains them so another tool can do the same.

A list is a **seed**: a row says the person belongs somewhere, not that they need anything now. Each row becomes a `listed` record, which never qualifies a person alone (see `skills/collecting-signals/SKILL.md`).

## Notion (`<space>.notion.site`)

1. Page id and view id: the page URL ends with a 32-hex id (the page); a database view adds `?v=<32-hex>` (the view). Both are UUIDs once dashes are added (8-4-4-4-12).
2. `POST https://<space>.notion.site/api/v3/loadPageChunk` with:

   ```json
   {"pageId": "<page uuid>", "limit": 100, "cursor": {"stack": []}, "chunkNumber": 0, "verticalColumns": false}
   ```

   In `recordMap.block[<page uuid>]`, the value (sometimes nested as `value.value`) holds `collection_id`. In `recordMap.collection[<collection id>]`, `schema` maps short column keys to `{"name", "type"}`.
3. `POST https://<space>.notion.site/api/v3/queryCollection` with:

   ```json
   {"collection": {"id": "<collection id>"}, "collectionView": {"id": "<view uuid>"},
    "loader": {"type": "reducer", "reducers": {"collection_group_results": {"type": "results", "limit": 1000}},
               "searchQuery": "", "userTimeZone": "UTC"}}
   ```

   Row ids are in `result.reducerResults.collection_group_results.blockIds`; each row is a block of `recordMap.block` with `properties`, keyed by the short column keys. A text value is a list of segments (`[["text"]]`); a date is a segment annotated `["d", {"start_date": "YYYY-MM-DD"}]`.
4. A row's own page: `https://<space>.notion.site/<row id without dashes>`.

Config: `sources.notion.lists[]` with `site`, `page_id`, `view_id` and the column names to read (`name`, `linkedin`, `x`, `role`, `company`, `text`, `date`).

## folk shared views (`app.folk.app/shared/...`)

`POST https://gateway.folk.app/networks/graphql`, no authentication:

```graphql
query($id:String!,$offset:Int,$limit:Int){
  sharedViewContactList(id:$id,offset:$offset,limit:$limit){
    totalCount items{... on Person{fullname pJobTitle urls{value}}}}}
```

The `id` is the last segment of the shared view slug, not the whole slug. Page with `offset` and `limit` (100) until `totalCount`. The collector reads names, titles and the LinkedIn and X URLs; it does not read emails from lists.

## Limits

- Both endpoints are undocumented and may change; `source-health.json` records the failure and the run continues.
- Respect the list owner's intent: a list published for a community is read to find people's own public posts, never to bulk-message its rows.
