# Stock FIFO Tracker

## What This Is

A Django web app for tracking personal stock trades with FIFO cost-basis accounting (dual USD/THB currency), used by a single person to record buys/sells, view a live portfolio dashboard, and export formal FIFO capital-gain reports (PDF/CSV). The app itself is already built and feature-complete. This GSD milestone covers taking it from "runs on my machine" to reachable securely, at all times, from a home Raspberry Pi 4 (64-bit OS Lite) via a Cloudflare Tunnel.

## Core Value

The app must be reachable securely over the internet via Cloudflare Tunnel — without exposing the Pi's home IP or opening router ports — while preserving the FIFO ledger's integrity and the owner's exclusive access to their financial data.

## Requirements

### Validated

- ✓ FIFO-accurate buy/sell lot tracking with dual-currency (USD/THB) cost basis — existing
- ✓ Portfolio dashboard with live pricing (yfinance) and graceful per-symbol degradation — existing
- ✓ FIFO Portfolio Report export (PDF via ReportLab, CSV) — existing
- ✓ Per-user data isolation (owner-scoped queries, login required) — existing
- ✓ Evidence upload for buy/sell transactions — existing
- ✓ Runs on Raspberry Pi 4 (64-bit OS Lite) as a local server — existing (commit `091d58c`)
- ✓ Django settings hardened for production (env-driven `CSRF_TRUSTED_ORIGINS`, `SECURE_SSL_REDIRECT`, secure cookies, HSTS gated on `DEBUG`, fail-closed `DEBUG` default) — Phase 1

### Active

- [ ] Real domain acquired and configured (`CSRF_TRUSTED_ORIGINS`, Cloudflare Tunnel hostname)
- [ ] Cloudflare Tunnel configured and running on the Pi, routing the domain to the local Django server
- [ ] App reachable over the internet through the tunnel without exposing the Pi's IP or opening router ports
- [ ] Necessary pre-production security gaps closed: evidence file-upload validation (type/size limits), review of Django's direct media-file serving under the tunnel
- [ ] Deployment runbook documented (bringing the Pi server + tunnel back up after a reboot/outage)

### Out of Scope

- Multi-user support / concurrency hardening — single user only for this milestone
- SQLite → PostgreSQL migration — CONCERNS.md flags write contention as a future risk, not blocking at single-user load
- New app features (bulk import, tax-year filtering, broker reconciliation) — deployment-only milestone; tracked in CONCERNS.md for a future milestone
- Automated test suite additions (FIFO allocation tests, view tests, isolation tests) — valuable per CONCERNS.md but out of scope for this deployment-focused milestone

## Context

- Existing Django 6 + SQLite app, fully featured — see `.planning/codebase/` for the full architecture/stack/conventions map
- Target host: Raspberry Pi 4, 64-bit OS Lite, already running the app locally (commit history: "Prepare necessary things to deploy to local server", "Fixing bug to run on local server (Raspberry pi 4 x64 OS lite)")
- No domain owned yet — must be acquired before `CSRF_TRUSTED_ORIGINS` and the Tunnel hostname can be finalized
- Single owner/user — no other accounts will use this instance
- `.env` holds `DEBUG`/`SECRET_KEY`/`ALLOWED_HOSTS` via `python-decouple`; `DEBUG=True` locally, must be `False` on the Pi deployment
- `config/settings.py` is fully hardened as of Phase 1 (commits `64a392d`, `14f27b4`, `785a34e`): env-driven `CSRF_TRUSTED_ORIGINS`, `SECURE_SSL_REDIRECT`, `SECURE_PROXY_SSL_HEADER`, secure cookies, HSTS (all three settings correctly gated on `not DEBUG`), fail-closed `DEBUG` default. Trusting `X-Forwarded-Proto` is only safe once Phase 2 binds Gunicorn to loopback-only (documented inline, tracked as a hard Phase 2 prerequisite).
- `CONCERNS.md` flags remaining pre-production items for later phases: missing file-upload validation (Phase 3), Django directly serving media files not production-safe (Phase 3)

## Constraints

- **Hardware**: Raspberry Pi 4, 64-bit OS Lite — limited RAM/CPU/disk versus a typical server
- **Network**: No port forwarding or static IP on the home network — Cloudflare Tunnel is the only path in
- **Database**: Stays on SQLite for this milestone — no migration to Postgres
- **Users**: Single user — no multi-tenant load or concurrency requirements
- **Budget**: Personal project — prefer a low-cost domain and Cloudflare's free Tunnel tier

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Keep SQLite instead of migrating to PostgreSQL | Single user, low write volume — migration effort not justified for this milestone | — Pending |
| Use Cloudflare Tunnel instead of port forwarding | Avoids exposing home IP / opening router ports on a residential network | — Pending |
| `SESSION_COOKIE_SECURE` / `CSRF_COOKIE_SECURE` conditional on `not DEBUG` | Keeps local dev over plain HTTP working while enforcing secure cookies once `DEBUG=False` on the Pi | ✓ Good |
| Defer multi-user support, new features, and test-suite work out of this milestone | Keep the deployment milestone focused and shippable | — Pending |
| `SECURE_HSTS_SECONDS` gated on `not DEBUG` (`31536000 if not DEBUG else 0`) | Code review (Phase 1) caught it as ungated, unlike its sibling HSTS settings — an HTTPS-reached dev instance would otherwise lock a browser into forced-HTTPS for a year | ✓ Good |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd-transition`):
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

**After each milestone** (via `/gsd-complete-milestone`):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

---
*Last updated: 2026-07-19 after Phase 1 (Django Production Settings Hardening)*
