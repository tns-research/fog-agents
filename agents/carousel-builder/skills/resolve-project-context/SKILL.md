---
name: resolve-project-context
description: Load shared brand and business context for a project from the project-context folder, falling back to a short inline Q&A when it is absent. Reads brand.json and context.json defensively, then exposes the brand tokens and any voice rules to the carousel workflow. Use at Step 0 of carousel-builder. Triggers: "load my context", "use my brand", "make it on-brand".
license: Apache-2.0
compatibility: Claude Code, Cursor, Codex CLI, Gemini CLI
metadata:
  version: "1.0"
allowed-tools: Read
---

# Skill: resolve-project-context

Read the shared context once, then let the rest of the carousel run reuse it. This skill never writes. It only reports what was found so the agent can decide whether to reuse the shared folder or fall back to a short inline Q&A.

**Golden rule:** shared context is an accelerator, never a hard gate. A missing `project-context/` folder must never stop the run.

---

## When to load

- Step 0 of `carousel-builder`, always, on every run.

---

## Procedure

1. **Locate the folder.** Look for `<project-root>/<project-slug>/project-context/`.
2. **If it exists, read both artifacts defensively:**
   - `brand.json`: `bg`, `text_primary`, `accent`, `accent_secondary`, `font_heading`, `font_body`, `logo_path`. Resolve `logo_path` against the `project-context/` folder, not the agent folder.
   - `context.json`: `one_liner`, `what_it_is`, `category`, `icp`, `offer`, `positioning`, `voice`.
3. **Carry forward into the run:**
   - Brand tokens -> default typography colors, accents, and the logo path used by render.
   - `voice.banned_words` -> hard blacklist for any copy step that needs it.
   - `voice.claims_policy` -> the anti-fabrication rule for any copy step that needs it.
4. **If it does not exist, run a short inline Q&A (3 questions max), then continue:**
   - What is the project?
   - Who is it for?
   - Primary brand color, if known?
   - Treat the answers as the minimal context. Do not block on more detail.
5. **Report** in one line what was loaded, or that the run is using inline answers.

---

## What this skill does not do

- It does not extract or re-derive brand colors from a URL. That lives in `project-context`.
- It does not write any file.

---

## Failure modes

- **`brand.json` present but malformed** -> ignore it, fall back to the inline color question, warn once.
- **`context.json` present but missing `voice`** -> apply a default empty blacklist and a conservative claims policy.
- **Neither file present** -> inline Q&A path. Never error.
