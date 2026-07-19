# Roadmap: Stock FIFO Tracker — Cloudflare Tunnel Deployment

## Overview

The app is already feature-complete and running locally on the Raspberry Pi. This milestone takes it from "runs on my machine" to safely and durably reachable from the internet at a real domain via Cloudflare Tunnel. The path is dependency-ordered: harden Django's production settings and put it under real process supervision while still LAN-only, close the two internet-facing security gaps flagged in `CONCERNS.md`, put automated off-device backups in place, and only then acquire the domain and flip the tunnel on for a real go-live. Edge-level hardening (Cloudflare Access, WAF, rate limiting, uptime monitoring) follows as a low-risk, dashboard-only layer once the base deployment is confirmed stable.

## Phases

**Phase Numbering:**

- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [x] **Phase 1: Django Production Settings Hardening** - Django's security settings are production-ready and verified locally, before any public exposure (completed 2026-07-19)
- [ ] **Phase 2: Gunicorn + systemd Process Supervision** - The app runs as a resilient background service on the Pi instead of the dev server
- [ ] **Phase 3: Close Internet-Facing Security Gaps** - Evidence file access and uploads are safe to expose once the app is reachable from the internet
- [ ] **Phase 4: Backup and Data Durability** - The FIFO ledger survives an SD-card failure or unclean power loss
- [ ] **Phase 5: Domain, Tunnel & Go-Live** - The app is reachable securely over the internet at a real domain, through Cloudflare Tunnel
- [ ] **Phase 6: Edge-Level Hardening** - The publicly reachable app has additional identity, abuse, and observability protections at Cloudflare's edge

## Phase Details

### Phase 1: Django Production Settings Hardening

**Goal**: Django's security settings are production-ready and verified locally — `SECURE_PROXY_SSL_HEADER`, `SECURE_SSL_REDIRECT`, secure cookies, HSTS, and `.env`-driven `CSRF_TRUSTED_ORIGINS`/`ALLOWED_HOSTS` — so the app behaves correctly once it sits behind Cloudflare's tunnel and doesn't leak debug information in production.
**Depends on**: Nothing (first phase)
**Requirements**: SETTINGS-01, SETTINGS-02, SETTINGS-03, SETTINGS-04
**Success Criteria** (what must be TRUE):

  1. With `DEBUG=False` locally, `python manage.py check --deploy` passes with no warnings
  2. A request carrying `X-Forwarded-Proto: https` (simulating Cloudflare's edge) is trusted as secure and does not trigger an HTTPS redirect loop
  3. `CSRF_TRUSTED_ORIGINS` and `ALLOWED_HOSTS` are read from `.env`, ready to take the real domain once it's acquired in Phase 5
  4. `DEBUG` defaults to `False` when unset in `.env` — the app fails closed, not open

**Plans**: 1/1 plans executed

- [x] 01-01-PLAN.md

### Phase 2: Gunicorn + systemd Process Supervision

**Goal**: The app runs as a resilient, supervised background service on the Pi — gunicorn instead of `runserver`, managed by systemd — while still only reachable from the Pi itself, so worker/process behavior can be validated before any tunnel exists.
**Depends on**: Phase 1
**Requirements**: PROC-01, PROC-02, PROC-03
**Success Criteria** (what must be TRUE):

  1. The app serves requests via gunicorn bound to `127.0.0.1`, not `manage.py runserver`
  2. Static files load correctly via whitenoise from within the gunicorn process, with no second static-file server running
  3. After a full Pi reboot, gunicorn is running again automatically without any manual command
  4. If the gunicorn process is killed, systemd restarts it automatically (`Restart=on-failure`) and it runs as a non-root user

**Plans**: TBD

### Phase 3: Close Internet-Facing Security Gaps

**Goal**: The two pre-production security gaps flagged in `CONCERNS.md` — unauthenticated media serving and unvalidated evidence uploads — are closed before the app is ever reachable from the internet.
**Depends on**: Phase 1 (can run in parallel with Phase 2)
**Requirements**: SEC-01, SEC-02
**Success Criteria** (what must be TRUE):

  1. Requesting an evidence file's URL while logged out, or while logged in as a different user, is denied — only the owning user can view their own evidence
  2. Uploading an evidence file of a disallowed type or over the size cap is rejected with a clear error message

**Plans**: TBD

### Phase 4: Backup and Data Durability

**Goal**: The FIFO ledger and evidence files survive an SD-card failure, corruption, or unclean power loss on the Pi, with a proven, tested restore path — independent of whether the tunnel exists yet.
**Depends on**: Nothing new (independent of Phases 1-3; must complete before Phase 5 go-live)
**Requirements**: BACKUP-01, BACKUP-02, BACKUP-03
**Success Criteria** (what must be TRUE):

  1. SQLite runs in WAL mode
  2. A nightly automated job produces a consistent backup (via `VACUUM INTO`/`.backup`, never a raw file copy) of the database and the `media/` directory, stored off the Pi
  3. A backup has been restored at least once and successfully brought the app back to a working state with correct data

**Plans**: TBD

### Phase 5: Domain, Tunnel & Go-Live

**Goal**: The app is reachable securely over the internet at a real domain through a named Cloudflare Tunnel — without exposing the Pi's home IP or opening router ports — and a runbook exists for bringing it back up after an outage.
**Depends on**: Phase 1, Phase 2, Phase 3, Phase 4
**Requirements**: DEPLOY-01, DEPLOY-02, DEPLOY-03, DEPLOY-04, DEPLOY-05
**Success Criteria** (what must be TRUE):

  1. Visiting the real domain over HTTPS loads the app from anywhere on the internet, with no router ports open and the Pi's home IP never exposed
  2. `cloudflared` runs as a named-tunnel systemd service (never a Quick Tunnel) that comes back up automatically after a Pi reboot
  3. An end-to-end smoke test succeeds over the real domain: login, record a buy/sell, export a PDF/CSV report, and upload/view evidence
  4. A deployment runbook documents cold-start after reboot/outage, restore-from-backup steps, and the `.env` variable reference

**Plans**: TBD

### Phase 6: Edge-Level Hardening

**Goal**: The publicly reachable app gains edge-level identity, abuse-prevention, and observability protections — dashboard-only Cloudflare configuration, no app code changes — added once the base deployment is confirmed stable.
**Depends on**: Phase 5
**Requirements**: EDGE-01, EDGE-02, EDGE-03, EDGE-04, EDGE-05
**Success Criteria** (what must be TRUE):

  1. Cloudflare Access requires an identity check (one-time-PIN email) before any request reaches the tunnel hostname
  2. Cloudflare WAF custom rules and Bot Fight Mode are active on the domain
  3. A Cloudflare rate-limiting rule throttles excessive requests to the app
  4. An external, off-Pi uptime monitor alerts if the public hostname becomes unreachable
  5. The nightly backup cron job is wrapped in a dead-man's-switch ping that alerts if backups stop running

**Plans**: TBD

## Progress

**Execution Order:**
Phases execute in numeric order: 1 → 2 → 3 → 4 → 5 → 6

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Django Production Settings Hardening | 1/1 | Complete    | 2026-07-19 |
| 2. Gunicorn + systemd Process Supervision | 0/TBD | Not started | - |
| 3. Close Internet-Facing Security Gaps | 0/TBD | Not started | - |
| 4. Backup and Data Durability | 0/TBD | Not started | - |
| 5. Domain, Tunnel & Go-Live | 0/TBD | Not started | - |
| 6. Edge-Level Hardening | 0/TBD | Not started | - |
