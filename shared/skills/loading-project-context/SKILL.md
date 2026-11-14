---
name: loading-project-context
description: Loads the shared business context a founder wrote once with the project-context agent (context.json, optional brand.json) and prefills the calling agent's inputs from it, then asks the user only for the fields that are still missing, in one grouped message. Exposes the allowed claims (the positioning.proof items shared/scripts/proof.py finds usable for the agent's scope), voice.claims_policy and voice.banned_words to every copy step, and the people and partners registries (people.json, partners.json, read through shared/scripts/registry.py) to every agent that shows a face, a name or a logo. With the brand option it also reads brand.json (V2 contract, V1 files mapped on load) and exposes color roles, fonts, the logo variant for the background, the logo audit and the harvested assets to visual agents. Use at Step 0 of every agent of the stack except project-context, which writes these files. Triggers on "load my context", "use my project context", "use my brand", "you already know my product".
license: Apache-2.0
compatibility: Claude Code, Cursor, Codex CLI, Gemini CLI
metadata:
  version: "1.1"
allowed-tools: Read Bash(python3:*)
---

# loading-project-context

Read the shared context once so the founder never re-types what they already told the stack. This skill only reads. It never writes to `project-context/`.

**Golden rule:** shared context is an accelerator, never a hard gate. A missing or partial `project-context/` folder must never stop a run. It only means Step 0 asks a few more questions.

Visual agents (`static-ads-builder`, `carousel-builder`, `short-video-builder`) load it with the **`brand` option** (section [Option brand](#option-brand-brand-tokens-and-assets) below): same procedure, plus `brand.json`.

---

## When to load

Step 0 of every agent that links here, on every run, before any input question is asked.

---

## Procedure

### 1. Locate the folder

The shared folder is a sibling of the agent's own output folder, in the founder's project:

```
<your-projects-root>/<project-slug>/project-context/
├── context.json   # business context (the contract: agents/project-context/assets/context-schema.json)
├── context.md     # same facts, prose
├── brand.json     # colors, fonts, logo, harvested assets (visual agents only)
├── people.json    # people a deliverable may show or name, with consent (shared/schemas/people.schema.json)
└── partners.json  # companies whose name or logo may appear, with consent (shared/schemas/partners.schema.json)
```

Resolve `<your-projects-root>` and `<project-slug>` the way the calling agent already does (ask once if unknown, never hard-code a root). Never look inside the fog-agents repo for this folder.

### 2. Read `context.json` defensively

Every field is optional from the reader's point of view. A missing field means "ask or omit", never an error.

| Field | Meaning |
|-------|---------|
| `url` | Founder's primary site |
| `one_liner`, `what_it_is` | What the product is |
| `category` | Market category in buyer words |
| `geography.country` | Primary market country, ISO 3166-1 alpha-2 lowercase (`fr`, `us`), `null` when global |
| `geography.notes` | Free-text geo scope |
| `icp.who`, `icp.pains[]`, `icp.jobs[]` | Buyer, pains, jobs to be done |
| `offer.core`, `offer.price_model`, `offer.differentiators[]` | What is sold and why it wins |
| `positioning.against`, `positioning.promise` | Status quo displaced, promised outcome |
| `positioning.proof[]` | **Allowed claims.** The only product proof copy may use without a new source URL. Plain strings or objects with `kind`, `source`, `date`, `consent`: read them through `shared/scripts/proof.py`, never by hand-parsing |
| `voice.tone`, `voice.language` | Default tone and output language |
| `voice.banned_words[]` | Hard blacklist for all copy |
| `voice.claims_policy` | Anti-fabrication rule. Default when absent: "no invented stats, every metric must trace to a URL or be omitted" |

If `context.json` is unreadable but `context.md` exists, read the same facts from the prose and warn once.

### 3. Prefill the agent's inputs

Each calling agent lists, in its own Step 0, which of its inputs map to which context field. Apply this precedence, highest first:

1. A value the user gave in this conversation.
2. A value already in the agent's own `config.json`.
3. The mapped `project-context` field.
4. The agent's documented default.

Do not copy prefilled values into the agent's `config.json`. The agent config holds agent-specific settings and explicit overrides; `project-context` stays the single source for business facts, so a later edit there reaches every agent.

### 4. Show, then ask only for what is missing

Print one compact block before asking anything:

```
Loaded project-context (context.json).
Prefilled: market = <...>, language = <...>, geography = <...>
Still needed: <input_1>, <input_2>
```

Ask only for the inputs still unresolved, **in one message** together with every other Step 0 question of the calling agent (tools, config, brand). Each question states the default the agent will use without an answer, so an unattended run continues on documented defaults instead of waiting. The user can correct any prefilled value in the same answer.

### 5. Carry the copy rules forward

Every copy-writing step of the calling agent receives:

- `allowed_claims` = the items of `positioning.proof[]` that `usable(item, scope, today)` of [`../../scripts/proof.py`](../../scripts/proof.py) accepts, as `proof_text(item)` (possibly empty). `scope` is the agent's use: `ads` (static-ads-builder), `carousel` (carousel-builder), `posts` (founder-content-writer), `outreach` (cold-outreach-builder), `site` (landing pages), `video`. Keep the refused items with their reason: they go into the report (claims ledger, "Proof refused" line). A plain string is usable with a warning.
- `claims_policy` = `voice.claims_policy` or the default above.
- `banned_words` = `voice.banned_words[]` or an empty list.
- `tone`, `language`.

The rules for using them live in [`../enforcing-claims-policy/SKILL.md`](../enforcing-claims-policy/SKILL.md).

### 6. Report the path taken

One line in the chat and one line in the report's methodology section: "Loaded project-context (context.json)", "Partial project-context (missing: icp, voice)", or "No project-context found, inputs collected in chat". With the brand option, add the brand path: "brand.json V2", "brand.json V1 mapped to V2" or "no brand.json, inline brand answers".

Then read the project's decisions with [`../keeping-project-memory/SKILL.md`](../keeping-project-memory/SKILL.md) (Step 0 part).

---

## Registries: people and partners

For every agent that shows a face, names a person or shows a logo. Contracts: [`../../schemas/people.schema.json`](../../schemas/people.schema.json), [`../../schemas/partners.schema.json`](../../schemas/partners.schema.json); reader: [`../../scripts/registry.py`](../../scripts/registry.py); written by project-context (`agents/project-context/skills/build-registries/SKILL.md`).

```python
import sys; sys.path.insert(0, "<repo>/shared/scripts")
from registry import load_people, load_partners, allowed, is_operator, find, logo_for

ctx = "<project>/project-context"
people, partners = load_people(ctx), load_partners(ctx)        # [] when a file is absent
ok, reason = allowed(find(people, "Ana Ruiz"), "ads")           # (bool, reason); find() returns None when absent
logo = logo_for(find(partners, "acme"), "dark", ctx)            # logo_on_dark only; None when that variant is missing
```

Rules every reader applies:

- A person or a logo goes into a deliverable only when `allowed(entry, scope)` is true: `consent.status` `granted` with a date, a source and a `scope` holding the use. Absent from the registry (`find` returns `None`) is consent unknown: blocked. The person with `"is_operator": true` (the founder running the agent) is always allowed.
- Every path (`photo`, `logo`, `logo_on_dark`) is relative to the `project-context/` folder.
- `logo` is for light backgrounds, `logo_on_dark` for dark ones. A missing variant is not replaced by the other one without a contrast check (R5 of [`../reviewing-renders/SKILL.md`](../reviewing-renders/SKILL.md)); otherwise the company is named in text or left out.
- Every blocked entry the brief asked for goes into the report with the reason `allowed()` gave, so the founder knows whose consent to record.
- `RegistryError` (a file that is not JSON) → every entry of that file is blocked, warn once in the Step 0 block, never stop.

Per consumer (the scope string is fixed):

| Agent | Scope | Reads | Use |
|-------|-------|-------|-----|
| `static-ads-builder` | `ads` | `people.json`: `agents/static-ads-builder/scripts/photo_edit.py` refuses a real-photo edit of a person without granted `ads` consent | A face, a customer name or a partner logo enters `ads.json` only when `allowed(..., "ads")` is true; a logo strip takes `logo` or `logo_on_dark` from the ad's background. |
| `carousel-builder` | `carousel` | reserved scope: its workflow does not read the registries; its research step checks by hand that people are not identifiable without consent and that partner logos may be shown | When a deck shows a person or a partner logo, `allowed(..., "carousel")` is the check to run. |

Command line, for a quick look or a harness without Python imports:

```bash
python3 shared/scripts/registry.py allowed <project>/project-context --scope ads    # allowed / blocked per entry, with the reason
python3 shared/scripts/registry.py check <project>/project-context                  # schema, consent, photos, files
```

---

## Option `brand`: brand tokens and assets

For agents that render visuals: `static-ads-builder`, `carousel-builder` and `short-video-builder`. Run it inside step 2 above, after `context.json`.

### Read `brand.json`

1. Open `<project>/project-context/brand.json`. Absent → go to "No brand file" below.
2. **V2** (`"schema_version": "2.0"`): the contract is [`../../schemas/brand.schema.json`](../../schemas/brand.schema.json). Every path in it is relative to the `project-context/` folder: `assets/logos/wordmark-on-dark.svg` resolves to `<project>/project-context/assets/logos/wordmark-on-dark.svg`.
3. **V1** (no `schema_version`): map it on load with the table [Reading a V1 file](../../schemas/README.md#reading-a-v1-file). V1 paths are relative to the project root: strip the leading `project-context/` before resolving. Never rewrite the founder's file; suggest a `project-context` re-run to upgrade it.
4. Validate when a shell is available (from the agent folder):

   ```bash
   python3 ../../shared/scripts/validate_json.py ../../shared/schemas/brand.schema.json <project>/project-context/brand.json
   ```

   Exit 1 on a V2 file → use the fields that read correctly, list the errors once in the Step 0 block, never stop. A V1 file fails this schema by design: skip the check and map it.

### Expose to the run

| What | From | Rule |
|------|------|------|
| Color roles | `colors.*` | Missing roles follow [Fallbacks for missing roles](../../schemas/README.md#fallbacks-for-missing-roles). Templates take the CSS variables of [Mapping to CSS custom properties](../../schemas/README.md#mapping-to-css-custom-properties). |
| Fonts | `fonts.display`, `fonts.body`, `fonts.fonts_url` | Local `files` become `@font-face`; otherwise `fonts_url`. A family that cannot load is a warning in the report, never a silent swap. |
| Logo | `logos.on_dark` when `mode` (or the creative's background) is dark, `logos.on_light` otherwise | `logo_audit.status: fail` or a failing check for that variant → do not place that file on that background: take the other variant only after a contrast check, else typeset `logo_text` in `fonts.display`. `unchecked` → the render review checks the logo (R5 of [`../reviewing-renders/SKILL.md`](../reviewing-renders/SKILL.md)). |
| Real material | `assets.screenshot_path`, `assets.og_image_path`, `assets.favicon_path`, `assets.images[]` (with `role`) | The pool of reference files creatives are built from. `role: texture` images are decoration, never a product shot. Never re-scrape the site for them. |
| Caveats | `warnings[]` | Carried into the report's Limitations. |

### No brand file

Add at most two questions to the Step 0 message: the primary brand color (hex, optional; default: a neutral dark text on white with no accent claim) and a logo file path or URL (optional; default: `logo_text` from the product name, typeset). The calling agent adds its own (for example the exact product name). Never extract colors from a URL here: brand extraction belongs to `project-context`'s `extract-brand` skill.

This skill never writes `brand.json`.

---

## Failure modes

- **Folder absent** → run the agent's own input questions exactly as it did before this skill existed. Apply the default `claims_policy` and an empty `allowed_claims` list. No registry: no person but the founder (who said so in chat) and no logo is shown.
- **`context.json` malformed** → fall back to `context.md`; if that is also unusable, treat as absent and warn once.
- **`voice` missing** → default `claims_policy`, empty `banned_words`, tone `founder`, language from the user or `en`.
- **`brand.json` malformed (not JSON)** → ignore it, use the "No brand file" questions, warn once.
- **Context and user disagree** (for example a different ICP this run) → the user wins for this run; suggest updating `project-context` if the change is permanent.
