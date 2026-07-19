# Project Research Summary

**Project:** stock-fifo-django — self-hosted deployment milestone
**Domain:** Self-hosted single-user Django deployment (Raspberry Pi 4, Cloudflare Tunnel, SQLite)
**Researched:** 2026-07-19
**Confidence:** MEDIUM

## Executive Summary

This milestone is not "build a feature," it's "make an already-working local Django app safely and durably reachable from the internet for one user, on a Raspberry Pi 4, with no static IP and no port forwarding." All four research passes converge on the same shape of solution: Cloudflare Tunnel (`cloudflared`) dials out from the Pi to Cloudflare's edge, which terminates TLS and forwards plain HTTP over loopback to Gunicorn running the existing Django app unchanged; systemd supervises both processes; SQLite stays as the database. No reverse proxy (nginx or Caddy) sits between cloudflared and gunicorn — at single-user scale it is pure added attack surface and a second process to keep alive for zero measurable benefit, since Cloudflare's edge already provides TLS termination, WAF, DDoS protection, and CDN caching.

The recommended approach is: harden Django's production settings (`SECURE_PROXY_SSL_HEADER`, `SECURE_SSL_REDIRECT`, real `CSRF_TRUSTED_ORIGINS`, secure cookies) and validate them locally first; stand up Gunicorn as a systemd service bound to `127.0.0.1` and prove it works before any public exposure; close the two internet-facing security gaps already flagged in `CONCERNS.md` (unauthenticated media serving, missing upload validation) before going live; only then acquire the domain and wire up the named Cloudflare Tunnel as a systemd service; and put an off-device automated SQLite/media backup in place before calling any of it done, since SQLite-on-SD-card is a real, well-documented data-loss risk on Pi hardware. Cloudflare Access (free tier, edge-level auth) is the highest-value, lowest-effort follow-up hardening layer, added after the base deployment is confirmed stable.

The dominant risks are configuration mistakes that look like outages or security holes rather than code bugs: a missing `SECURE_PROXY_SSL_HEADER` causes an infinite HTTPS redirect loop; a placeholder `CSRF_TRUSTED_ORIGINS` silently 403s every POST form; an ad-hoc/Quick Tunnel setup dies on reboot; and — most consequential — media evidence files served via Django's raw `serve()` view become unauthenticated-readable to the entire internet the moment the tunnel goes live, because that view has no owner check today. Every one of these is a "looks done, isn't" trap best caught with an explicit verification step (curl tests, a real reboot, an unauthenticated fetch attempt) rather than assumed from "the homepage loads."

## Key Findings

### Recommended Stack

The stack is deliberately minimal: **gunicorn** (WSGI server, pinned `<27` for confirmed Python 3.13 support on the Pi's default Trixie image) replaces `runserver`; **cloudflared** (Cloudflare's official apt package, arm64-supported) is the only thing that talks to the outside world, running as a named-tunnel systemd service (never a Quick Tunnel in production); **whitenoise** serves static files directly from the gunicorn process, eliminating any need for a second server just for `/static/`; and **systemd** (already present on Raspberry Pi OS Lite) supervises both processes — no supervisord/pm2/Docker needed for two processes on one box. `django-sendfile2` and any TLS/certbot tooling are explicitly *not* needed: TLS terminates at Cloudflare's edge, and media authorization should be handled by an authenticated Django view, not a sendfile/proxy handoff (see Architecture Approach below for why no proxy is needed at all).

**Core technologies:**
- gunicorn 26.0.0 — WSGI server for the existing synchronous Django app; right-sized vs. uWSGI/ASGI servers that add unneeded complexity here
- cloudflared (latest apt) — outbound-only tunnel daemon; publishes the Pi without opening router ports, terminates nothing itself (edge does that)
- whitenoise 6.12.x — serves `/static/` compressed and cache-busted from within the gunicorn process, no second server needed
- systemd (OS-provided) — process supervision, boot-time start, crash auto-restart for both gunicorn and cloudflared

### Expected Features

This is an operational/deployment feature set, not application features — "users" here means the single owner-operator.

**Must have (table stakes):**
- Gunicorn and cloudflared each as systemd services with `Restart=on-failure`, non-root user, boot-start — verified by an actual Pi reboot, not just `systemctl enable`
- Django production settings hardened: `DEBUG=False` (fail-closed default), `SECURE_SSL_REDIRECT`, `SECURE_PROXY_SSL_HEADER`, secure cookies, real `CSRF_TRUSTED_ORIGINS`
- Evidence media access resolved via an **authenticated Django view** (login-required, owner-scoped, streaming the file) — not a bare proxy `file_server` directive (see reconciliation note below)
- File upload validation (extension allowlist + size cap) on evidence images
- Automated, off-device (not just off-process) SQLite + media backup via cron, using `VACUUM INTO`/`.backup`, never a raw `cp` on a live file
- A written deployment runbook covering cold-start, restore-from-backup, and `.env` reference

**Should have (differentiators, add after base deployment is stable):**
- Cloudflare Access (Zero Trust free tier) in front of the tunnel hostname — dashboard-only config, no app changes, adds edge-level identity check before any request reaches the Pi
- Cloudflare WAF custom rules + Bot Fight Mode, and one rate-limiting rule (free tier caps: 5 WAF rules, 1 rate-limit rule)
- External uptime monitor (must run off the Pi) and a dead-man's-switch ping wrapping the backup cron

**Defer (v2+, explicitly out of scope for this milestone):**
- Full observability stack (Prometheus/Grafana/ELK) — resource cost disproportionate to a single-user Pi 4
- SQLite → PostgreSQL migration — already out of scope per PROJECT.md
- Container orchestration, CI/CD pipelines, MFA/SSO identity providers — enterprise patterns with no proportionate benefit at this scale
- `log2ram`/logrotate tuning — pure maintenance-burden reduction, not urgent

### Architecture Approach

Request flow: Browser → Cloudflare Edge (TLS termination, WAF, sets `X-Forwarded-Proto: https`) → outbound tunnel connection → `cloudflared` on the Pi (matches `config.yml` ingress rules) → plain HTTP over loopback only → Gunicorn bound to `127.0.0.1:8000` → unchanged Django app → SQLite. The critical trust boundary is that Gunicorn is reachable *only* via loopback from cloudflared — nothing else on the LAN can reach it or forge the `X-Forwarded-Proto` header, which is what makes it safe for Django to trust that header for `SECURE_SSL_REDIRECT`/secure-cookie logic.

**Major components:**
1. Cloudflare Edge — TLS termination, WAF/DDoS, sets forwarded headers (managed entirely via dashboard, not app code)
2. cloudflared (systemd service) — outbound tunnel, ingress-rule routing to local Gunicorn port, no inbound port ever opened
3. Gunicorn (systemd service, bound to `127.0.0.1`) — WSGI process running the unchanged Django app
4. Django app — no code changes for the tunnel itself; only settings hardening and the media-serving fix (below)
5. systemd — independent supervision of the two services; one dependency edge (cloudflared can start before gunicorn is up, will just 502 briefly)

**Reconciling the reverse-proxy question (STACK.md/ARCHITECTURE.md vs. FEATURES.md):** STACK.md and ARCHITECTURE.md both conclude no local reverse proxy (nginx or Caddy) should be introduced for this deployment — cloudflared should point directly at gunicorn on `127.0.0.1`, since Cloudflare's edge already handles TLS, WAF, and static-asset caching, and a local proxy would just be another systemd unit and attack surface for a single-user app. FEATURES.md initially frames a Caddy reverse proxy as the fix for the known media-serving gap (Django's `re_path`-mounted `serve()` view has no owner check), but FEATURES.md's own Dependency Notes section flags that a bare `file_server /media/` directive in that proxy would *reopen* the access-control gap, since a plain static-file directive has no concept of per-owner permission. **This synthesis resolves the tension in favor of STACK.md/ARCHITECTURE.md: no reverse proxy is needed for this deployment at all.** The correct fix for the media gap is a Django-level change — a `login_required`, owner-scoped view (following the `LoginRequiredMixin` pattern already used elsewhere in the app) that streams the evidence file via `FileResponse` after checking `request.user` owns it, replacing the raw `re_path(...serve...)` mapping. This closes the gap without adding any new process, and is consistent with PITFALLS.md's own recommended "app-level fix." Static assets (`/static/`) are served via whitenoise from within the gunicorn process — also with no proxy involved. Introduce nginx/Caddy only in the future if the Pi hosts multiple local services and needs local path-based routing beyond what Cloudflare Tunnel's own ingress rules already provide — explicitly out of scope now.

### Critical Pitfalls

1. **Missing `SECURE_PROXY_SSL_HEADER` → infinite redirect loop** — Django can't tell the request was HTTPS (it only ever sees plain loopback HTTP from cloudflared); if `SECURE_SSL_REDIRECT` is on without this header set, the site becomes completely unreachable. Set `SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')` before enabling the redirect, and verify with `curl -H "X-Forwarded-Proto: https"` locally before go-live.
2. **`CSRF_TRUSTED_ORIGINS` left as placeholder or scheme-mismatched** — every POST (login, buy/sell, evidence upload) silently 403s; must be the real domain with `https://` scheme, sourced from `.env` via the existing `python-decouple` pattern, and smoke-tested with a real form submission post-go-live (GET pages loading fine says nothing about this).
3. **Unauthenticated media access (evidence uploads)** — the single highest-severity gap: once tunneled to the internet, Django's raw `serve()` view at `/media/` has no owner check, exposing personal financial evidence files to anyone who can guess/enumerate a filename. Must be fixed with an authenticated, owner-scoped Django view (see Architecture reconciliation above) before the tunnel routes public traffic — this is a go-live blocker, not a nice-to-have.
4. **SQLite corruption from unclean power loss on SD card** — Pi has no UPS by default; enable WAL mode, and treat an automated, tested, off-device backup as the actual mitigation (not a "corruption-proof" primary copy).
5. **`cloudflared` run ad-hoc or as a Quick Tunnel** — dies on reboot/SSH-close, or gets a random unmemorable URL every restart; must be a named tunnel with a systemd service, verified with an actual Pi reboot test, not just `systemctl enable`.

## Implications for Roadmap

Based on research, suggested phase structure (dependency-ordered — local/testable-in-isolation work first, public-exposure work last):

### Phase 1: Django Production Settings Hardening
**Rationale:** Pure code changes, independently testable locally with `DEBUG=True`/`DEBUG=False` toggling, no infrastructure dependency — should be solid before anything is internet-reachable so that CSRF/redirect debugging doesn't get conflated with tunnel/DNS issues later.
**Delivers:** `SECURE_PROXY_SSL_HEADER`, `SECURE_SSL_REDIRECT`, secure cookie flags, HSTS settings, `.env`-driven `CSRF_TRUSTED_ORIGINS`/`ALLOWED_HOSTS` scaffolding (real values pending domain acquisition), `DEBUG` fail-closed default, `python manage.py check --deploy` passing clean.
**Addresses:** Table-stakes settings items from FEATURES.md.
**Avoids:** Pitfall 1 (redirect loop), Pitfall 2 (CSRF placeholder), Pitfall 5 (DEBUG leaking to prod).

### Phase 2: Gunicorn + systemd Process Supervision
**Rationale:** Validates the app runs correctly under a real WSGI server (worker/thread behavior differs from `runserver`) while still only reachable from the Pi itself — cheap to debug in isolation before any tunnel exists.
**Delivers:** `gunicorn` in `requirements.txt`, manual verification (`gunicorn config.wsgi:application --bind 127.0.0.1:8000`), then a `gunicorn.service` systemd unit with `Restart=on-failure`, non-root user, boot-start — reboot-tested.
**Uses:** gunicorn from STACK.md.
**Implements:** Component 3 (Gunicorn) and the systemd supervision pattern from ARCHITECTURE.md.

### Phase 3: Close Internet-Facing Security Gaps
**Rationale:** These gaps (media serving, upload validation) are low-risk on a LAN-only deployment but become real exposure the moment the app is public — must be closed before Phase 5 wires up the tunnel, but doesn't depend on the tunnel/domain existing, so can run in parallel with Phase 2.
**Delivers:** Authenticated, owner-scoped Django view replacing the raw `re_path(...serve...)` media mapping (no reverse proxy — see reconciliation above); `FileExtensionValidator` + size cap on evidence uploads; whitenoise wired in for `/static/`.
**Addresses:** The "review of Django's direct media-file serving" Active requirement in PROJECT.md; file-upload validation table-stakes item.
**Avoids:** Pitfall 3/6 (unauthenticated media exposure) — the single highest-severity item in this research.

### Phase 4: Backup and Data Durability
**Rationale:** Independent of the tunnel/domain; should exist before go-live since SQLite-on-SD-card corruption is a real, documented risk once the app is running 24/7 unattended.
**Delivers:** WAL mode enabled, nightly cron `VACUUM INTO`/`.backup` of SQLite + `media/` directory, copied off the Pi to a second location, with at least one test restore performed.
**Addresses:** Automated off-device backup table-stakes item from FEATURES.md.
**Avoids:** Pitfall 3 (SQLite corruption / data loss).

### Phase 5: Domain Acquisition, Cloudflare Tunnel, and Go-Live
**Rationale:** Everything before this is a prerequisite that must be correct first — misconfigured `ALLOWED_HOSTS`/`CSRF_TRUSTED_ORIGINS` at this point manifests as confusing 400/403 errors that look like tunnel problems but aren't. This is the step that actually exposes the app to the internet.
**Delivers:** Domain acquired and added to Cloudflare; `ALLOWED_HOSTS`/`CSRF_TRUSTED_ORIGINS` finalized with real values; named Cloudflare Tunnel created, `config.yml` with mandatory catch-all `404` ingress rule, `cloudflared` installed as a systemd service and reboot-tested; end-to-end smoke test (login, buy/sell POST, PDF/CSV export, evidence upload/view) over the real HTTPS domain; deployment runbook written.
**Addresses:** Remaining table-stakes items (cloudflared as systemd service, real CSRF origins, runbook).
**Avoids:** Pitfall 4 (ad-hoc/Quick Tunnel), and validates Phases 1–3 actually work under real public traffic.

### Phase 6 (optional follow-up, not blocking go-live): Edge-Level Hardening
**Rationale:** Dashboard-only configuration, no app code changes — highest value-per-effort, but not required to safely go live since Phases 1–5 already close the critical gaps.
**Delivers:** Cloudflare Access (Zero Trust free tier) on the tunnel hostname, WAF custom rules + Bot Fight Mode, one rate-limiting rule, external uptime monitor, dead-man's-switch ping on the backup cron.

### Phase Ordering Rationale

- Settings and process-supervision work (Phases 1–2) is entirely local to the Pi and testable without any public exposure — deliberately sequenced before the domain/tunnel (Phase 5) so that security-header behavior (CSRF, secure cookies, SSL redirect) isn't being debugged simultaneously with DNS propagation/tunnel connectivity issues, which are a different failure class with different symptoms.
- The media-serving fix (Phase 3) is explicitly called out as a go-live blocker in both FEATURES.md and PITFALLS.md and must land before Phase 5 makes the app internet-reachable — sequenced early since it's a pure Django-level change with no infrastructure dependency, so it can run in parallel with Phase 2.
- Backup (Phase 4) has no hard dependency on the tunnel and protects against a risk (SD card failure/corruption) that exists independent of internet exposure — sequenced before go-live rather than after, since "backup before go-live" is cheaper than "backup after an incident."
- Domain/tunnel (Phase 5) is deliberately last among the required phases because it's the one step that can't be tested in isolation — it depends on every other phase being correct, and getting it wrong manifests as confusing errors that look like earlier-phase bugs.
- Edge-level hardening (Phase 6) is explicitly sequenced after a stable base deployment per FEATURES.md's own MVP definition ("Add After Validation") — it's dashboard-only and low-risk to add later, unlike the phases before it.

### Research Flags

Phases likely needing deeper research during planning:
- **Phase 5 (Domain + Tunnel + Go-Live):** Cloudflare Tunnel `config.yml`/named-tunnel setup is well-documented in official docs but has Pi-specific apt-repo nuances (Trixie vs. bookworm codename) that should be re-verified with `lsb_release -cs` at actual deploy time rather than assumed from this research.
- **Phase 2 (Gunicorn/systemd):** ARM64 wheel availability for `Pillow`/`cryptography` (Pitfall 7) should be verified with a clean `pip install -r requirements.txt` dry-run directly on the Pi hardware before relying on this phase's plan — a Pi-specific bug fix already appears in recent commit history, suggesting this has bitten the project before.

Phases with standard patterns (skip research-phase):
- **Phase 1 (Settings hardening):** Django's official deployment checklist and `SECURE_PROXY_SSL_HEADER`/CSRF documentation are authoritative and directly applicable — no ambiguity here.
- **Phase 3 (Security gaps):** The authenticated-view pattern for media serving is a standard `LoginRequiredMixin`-equivalent Django pattern already used elsewhere in this codebase.
- **Phase 4 (Backup):** SQLite `.backup`/`VACUUM INTO` and WAL mode are official SQLite-documented, low-ambiguity patterns.

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | MEDIUM | Official Cloudflare/Django/PyPI docs cross-checked directly (gunicorn PyPI classifiers verified); some Pi/ARM-specific details (apt codename, exact default Python version) flagged as needing on-device verification |
| Features | MEDIUM | Cross-referenced against project-internal `CONCERNS.md`/`PROJECT.md` (HIGH-confidence sources) plus multiple independent web sources for backup/monitoring/Cloudflare-tier specifics |
| Architecture | MEDIUM | Cross-checked across official Cloudflare docs, Django docs/forum threads, and multiple independent deployment write-ups; no single primary source covers this exact Pi+Tunnel+Django combination end-to-end |
| Pitfalls | MEDIUM | Web-sourced but cross-checked against official Django/SQLite/Cloudflare docs; no project-specific load testing was performed, so thermal/undervoltage findings (Pitfall 8) are general Pi 4 guidance, not measured on this specific unit |

**Overall confidence:** MEDIUM

### Gaps to Address

- **Reverse proxy question:** Resolved in this synthesis (no proxy needed; media fix is a Django view change) — flag to the roadmapper/planner that FEATURES.md's raw text still recommends a Caddy proxy and should not be followed literally; this SUMMARY.md's Architecture Approach section is the authoritative resolution.
- **Pi's actual Python/OS version:** STACK.md assumes Trixie/Python 3.13 but flags this should be confirmed with `python3 --version`/`lsb_release -cs` on the actual hardware before finalizing package pins — treat as a Phase 2/5 verification step, not an assumption to plan around blindly.
- **ARM64 wheel build risk for Pillow/cryptography:** Should be resolved with an early dry-run `pip install` on the Pi (Phase 2), not discovered at go-live.
- **Thermal/undervoltage behavior under sustained load (e.g., PDF report generation):** No project-specific measurement exists; treat as a go-live verification checklist item (`vcgencmd get_throttled`) rather than a design constraint requiring code changes.

## Sources

### Primary (HIGH confidence)
- [Security in Django | Django documentation](https://docs.djangoproject.com/en/6.0/topics/security/) — `SECURE_PROXY_SSL_HEADER`, CSRF, secure-cookie settings
- [Deployment checklist | Django documentation](https://docs.djangoproject.com/en/6.0/howto/deployment/checklist/)
- [Cloudflare Tunnel · Cloudflare Docs](https://developers.cloudflare.com/tunnel/) and [Cloudflare One docs](https://developers.cloudflare.com/cloudflare-one/) — tunnel architecture, systemd service setup, config.yml/ingress rules, Quick Tunnels
- [Write-Ahead Logging — SQLite official docs](https://sqlite.org/wal.html) and [How To Corrupt An SQLite Database File](https://www.sqlite.org/howtocorrupt.html)
- [gunicorn · PyPI](https://pypi.org/project/gunicorn/) — verified directly, version 26.0.0, Python 3.10–3.13 classifiers
- [Thermal testing Raspberry Pi 4 — Raspberry Pi official news](https://www.raspberrypi.com/news/thermal-testing-raspberry-pi-4/)
- `.planning/PROJECT.md` and `.planning/codebase/CONCERNS.md` — project-internal, curated

### Secondary (MEDIUM confidence)
- [Using WhiteNoise with Django](https://whitenoise.readthedocs.io/en/stable/django.html)
- [TIL: Using Caddy with Django apps instead of Nginx](https://rtl.chrisadams.me.uk/2023/01/til-using-caddy-with-django-apps-instead-of-nginx/)
- [Uptime Kuma vs Healthchecks.io for Solo Self-Hosters](https://futurion.blog/self-hosting-uptime-kuma-vs-healthchecks-io-honest-trade-offs-for-solo-builders/)
- [Django Forum — CSRF verification failed after putting behind SSL proxy](https://forum.djangoproject.com/t/csrf-verification-failed-request-aborted-after-putting-behind-ssl-proxy/29130)
- [Pi Reliability: Reduce writes to your SD card — Chris Dzombak](https://www.dzombak.com/blog/2024/04/pi-reliability-reduce-writes-to-your-sd-card/)

### Tertiary (LOW confidence)
- Various community install/blog guides for `cloudflared` on Raspberry Pi (apt-repo steps, Pi-specific quirks) — used only where corroborated by 2+ sources or an official doc

---
*Research completed: 2026-07-19*
*Ready for roadmap: yes*
