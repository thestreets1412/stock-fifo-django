# Requirements: Stock FIFO Tracker — Cloudflare Tunnel Deployment

**Defined:** 2026-07-19
**Core Value:** The app must be reachable securely over the internet via Cloudflare Tunnel — without exposing the Pi's home IP or opening router ports — while preserving the FIFO ledger's integrity and the owner's exclusive access to their financial data.

## v1 Requirements

Requirements for this deployment milestone. Each maps to a roadmap phase.

### Settings Hardening

- [x] **SETTINGS-01**: `SECURE_PROXY_SSL_HEADER` is set so Django correctly trusts `X-Forwarded-Proto` from Cloudflare's tunnel (prevents an infinite HTTPS redirect loop)
- [x] **SETTINGS-02**: `SECURE_SSL_REDIRECT`, secure session/CSRF cookies, and HSTS settings are enabled correctly for production
- [x] **SETTINGS-03**: `CSRF_TRUSTED_ORIGINS` and `ALLOWED_HOSTS` are driven by `.env`, ready to take the real domain once acquired
- [x] **SETTINGS-04**: `DEBUG` defaults to `False` (fail-closed) in production; `python manage.py check --deploy` passes clean

### Process Supervision

- [ ] **PROC-01**: App runs under gunicorn (not `runserver`), bound to `127.0.0.1` only
- [ ] **PROC-02**: gunicorn runs as a systemd service — non-root user, `Restart=on-failure`, starts on boot — verified with an actual Pi reboot
- [ ] **PROC-03**: Static files are served via whitenoise from within the gunicorn process (no second server needed)

### Security Gaps

- [ ] **SEC-01**: Evidence media access is served through an authenticated, owner-scoped Django view — no unauthenticated file serving (closes the CONCERNS.md media-serving gap without introducing a reverse proxy)
- [ ] **SEC-02**: Evidence uploads are validated — file extension allowlist + size cap

### Backup & Data Durability

- [ ] **BACKUP-01**: SQLite WAL mode is enabled
- [ ] **BACKUP-02**: Automated nightly off-device backup of the SQLite database (`VACUUM INTO`/`.backup`, never a raw `cp`) and the `media/` directory
- [ ] **BACKUP-03**: At least one backup restore has been tested successfully

### Domain, Tunnel & Go-Live

- [ ] **DEPLOY-01**: A real domain is acquired and added to Cloudflare
- [ ] **DEPLOY-02**: `cloudflared` is installed as a **named** tunnel systemd service (never a Quick Tunnel) — verified with an actual Pi reboot
- [ ] **DEPLOY-03**: `ALLOWED_HOSTS`/`CSRF_TRUSTED_ORIGINS` are finalized with the real domain
- [ ] **DEPLOY-04**: End-to-end smoke test passes over the real HTTPS domain — login, buy/sell POST, PDF/CSV report export, evidence upload/view
- [ ] **DEPLOY-05**: Deployment runbook is written — cold-start after reboot/outage, restore-from-backup steps, `.env` variable reference

### Edge-Level Hardening

- [ ] **EDGE-01**: Cloudflare Access (Zero Trust free tier) is enabled in front of the tunnel hostname as an edge-level identity check
- [ ] **EDGE-02**: Cloudflare WAF custom rules + Bot Fight Mode are enabled
- [ ] **EDGE-03**: A Cloudflare rate-limiting rule is configured (free tier: 1 rule)
- [ ] **EDGE-04**: An external uptime monitor (running off the Pi) pings the public hostname
- [ ] **EDGE-05**: A dead-man's-switch ping wraps the backup cron job

## v2 Requirements

Deferred to a future milestone. Tracked but not in the current roadmap.

### Data & Scale

- **DATA-01**: SQLite → PostgreSQL migration
- **DATA-02**: Multi-user support / concurrency hardening

### Application Features

- **FEAT-01**: Bulk import for historical transactions
- **FEAT-02**: Tax-year filtering and reporting
- **FEAT-03**: Broker statement reconciliation
- **FEAT-04**: Transaction audit log / soft deletes

### Test Coverage

- **TEST-01**: FIFO allocation unit tests (`record_sale()`)
- **TEST-02**: View tests (AJAX forms, permission filtering)
- **TEST-03**: Cross-user data isolation integration tests

## Out of Scope

Explicitly excluded from this milestone. Documented to prevent scope creep.

| Feature | Reason |
|---------|--------|
| SQLite → PostgreSQL migration | Single user, low write volume — CONCERNS.md's write-contention risk doesn't materialize at this load |
| Multi-user support | This instance is for a single owner only |
| New application features (bulk import, tax-year filtering, reconciliation) | This is a deployment-only milestone; app is already feature-complete |
| Full observability stack (Prometheus/Grafana/ELK) | Disproportionate resource cost on a Pi 4 for a single-user hobby app |
| Container orchestration (Docker Compose, k3s) | Pure overhead for two systemd services on one machine |
| CI/CD pipeline / zero-downtime deploys | Deploys are infrequent and manual; a few seconds of restart downtime is a non-issue for a single user |
| Cloudflare paid tier | Free tier (5 WAF rules, 1 rate-limit rule, Bot Fight Mode, Access up to 50 users) already covers this threat model |
| MFA/SSO identity provider for Cloudflare Access | Massive setup overhead for exactly one user; Access's built-in one-time-PIN email login is sufficient |
| Local reverse proxy (nginx/Caddy) | Cloudflare's edge already terminates TLS and provides WAF/DDoS/CDN; a local proxy is extra attack surface and a second process for zero benefit at this scale |

## Traceability

Which phases cover which requirements. Confirmed during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| SETTINGS-01 | Phase 1 | Complete |
| SETTINGS-02 | Phase 1 | Complete |
| SETTINGS-03 | Phase 1 | Complete |
| SETTINGS-04 | Phase 1 | Complete |
| PROC-01 | Phase 2 | Pending |
| PROC-02 | Phase 2 | Pending |
| PROC-03 | Phase 2 | Pending |
| SEC-01 | Phase 3 | Pending |
| SEC-02 | Phase 3 | Pending |
| BACKUP-01 | Phase 4 | Pending |
| BACKUP-02 | Phase 4 | Pending |
| BACKUP-03 | Phase 4 | Pending |
| DEPLOY-01 | Phase 5 | Pending |
| DEPLOY-02 | Phase 5 | Pending |
| DEPLOY-03 | Phase 5 | Pending |
| DEPLOY-04 | Phase 5 | Pending |
| DEPLOY-05 | Phase 5 | Pending |
| EDGE-01 | Phase 6 | Pending |
| EDGE-02 | Phase 6 | Pending |
| EDGE-03 | Phase 6 | Pending |
| EDGE-04 | Phase 6 | Pending |
| EDGE-05 | Phase 6 | Pending |

**Coverage:**

- v1 requirements: 22 total
- Mapped to phases: 22
- Unmapped: 0 ✓

---
*Requirements defined: 2026-07-19*
*Last updated: 2026-07-19 after initial definition*
