# Security policy

## Reporting a vulnerability

Please report security issues privately, through GitHub Security Advisories:
open the [Security tab of tns-research/fog-agents](https://github.com/tns-research/fog-agents/security) and click **Report a vulnerability**
([direct link](https://github.com/tns-research/fog-agents/security/advisories/new)).
Do not open a public issue, pull request or discussion for a vulnerability.

A useful report names the agent and the script, the command or input that triggers the issue, what happens, and what you expected. A minimal reproduction (a fixture file, a crafted page) helps most.

We aim to acknowledge a report within a few working days, then keep you informed until a fix or a decision. Fixes land on the default branch; there are no maintained release branches, so only the latest version of the default branch is supported. We credit reporters in the advisory unless they ask otherwise.

## Scope

In scope:

- The scripts under `agents/*/scripts/`, `shared/scripts/` and `shared/skills/*/scripts/`: file handling, URL fetching, subprocess calls, path handling, anything that reads or writes outside the user's project folder.
- The approval and spend gates: a way to publish, schedule, send or approve without the founder, or to call a paid API without `--confirm-spend` where the script documents that flag.
- Untrusted content: a web page, post, e-mail, prospect reply or third-party file that makes an agent following its workflow run a command, fetch a local file or internal address, change its configuration, spend or publish.
- The CI workflow under `.github/`.

Out of scope:

- Vulnerabilities in third-party CLIs, APIs or model providers the agents call. Report those upstream.
- Issues that need an attacker who already controls the user's machine, shell or API keys.
- The quality of generated copy, unless it leaks data or bypasses a gate.

## Known limits

- The approval gates stop an agent that follows its `AGENT_<NAME>.md` workflow. They do not stop an agent with an unrestricted shell: such an agent can edit queue and state files or run the approve command itself. Keep publishing and payment keys out of the agent's environment when you do not want it to act alone, and review the queue before anything goes live.
- Scripts that call a paid API require `--confirm-spend` (or print the planned calls and exit); `generate_image.py` of carousel-builder and `enrich_context.py` of project-context also accept `FOG_ALLOW_SPEND=1` for scripted runs. The flag records the founder's agreement; it is not an access control. The real limit is which keys you put in the environment.
- Fetching scripts accept http and https only. Some also refuse private, loopback and link-local addresses; DNS rebinding between the check and the request is not covered.
- Fetched content is data, never instructions (see `AGENTS.md` and `shared/skills/handling-untrusted-content/SKILL.md`). This rule lowers the risk of prompt injection; no model follows it perfectly.
