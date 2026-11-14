# shared/schemas/

JSON Schemas (draft 2020-12) for the files agents hand to each other, plus example instances. Validate any instance with the stack's stdlib validator:

```bash
python3 shared/scripts/validate_json.py <schema.json> <instance.json>
python3 shared/scripts/validate_json.py --jsonl <schema.json> <file.jsonl>
```

Exit 0 valid, 1 invalid (one line per error: file, JSON path, message), 2 unreadable file or not JSON. The validator implements the subset these schemas use (`type`, `required`, `properties`, `additionalProperties`, `items`, `enum`, `const`, `pattern`, `minLength`, `maxLength`, `minItems`, `maxItems`, `minimum`, `maximum`, local `$ref`); write new schemas within it. Its own tests: `python3 shared/scripts/tests/test_validate_json.py`.

| Schema | Instance location | Producer | Readers | Example |
|--------|-------------------|----------|---------|---------|
| [`brand.schema.json`](./brand.schema.json) | `<project>/project-context/brand.json` | project-context | carousel-builder, static-ads-builder, every visual agent | [`examples/brand.swanbase.json`](./examples/brand.swanbase.json) |
| [`run-record.schema.json`](./run-record.schema.json) | one line of `<project>/project-context/memory/runs.jsonl` | every agent, last step | growth orchestration, evals, Step 0 idempotence guard | in [`../skills/keeping-project-memory/SKILL.md`](../skills/keeping-project-memory/SKILL.md) |
| [`copy-rules.schema.json`](./copy-rules.schema.json) | `shared/skills/writing-gate/packs/*.json`, `<project>/project-context/voice/rules.json` | stack maintainers, project-context, the founder | writing gate | [`../skills/writing-gate/packs/en.json`](../skills/writing-gate/packs/en.json) |
| [`people.schema.json`](./people.schema.json) | `<project>/project-context/people.json` | project-context | static-ads-builder (photo_edit consent); scope `carousel` reserved, see loading-project-context | [`examples/people.fixturely.json`](./examples/people.fixturely.json) |
| [`partners.schema.json`](./partners.schema.json) | `<project>/project-context/partners.json` | project-context | `shared/scripts/registry.py` (`check`, `allowed`); no agent script reads it, see loading-project-context | [`examples/partners.fixturely.json`](./examples/partners.fixturely.json) |

Schemas are strict for producers (unknown keys fail, so a renamed field is caught) and readers stay defensive (a missing optional field means "use the fallback", never an error).

---

## `brand.json` V2

Every path in a V2 file is relative to the `project-context/` folder: `assets/logos/wordmark-on-dark.svg` resolves to `<project>/project-context/assets/logos/wordmark-on-dark.svg`. The schema rejects absolute paths, `..`, and paths starting with `project-context/`.

### Reading a V1 file

A `brand.json` without `schema_version` is V1, the older format of `extract-brand`. Readers map it on load; producers write V2 only.

| V1 key | V2 key | Note |
|--------|--------|------|
| `bg` | `colors.bg` | |
| `text_primary` | `colors.text` | |
| `accent` | `colors.accent` | |
| `accent_secondary` | `colors.accent_secondary` | |
| `font_heading` | `fonts.display.family` + `fonts.display.fallback` | Split the CSS stack: first family unquoted goes to `family`, the rest to `fallback`. `"'Instrument Serif', Georgia, serif"` gives `Instrument Serif` and `Georgia, serif`. |
| `font_body` | `fonts.body.family` + `fonts.body.fallback` | Same split. |
| `logo_path` (and `assets.logo_path`) | `logos.on_dark.wordmark` or `logos.on_light.wordmark` | V1 paths are relative to the project root: strip the leading `project-context/`. Place the file under the variant matching the background it was harvested on (`on_dark` when `bg` is dark), with `format` from the extension, and set `logo_audit.status` to `unchecked`. |
| `assets.og_image_path`, `assets.favicon_path`, `assets.screenshot_path` | same keys under `assets` | Strip the leading `project-context/`. |
| `assets.images[]` (strings) | `assets.images[].path` | Each string becomes `{ "path": ... }`, prefix stripped. |
| `warnings` | `warnings` | |

Keys some V1 readers expected but no V1 producer wrote:

| Key some V1 readers expected | V2 key |
|-------------------------------|--------|
| `text_secondary` | `colors.text_secondary` |
| `text_muted` | `colors.text_muted` |
| `card_bg` | `colors.surface` |
| `card_border` | `colors.border` |
| `card_radius` | `radius` |
| `fonts_url` | `fonts.fonts_url` |
| `logo_text` | `logo_text` |

V2 adds `schema_version`, `name`, `mode`, `source_url`, `as_of`, `colors.on_accent`, font `weights`, `source` and local `files`, both logo variants with `mark` and `wordmark`, `logo_audit` and `extensions`.

### Fallbacks for missing roles

Only `colors.bg`, `colors.text` and `colors.accent` are required. A reader derives the rest, in this order:

| Missing | Use |
|---------|-----|
| `text_secondary` | `text` |
| `text_muted` | `text_secondary` |
| `surface` | `bg` |
| `border` | `text_muted` |
| `accent_secondary` | `accent` |
| `on_accent` | `#ffffff` or `#000000`, whichever contrasts more with `accent` |
| `radius` | `0` |
| `logos.on_<mode>` | the other variant only after a contrast check against `bg`, else `logo_text` typeset in `fonts.display` |

### Mapping to CSS custom properties

The variable names visual agents inline into their templates:

```css
:root {
  --bg: <colors.bg>;               --surface: <colors.surface>;
  --text: <colors.text>;           --text-secondary: <colors.text_secondary>;
  --text-muted: <colors.text_muted>; --border: <colors.border>;
  --accent: <colors.accent>;       --accent-secondary: <colors.accent_secondary>;
  --on-accent: <colors.on_accent>; --radius: <radius>;
  --font-display: '<fonts.display.family>', <fonts.display.fallback>;
  --font-body: '<fonts.body.family>', <fonts.body.fallback>;
}
```

Local font files (`fonts.*.files`) become `@font-face` rules; otherwise `fonts.fonts_url` goes in a `<link rel="stylesheet">`.
