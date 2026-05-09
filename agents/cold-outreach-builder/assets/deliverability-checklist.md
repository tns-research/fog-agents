# Deliverability Checklist (cold email, 2026)

Deliverability is the floor, not a tactic. A perfect message that lands in spam is wasted. Run through this checklist before any cold-email send.

Updated to reflect Gmail / Yahoo / Outlook policy changes through Q1 2026.

---

## A. Authentication (mandatory)

All three are required since 2024. Enforcement tightened in November 2025; Gmail rejects non-compliant bulk senders.

- [ ] **SPF** (Sender Policy Framework) record on the sending domain. Lists which servers are allowed to send mail for the domain.
- [ ] **DKIM** (DomainKeys Identified Mail) signing on outbound mail. Cryptographic signature proves the message was not altered.
- [ ] **DMARC** (Domain-based Message Authentication, Reporting and Conformance) record published. Policy: `p=quarantine` minimum, `p=reject` ideal once aligned.
- [ ] DMARC alignment: the From-domain must align with the SPF / DKIM domain (relaxed alignment minimum, strict ideal).
- [ ] **BIMI** (Brand Indicators for Message Identification) optional but boosts inbox placement on Gmail when the sending domain has DMARC `p=reject`.

How to verify: `dig TXT _dmarc.<domain>`, `dig TXT default._domainkey.<domain>`, `dig TXT <domain>` (look for `v=spf1`).

---

## B. Sending domain hygiene

- [ ] Use a **dedicated subdomain** (e.g. `outreach.acme.com`), not the main domain. Protects the main domain reputation if the cold campaign damages sender score.
- [ ] The subdomain has its own SPF / DKIM / DMARC.
- [ ] Reverse DNS (PTR record) resolves cleanly.
- [ ] No blacklisted IPs (check via Spamhaus, Barracuda, SORBS).
- [ ] If using a sending tool (e.g. Instantly), confirm the tool's sending IPs are clean and the SPF includes them.

---

## C. Inbox warmup

A new sending inbox or domain has no reputation. Cold-blasting from it triggers anti-spam.

- [ ] Inbox warmed for **14 to 30 days minimum** before any cold send. Tools: Mailwarm, Lemwarm, Instantly Warmup. Free options: Warmup Inbox.
- [ ] Warmup volume ramps gradually: start at 5 to 10 emails per day, add 5 per day until 50 to 100 per day.
- [ ] After cold-campaign launch, warmup continues in background to maintain reputation.
- [ ] Do not pause warmup mid-campaign.

---

## D. Volume caps

Sustained volume is a signal. Spikes are a signal.

| Inbox age | Max cold sends per day | Notes |
|-----------|-----------------------:|-------|
| <14 days | 0 | warmup only |
| 14 to 30 days | 5 to 10 | careful ramp |
| 30 to 60 days | 20 to 30 | warm + cold |
| 60+ days, established reputation | 30 to 50 | sustained |
| Spike (>2x prior daily volume) | flagged | avoid |

If sending volume needs to exceed 50 per inbox per day, add inboxes (multi-inbox setup). Never spike a single inbox.

---

## E. Spam-complaint and bounce rates

These are sender-reputation killers. Targets per Gmail's bulk-sender requirements:

- [ ] **Spam-complaint rate ≤ 0.3%** (target ≤ 0.1%). Gmail's threshold; sustained breach = throttling or block.
- [ ] **Hard-bounce rate ≤ 2%** ideally, ≤ 5% acceptable on a fresh list.
- [ ] List validation before send: NeverBounce, ZeroBounce, or built-in tool feature. Remove invalid emails.
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
- [ ] From-address matches the human (`alex@outreach.acme.com`).
- [ ] Reply-to set to the same address as From, or to a real monitored inbox.
- [ ] Display name does not mismatch the From-domain (anti-phishing filters flag this).

---

## J. List quality

A clean list with great copy gets through. A bad list with great copy does not.

- [ ] Email addresses are role-appropriate (no `info@`, `contact@`, `noreply@` in cold).
- [ ] List validated within 7 days of send (not at list-build time, again at send time).
- [ ] No purchased lists. Purchased lists trigger immediate spam-trap hits and burn the domain.
- [ ] Honour suppression lists from prior campaigns (do not re-cold the same prospect within 90 days unless explicitly opted-in).

---

## K. Pre-send sanity check

Run before launching any campaign:

```bash
# Check SPF / DKIM / DMARC of the sending domain
dig TXT outreach.acme.com
dig TXT _dmarc.outreach.acme.com
dig TXT default._domainkey.outreach.acme.com

# Check sender against blacklists
# (Use mail-tester.com, mxtoolbox.com, or your tool's built-in checker)

# Run one test send to a Gmail and an Outlook inbox you control
# Inspect headers (Authentication-Results) and inbox placement
```

If any check fails, stop the campaign and fix before sending.

---

## L. Channel-specific notes

For LinkedIn outreach, this checklist does not apply (LinkedIn handles its own delivery). LinkedIn-specific deliverability concerns (cap-flagging, account safety) are in `sequencing-linkedin-dm/SKILL.md`.

---

## Summary

A campaign that fails any item in sections A, C, D, E, or G is not ready to send. Fix first, ship after. Sections B, F, H, I, J are best-practice but graded; aim for full pass.

The agent's review-mode report includes a deliverability section with each item ticked or flagged.
