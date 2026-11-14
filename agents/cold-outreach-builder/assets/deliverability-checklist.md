# Deliverability Checklist (cold email, 2026)

Deliverability is the floor, not a tactic. A perfect message that lands in spam is wasted. Run through this checklist before any cold-email send.

Provider rules quoted below carry their source; the volume and warmup numbers are conservative defaults of this stack, not provider rules. Re-check the linked pages before a large send: providers change them.

---

## A. Authentication (mandatory)

All three are required for bulk senders to Gmail (Google, Email sender guidelines, https://support.google.com/a/answer/81126). "Starting November 2025, Gmail is ramping up its enforcement on non-compliant traffic" (Google, Email sender guidelines FAQ, https://support.google.com/a/answer/14229414).

- [ ] **SPF** (Sender Policy Framework) record on the sending domain. Lists which servers are allowed to send mail for the domain.
- [ ] **DKIM** (DomainKeys Identified Mail) signing on outbound mail. Cryptographic signature proves the message was not altered.
- [ ] **DMARC** (Domain-based Message Authentication, Reporting and Conformance) record published. Policy: `p=quarantine` minimum, `p=reject` ideal once aligned.
- [ ] DMARC alignment: the From-domain must align with the SPF / DKIM domain (relaxed alignment minimum, strict ideal).
- [ ] **BIMI** (Brand Indicators for Message Identification) optional: shows the brand logo in inboxes that support it, and needs DMARC at enforcement. It is a display feature, not a deliverability fix.

How to verify: `python3 scripts/check_sender.py --domain <sending domain> --dkim-selector <selector> --out sender-check.json` reads SPF, DKIM, DMARC and MX by DNS only (dig, else DNS over HTTPS, else answers pasted into a `--records` file) and writes what it saw; the report and the sidecar copy that file, never hand-typed booleans. The DKIM selector is the `s=` tag of the `DKIM-Signature` header of a message you sent from the domain.

---

## B. Sending domain hygiene

- [ ] Use a **dedicated subdomain** (e.g. `outreach.acme.example`), not the main domain. Protects the main domain reputation if the cold campaign damages sender score.
- [ ] The subdomain has its own SPF / DKIM / DMARC.
- [ ] Reverse DNS (PTR record) resolves cleanly.
- [ ] No blacklisted IPs (check via Spamhaus, Barracuda, SORBS).
- [ ] If using a sending tool, confirm the tool's sending IPs are clean and the SPF includes them.

---

## C. Inbox warmup

A new sending inbox or domain has no reputation. Cold-blasting from it triggers anti-spam.

- [ ] Inbox warmed for **14 to 30 days minimum** before any cold send (stack default). Use your sending tool's built-in warmup or a dedicated warmup service.
- [ ] Warmup volume ramps gradually from a handful of emails per day; follow the ramp of the warmup tool rather than a fixed figure.
- [ ] After cold-campaign launch, warmup continues in background to maintain reputation.
- [ ] Do not pause warmup mid-campaign.

---

## D. Volume caps

Sustained volume is a signal. Spikes are a signal. The caps below are this stack's conservative defaults (no provider publishes a per-inbox cold-send limit); lower them at the first sign of trouble (bounces, complaints, Postmaster Tools reputation drop).

| Inbox age | Max cold sends per day (stack default) | Notes |
|-----------|-----------------------:|-------|
| <14 days | 0 | warmup only |
| 14 to 30 days | 5 to 10 | careful ramp |
| 30 to 60 days | 20 to 30 | warm + cold |
| 60+ days, established reputation | 30 to 50 | sustained |
| Sudden spike over the prior daily volume | flagged | avoid |

If sending volume needs to exceed 50 per inbox per day, add inboxes (multi-inbox setup). Never spike a single inbox.

---

## E. Spam-complaint and bounce rates

These are sender-reputation killers.

- [ ] **Spam-complaint rate**: "Keep spam rates reported in Postmaster Tools below 0.10% and avoid ever reaching a spam rate of 0.30% or higher" (Google, Email sender guidelines, https://support.google.com/a/answer/81126).
- [ ] **Hard bounces**: every address verified before the first send, every hard bounce removed at once, and the sequence paused if bounces keep coming. No provider publishes a bounce threshold for cold mail; do not quote one.
- [ ] List validation before send: a third-party validation service or the sending tool's own feature. Remove invalid emails.
- [ ] **Never verify addresses by SMTP probes (RCPT TO) from the machine that runs the agent.** Probing mail servers gets that IP listed on blocklists (Spamhaus among them), after which every check reads as a rejection and the domain's own mail suffers. `check_sender.py` makes DNS queries only. After a wave of rejections, re-check one address known to be good before believing the wave.
- [ ] Suppression list maintained: bounced emails, replied-stop-asking emails, unsubscribed.

---

## F. Message format

- [ ] **Plain text** preferred. Plain-text or minimal HTML (signature only).
- [ ] **Single link maximum** in body, **zero links** in Email 1 ideal.
- [ ] **No tracking pixel**, or tracking-pixel disabled. Gmail's spam filter penalizes trackers.
- [ ] **No banner images**, **no multi-column layouts**, **no HTML tables for layout**.
- [ ] If a link is necessary, it goes to a domain owned by the sender (not bit.ly, not goo.gl, no URL shorteners).
- [ ] HTML and text MIME parts both populated if HTML is sent (no HTML-only).

---

## G. Unsubscribe (jurisdictional)

Required for bulk senders per Gmail (since 2024) and per CAN-SPAM (US), GDPR (EU), CASL (Canada).

- [ ] **List-Unsubscribe header** in every cold message: `List-Unsubscribe: <mailto:unsub@example.com>, <https://example.com/unsubscribe?id=...>`
- [ ] **One-click unsubscribe** (RFC 8058 compliant `List-Unsubscribe-Post: List-Unsubscribe=One-Click` header).
- [ ] Unsubscribe link in the visible body for B2C; for B2B cold under CAN-SPAM, the header is sufficient but visible body link recommended.
- [ ] Honoring an unsubscribe within 10 days is a legal requirement (CAN-SPAM); the sending tool should automate this.

---

## H. Send-time discipline

- [ ] Vary day-of-week and time-of-day across the sequence (see `designing-sequences/SKILL.md`).
- [ ] Avoid Mondays before 09:00 and Fridays after 16:00 in recipient's timezone.
- [ ] Avoid Sundays unless the ICP is publicly active on Sundays.
- [ ] Send in batches with random jitter (5 to 30 second intervals between sends) when using a tool that supports it.

---

## I. From-name and reply-to

- [ ] From-name is a real human (`Alex Morgan`, not `Acme Sales`).
- [ ] From-address matches the human (`alex@outreach.acme.example`).
- [ ] Reply-to set to the same address as From, or to a real monitored inbox.
- [ ] Display name does not mismatch the From-domain (anti-phishing filters flag this).

---

## J. List quality

A clean list with great copy gets through. A bad list with great copy does not.

- [ ] Email addresses are role-appropriate (no `info@`, `contact@`, `noreply@` in cold).
- [ ] List validated within 7 days of send (not at list-build time, again at send time).
- [ ] No purchased lists. Purchased lists trigger immediate spam-trap hits and burn the domain.
- [ ] Honour suppression lists from prior campaigns: `scripts/outreach_state.py` keeps them (bounced, unsubscribed, negative replies never return; anyone else waits `state.recontact_after_days` of `limits.json`, default 180 days), and `run_dossiers.py prepare` and the export apply them.

---

## K. Pre-send sanity check

Run before launching any campaign:

```bash
# Check SPF / DKIM / DMARC / MX of the sending domain, and the sending plan (DNS only)
python3 scripts/check_sender.py --domain outreach.acme.example --dkim-selector <selector> \
  --inbox-age-days <age> --list-size <n> --out sender-check.json
# Without Python: the same checks by hand
dig TXT outreach.acme.example
dig TXT _dmarc.outreach.acme.example
dig TXT <selector>._domainkey.outreach.acme.example
dig MX outreach.acme.example

# Check sender against blacklists
# (Use mail-tester.com, mxtoolbox.com, or your tool's built-in checker)

# Run one test send to a Gmail and an Outlook inbox you control
# Inspect headers (Authentication-Results) and inbox placement
```

If any check fails (exit 1 of `check_sender.py`), stop the campaign and fix before sending.

---

## L. Channel-specific notes

For LinkedIn outreach, this checklist does not apply (LinkedIn handles its own delivery). LinkedIn-specific deliverability concerns (cap-flagging, account safety) are in `sequencing-linkedin-dm/SKILL.md`.

---

## Summary

A campaign that fails any item in sections A, C, D, E, or G is not ready to send. Fix first, ship after. Sections B, F, H, I, J are best-practice but graded; aim for full pass.

The agent's review-mode report includes a deliverability section with each item ticked or flagged.
