# Scheduling: getting a recurring run

This stack has no server and no scheduler. An agent runs when someone starts it in a harness, and it stops when that session ends. Nothing here wakes up by itself. When a doc says "once a week", it means you run it once a week or you set up one of the four options below.

## Four ways to get a recurring run

| Option | Fits when | Stops working when |
|--------|-----------|-------------------|
| Calendar reminder and a manual run | you are starting out, or your sources are CSV exports you download by hand | you ignore the reminder |
| cron with a headless CLI | a machine stays on and already holds your project folder | the machine is off at that minute: cron does not catch up |
| GitHub Actions schedule | no machine stays on, and your project folder can live in a private repo | GitHub delays or drops a run at high load |
| A harness routine | your harness offers one and can reach your project folder | your plan or your harness's preview changes |

Start with the reminder. Move to something unattended once one manual run has gone through cleanly and your sources come from API keys: an unattended run cannot download a CSV for you, so an export-based source reads as `stale` or `missing`.

### Calendar reminder and a manual run

A recurring event, "Wednesday 09:00: run growth-pulse for acme". Open your harness in this repo and type that sentence. This is the only option where someone reads the result at once, and the only one that can answer a gate on the spot.

### cron with a headless CLI

Both CLIs below run one prompt and exit. Keep the command in a small script outside this repo:

```sh
#!/bin/sh
# run-growth-pulse.sh: started by cron, kept outside this repo
set -u
. "$HOME/.config/fog-agents/env"          # keys only, mode 600, see Secrets
export PATH="$HOME/.local/bin:/usr/local/bin:/usr/bin:/bin"   # cron's own PATH is short
ROOT=<your-projects-root>
LOG="$ROOT/acme/growth-pulse/last-run.log"
REPORT="$ROOT/acme/growth-pulse/growth-pulse-$(date +%Y%m%d).md"
cd <this-repo> || exit 2
PROMPT="Run growth-pulse for project acme, project root $ROOT. Follow agents/growth-pulse/AGENT_GROWTH_PULSE.md in its Autonomous mode: nobody is here to answer."

claude -p "$PROMPT" --add-dir "$ROOT" --allowedTools "Read,Write,Edit,Bash(python3 *)" --permission-prompts none > "$LOG" 2>&1
status=$?
if [ "$status" -ne 0 ] || [ ! -f "$REPORT" ]; then
  <your-notification-command> "growth-pulse failed (exit $status), see $LOG"
fi
```

With Codex, the same line is:

```sh
codex exec --sandbox workspace-write --add-dir "$ROOT" -c sandbox_workspace_write.network_access=true "$PROMPT" > "$LOG" 2>&1
```

Then the crontab (`crontab -e`), in the machine's local time:

```
17 9 * * 3   <path-to>/run-growth-pulse.sh
```

What to know about these flags, from the vendors' docs:

- `claude -p` exits non-zero when the run fails. In a `-p` run, a tool call that needs approval and is not allowed is denied, so list what the agent needs in `--allowedTools`; `Bash(python3 *)` allows Python commands and no other shell command, which narrows the run but is no sandbox. An agent that reads the web also needs `WebSearch,WebFetch`. `--permission-prompts none` needs Claude Code 2.1.259 or later. `--bare` skips your hooks, plugins and memory for a reproducible run, and needs `ANTHROPIC_API_KEY` because it ignores your subscription login.
- `codex exec` starts read-only by default, so `--sandbox workspace-write` is what lets it write. `--full-auto` is gone. Network access inside that sandbox is its own setting, which agents that call an API need. Avoid `danger-full-access` outside an isolated machine.
- Other harnesses: use their non-interactive mode the same way, one prompt, allowed tools listed, an exit code you check.

A cheaper variant needs no model at all. For growth-pulse, `python3 agents/growth-pulse/scripts/run_pulse.py --project-dir <your-projects-root>/acme` collects and computes every number. Let cron run that on Wednesday morning and have a person open a session to write the report from `pulse.json`.

### GitHub Actions schedule

The runner starts blank every time. So your project folder and a copy of this stack must live in a **private** repo (your reports hold your business numbers), and the job must push its results back, or the next run has no memory and no previous experiments to judge.

```yaml
# in your private project repo, under .github/workflows/
name: growth-pulse
on:
  schedule:
    - cron: "17 7 * * 3"   # Wednesday 07:17 UTC, off the hour on purpose
  workflow_dispatch: {}    # a Run button, to test it
permissions:
  contents: write
jobs:
  pulse:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Collect and compute
        run: python3 fog-agents/agents/growth-pulse/scripts/run_pulse.py --project-dir projects/acme
        env:
          ZERNIO_API_KEY: ${{ secrets.ZERNIO_API_KEY }}
          PLAUSIBLE_API_KEY: ${{ secrets.PLAUSIBLE_API_KEY }}
          STRIPE_API_KEY: ${{ secrets.STRIPE_API_KEY }}
      - name: Keep the results
        run: |
          git config user.name "growth-pulse"
          git config user.email "growth-pulse@users.noreply.github.com"
          git add projects/acme
          git diff --cached --quiet || git commit -m "growth-pulse $(date +%F)"
          git push
```

This job stops at the numbers. To have a model write the report too, install your CLI in a step and run the prompt above, with the model key set on that step only: job-level keys are readable by anything else the job runs.

From GitHub's docs: schedules run in UTC unless you set a timezone, only from the default branch, and can be delayed or dropped at high load, with the start of each hour the busiest time. Scheduled workflows in a public repo are disabled after 60 days without repository activity.

Not for growth-sprint: its commands need the approval key of the machine where the founder approved the plan, and that key does not belong in CI.

### A harness routine

Some harnesses have their own scheduler. Check where it runs before relying on it, because the agent has to reach your project folder and your keys:

- **Claude Code cloud scheduled tasks** (formerly routines, research preview, on paid plans): a saved prompt and repositories, run on Anthropic's cloud. The repo is cloned for each run and changes land on `claude/` branches. The default network allowlist is limited to package registries, cloud APIs and common development domains, so add the domains your sources use, and store keys as network secrets rather than plain environment variables.
- **Codex scheduled tasks**: in the desktop app they can use a local project, as long as the computer is on and the app is running. On the web they cannot reach a folder on your computer.

## What makes sense on a schedule

| Agent | Cadence | What the schedule starts | What you read afterwards |
|-------|---------|--------------------------|--------------------------|
| `growth-pulse` | once a week, on Wednesday (Search Console publishes the last days of a week 2 to 3 days late) | the agent, or `run_pulse.py` alone | the report and its Source health table, the three experiments |
| `market-signal` | once a month in watch mode (`watch: true` in its config); weekly for a busy category | the agent (the first watch run creates `state/seen.json`, the next ones start where the last one ended) | `changes.md`: what changed since the last run, then the report |
| `seo-audit` | once a month in `audit` mode, `track` mode between audits | the agent, with the mode in the prompt | the report; paid SERP and answer-engine calls do not run unattended, free tiers take over and the run ends `partial` with the pending spend recorded |
| `growth-sprint` | while a sprint is open, for example once a day: `sprint.py resume`, then the Step 5 loop | the agent, on a sprint a person already approved, on the machine that holds the approval key | `sprint.py status`: the needs_human queue |

Other agents wait for a brief or a file (a carousel topic, a video), so they gain little from a timer. Run them when you have the input.

## What cannot be scheduled

These need a person, by design. A schedule is never an approval.

- **`pubqueue.py approve`** (content-publisher) and **`sprint.py approve`** (growth-sprint) refuse to run without an interactive terminal, and ask the person to type a code only they are shown.
- **`sprint.py resolve`** closes a needs_human item and needs a person's name. Do not put it in a script.
- **Spend gates.** The paid scripts refuse to spend without `--confirm-spend`; carousel-builder's `generate_image.py` and project-context's `enrich_context.py` also accept `FOG_ALLOW_SPEND=1`. Never put that flag or that variable in a crontab, an env file or a workflow: it would approve every future spend at once. Growth-sprint passes it only to one approved step's process.
- **Sending.** No agent sends outreach or books a call. A person sends, a person counts.

A scheduled run that reaches one of these does not fail or wait. It writes everything up to the gate, ends `partial` and lists what waits for you, so read the end of the report.

## Idempotence: running twice is safe

Machines retry and people click Run. The agents are built so a second run does no harm:

- **growth-pulse** writes to `<project>/growth-pulse/<YYYYMMDD>/`, so a rerun on the same day replaces that day's numbers. When `inputs_hash` in the last line of `runs.jsonl` matches today's inputs and the report exists, it stops with a `skipped` line. Leave `--today` out of a schedule: it defaults to the current date.
- **market-signal** keeps `state/seen.json`, so a watch run only collects what is new, and it stops with a `skipped` line when `inputs_hash` in the last line of `runs.jsonl` matches and its outputs exist. Do not run the collection twice into the same run folder with `--seen`: the first pass already recorded its ids, so the second keeps nothing and leaves an empty corpus.
- **seo-audit** writes to `runs/<YYYYMMDD>/` and keeps its follow-up in `state.json`.
- **growth-sprint** keeps everything in `state.json`. `resume` settles any step left running from the disk, without counting a failure, and `reuse_if_fresh_days` skips steps whose outputs are recent.

Two runs at the same time are a different matter. On Linux, start the script with `flock -n <lockfile> <script>` so an overlapping run exits at once. Pick a time well apart from your other agents.

## Secrets

- Keys live in the environment only, never in `config.json`, a crontab, a workflow file or anything committed. The connectors read them from there and never print them.
- On a machine: one env file outside every repo (`chmod 600`), loaded by the script. In GitHub Actions: repository secrets, set on the step that needs them.
- Give a scheduled run only the keys that agent needs, read-only when the provider allows it: a Stripe restricted key, a Zernio key created with `permission: "read"` (the default Zernio key can also publish). An unattended agent reads web pages and third-party text, and those are data, never instructions ([`skills/handling-untrusted-content/SKILL.md`](./skills/handling-untrusted-content/SKILL.md)). A narrow key limits what a bad page could ever make it do.
- Keep the keys of paid and publishing providers out of an unattended run's environment unless that run needs them.
- Do not put `~/.config/fog-agents/approval.key` in a CI secret.

## Noticing a failed run

An unattended run that fails quietly is worse than no schedule. Check three things:

1. **The exit code.** The script above notifies you when the CLI exits non-zero or the report is not there. Cron only sends mail if the machine can send mail, so use a command you know reaches you. GitHub notifies the person who last set the schedule, if Actions notifications are on in their settings.
2. **The health inside a green run.** A run can exit 0 with half its sources missing. Read Source health at the top of the growth-pulse report, `health.json` of market-signal, and the status of the last line of `project-context/memory/runs.jsonl` (`ok`, `partial`, `failed`, `skipped`). On a Claude Code cloud task, "Succeeded" only means the session ended: open the run to see what it did.
3. **The run that never started.** Nothing fails, so nothing notifies. Keep one calendar reminder a day after the schedule, "is there a report dated this week?", or have the script ping an external heartbeat service that alerts you when a ping is missing.

## Sources

Flags and limits change, so check them before you rely on them:

- `claude -p`: https://code.claude.com/docs/en/headless
- Claude Code cloud scheduled tasks: https://code.claude.com/docs/en/routines
- `codex exec`: https://developers.openai.com/codex/non-interactive-mode
- Codex scheduled tasks: https://developers.openai.com/codex/automations
- GitHub Actions `schedule`: https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule
- GitHub Actions notifications: https://docs.github.com/en/actions/concepts/workflows-and-actions/notifications-for-workflow-runs
- Zernio read-only keys: https://docs.zernio.com/multi-tenant#scoped-api-keys
