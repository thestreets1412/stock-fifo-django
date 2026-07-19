# Feature Research

**Domain:** Self-hosted single-user Django deployment operations (Raspberry Pi 4 + Cloudflare Tunnel)
**Researched:** 2026-07-19
**Confidence:** MEDIUM

This is an operational-features research pass, not application-features. The "user" of these deployment features is the app's single owner-operator. Findings cover process supervision, log handling, backup, Cloudflare Access/Zero Trust, Cloudflare Tunnel's built-in security controls, and monitoring — scoped to what a careful hobbyist should run, not what an enterprise SRE team would run.

## Feature Landscape

### Table Stakes (Users Expect These)

Things a "safe, reliable single-user home deployment" cannot ship without. Missing these = the deployment is fragile or actively unsafe, not just less polished.

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Gunicorn (or equivalent WSGI server) run as a systemd service, not `runserver` or a bare foreground process | `runserver` is not production-safe (no worker model, serves media insecurely, single-threaded); a bare `gunicorn` process dies when the SSH session closes and never restarts after a power blip/reboot — which Pi's on a home network will experience | LOW | `Restart=on-failure` (or `always`), dedicated non-root system user, `WantedBy=multi-user.target` so it starts on boot. Verify by rebooting the Pi once and confirming the app comes back without manual intervention. |
| Local reverse proxy (Caddy or nginx) in front of gunicorn, serving `/static/` and `/media/` directly | Directly answers the CONCERNS.md flag that Django serves media via `re_path(...serve...)` — not production-safe, and bypasses `LoginRequiredMixin` at the URL level since the raw serve view has no owner check | LOW–MEDIUM | Caddy has a simpler config than nginx for this project's scale (`file_server` + `reverse_proxy`, no cert config needed since Cloudflare Tunnel already terminates TLS at the edge). Moving media off Django's serve view fixes the "not production-safe" issue in CONCERNS.md but does NOT restore per-owner access control — see Dependency Notes. |
| `cloudflared` run as a systemd service with `Restart=on-failure` | If the tunnel process dies (crash, network blip, Pi update), the app becomes unreachable from the internet even though it's running locally — indistinguishable to the user from the whole Pi being down | LOW | `cloudflared service install` sets this up automatically on most OSes; verify it survives a reboot alongside gunicorn. |
| `DEBUG=False`, `SECURE_SSL_REDIRECT`, `SESSION_COOKIE_SECURE`, `CSRF_COOKIE_SECURE`, `SECURE_HSTS_SECONDS`, `SECURE_PROXY_SSL_HEADER`, real `CSRF_TRUSTED_ORIGINS` (not the placeholder) | Already flagged as Active requirements in PROJECT.md / immediate items in CONCERNS.md; without `SECURE_PROXY_SSL_HEADER` Django can't tell the request came in over HTTPS (Cloudflare Tunnel proxies HTTP to the origin), breaking secure-cookie and HSTS logic | LOW | This is app-config, not infra, but it's a hard prerequisite for the rest of this list to matter — a secure tunnel in front of an insecure Django config is false confidence. |
| File upload validation on evidence images (extension allowlist + size cap) | Already flagged as a CONCERNS.md security gap; an internet-reachable upload endpoint with no size cap is a disk-fill / DoS vector on a Pi's limited storage, and no extension check on an `ImageField` means a crafted file could still be accepted | LOW | `FileExtensionValidator` + `clean_evidence()` size check + `FILE_UPLOAD_MAX_MEMORY_SIZE`. Directly relevant once the app is internet-facing rather than LAN-only. |
| Automated, off-device SQLite + media backup (cron-driven) | SQLite lives as a single file on the Pi's SD card; SD cards fail without warning, and this app is the sole record of the owner's FIFO cost-basis/tax data — losing it is not a "restart the service" problem, it's data loss with financial consequence | LOW–MEDIUM | Use `sqlite3 db.sqlite3 "VACUUM INTO '/backup/path'"` (safe under concurrent access) or `.backup`, never `cp` on a live db file. Compress and copy the backup (and the `media/` evidence directory) to somewhere off the Pi — cloud storage, another machine, even a periodic manual pull — since a backup that only lives on the same SD card doesn't protect against card failure. |
| Deployment runbook (already an Active requirement in PROJECT.md) | Single operator, infrequent deploys — without a written runbook, recovering from a Pi reboot/power outage/SD card swap becomes a from-memory exercise under stress | LOW | Should cover: bringing gunicorn/cloudflared back up, restoring from backup, rotating `SECRET_KEY`/`.env` if compromised, and the exact `.env` variables required. |
| Non-root process user for gunicorn and cloudflared | Standard Linux hardening; if either process is compromised, running as root gives an attacker full Pi control instead of just app/tunnel access | LOW | One `adduser --system` call; systemd `User=`/`Group=` directives. |

### Differentiators (Meaningfully Raises the Deployment's Quality Bar)

Not required to be "safe and reliable," but each closes a real gap a single-user home deployment commonly has, at low-to-moderate effort.

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Cloudflare Access (Zero Trust, free tier) in front of the Cloudflare Tunnel hostname | Adds an identity check at Cloudflare's edge before any request reaches the Pi at all — defense-in-depth against credential stuffing/brute force on Django's own login, and against Django login bugs being the only thing standing between the internet and the FIFO ledger. Free tier supports up to 50 users (single user fits trivially) with one-time-PIN email auth out of the box, no IdP needed | LOW | Configured entirely in the Zero Trust dashboard as a policy on the tunnel hostname — no app code changes. This is the single highest-value/lowest-effort item in this list given the "extra auth layer in front of Django login" ask in the milestone context. |
| Cloudflare WAF custom rules + Bot Fight Mode (free tier: 5 custom rules) | Blocks obviously malicious/scanning traffic (SQLi/XSS patterns, known bad bots) before it reaches the Pi's limited CPU, at zero cost | LOW | Configure once in the Cloudflare dashboard. Bot Fight Mode is a single toggle. |
| Cloudflare rate limiting rule (free tier: 1 rule) targeted at `/accounts/login/` (or wherever Django's login lives) | Free tier only allows one rule, so spend it where it matters most: throttling login attempts blunts brute-force against Django's own auth, complementing (or substituting for) Cloudflare Access if Access is skipped | LOW | If Cloudflare Access is enabled, this rule becomes lower priority (Access already gates the whole app) — see Dependency Notes. |
| `log2ram` or a `journald` `SystemMaxUse` cap | Reduces SD card write wear from ongoing gunicorn/cloudflared/system logs, extending the SD card's working life on hardware that's otherwise annoying to re-flash | LOW | Genuinely optional — this is a longevity/maintenance-burden improvement, not a correctness or security fix. Worth doing once, not urgent. |
| External uptime check (Uptime Kuma self-hosted elsewhere, or a free hosted status-check service) pinging the public Cloudflare Tunnel hostname | Tells the owner the app went down *before* they notice by trying to use it — meaningfully different signal from "checked the Pi's systemd status," since it exercises the entire path (Cloudflare edge → tunnel → gunicorn) | LOW–MEDIUM | Must run off the Pi (a phone-based free checker, a $0 tier of a hosted status service, or a container on another machine) — a monitor that lives on the same device it's monitoring can't tell you the device itself is down. |
| Healthchecks.io-style dead-man's-switch ping at the end of the backup cron job | Silent backup failure is the worst kind of failure — the owner only discovers it when they need a backup that was never actually taken. A cron job that pings a URL on success, with alerting if the ping doesn't arrive on schedule, closes that gap | LOW | Free tier of healthchecks.io (or self-hosted) covers a single cron job easily. Pairs directly with the backup table-stakes item above — don't add this without the backup existing first. |
| WatchedFileHandler + logrotate for app-level Django logs (if the app writes its own log file beyond what systemd/journald captures) | Avoids the classic Django-in-production failure mode where log rotation silently stops writing to the rotated-away file handle | LOW–MEDIUM | Only relevant if the app is configured to log to a file at all; for a single-user low-traffic app, relying on `journald` capture of gunicorn's stdout/stderr (with a `SystemMaxUse` cap) is simpler and sufficient — see Anti-Features. |

### Anti-Features (Over-Engineering to Deliberately Avoid)

Patterns that make sense at team/enterprise scale but add operational burden without proportionate benefit for a single-user hobby Pi deployment.

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|------------------|-------------|
| Full observability stack (Prometheus + Grafana + node_exporter, ELK/Loki for logs) | "Real" production deployments have dashboards and metrics | A Pi 4 has limited RAM/CPU; running a metrics/logging stack alongside the app itself competes for the same constrained resources it's supposed to be monitoring, and nobody is paging an on-call rotation for a single-user hobby app | `journalctl` for ad-hoc log inspection, plus one lightweight external uptime check (Uptime Kuma/hosted) and one dead-man's-switch ping for backups — covers "is it up" and "did the backup run" with near-zero resource cost |
| Migrating SQLite to PostgreSQL as part of this deployment milestone | "Production databases use Postgres" | Already explicitly Out of Scope in PROJECT.md — single user, low write volume; CONCERNS.md's write-contention risk doesn't materialize at this load. Doing it now expands scope well beyond "deploy the existing app" | Keep SQLite; revisit only if usage patterns actually show contention (flagged in CONCERNS.md as a future risk, not a current one) |
| Cloudflare paid tier (Pro/Business) for advanced WAF managed rulesets, multi-rule rate limiting, ML anomaly detection | "More security is always better" | Budget constraint explicitly stated in PROJECT.md ("prefer... Cloudflare's free tier"); the free tier's 5 WAF rules + 1 rate-limit rule + Bot Fight Mode + Access already cover the realistic threat model for a single-user financial-tracker with no public signup | Free tier WAF/rate-limit/Access as documented above; revisit only if concrete abuse is observed |
| Container orchestration (Docker Compose with multiple services, or Kubernetes/k3s) for a single Django app + reverse proxy | "Containers are the modern deployment standard" | Adds an entire abstraction layer (image builds, volume mounts for SQLite persistence, container networking) for what is two systemd services on one machine; on a Pi 4 this is pure overhead with no corresponding benefit at single-user scale | Bare systemd services for gunicorn and cloudflared (and Caddy/nginx if used) — simpler to debug, simpler to document in the runbook, no image-build step to maintain |
| CI/CD pipeline with automated deploys, blue-green or zero-downtime deployment strategies | Standard for team projects with frequent releases | This app is feature-complete per PROJECT.md; deploys will be infrequent and manual (git pull + service restart is acceptable at this cadence). A few seconds of downtime during a manual restart is a non-issue for a single user who controls when they deploy | A short section in the deployment runbook: `git pull`, `migrate`, `collectstatic`, `systemctl restart gunicorn` |
| Multi-factor identity provider integration (SAML/OIDC via Okta/Entra) for Cloudflare Access | "Enterprise Zero Trust setups use SSO" | Massive setup overhead (registering an IdP app, managing SAML metadata) for exactly one user | Cloudflare Access's built-in one-time-PIN email login (or a social IdP like Google/GitHub if preferred) — same defense-in-depth benefit, zero IdP infrastructure |
| Custom audit-log / soft-delete system for transaction history (flagged in CONCERNS.md as "Missing Critical Feature") | Sounds like good practice for financial data | This is an *application* feature, not a deployment feature — explicitly out of scope for a deployment-only milestone per PROJECT.md ("New app features... out of scope") | Leave in CONCERNS.md for a future milestone; the automated off-device backup (table stakes above) is the deployment-appropriate mitigation for accidental data loss in the meantime |

## Feature Dependencies

```
Django hardened settings (DEBUG=False, SECURE_*, CSRF_TRUSTED_ORIGINS)
    └──requires──> Real domain acquired (PROJECT.md Active item)
    └──enables──> Cloudflare Tunnel routing traffic safely to Django

Reverse proxy (Caddy/nginx) serving /static /media
    └──requires──> gunicorn running as systemd service (proxy has something to forward to)
    └──replaces──> Django's re_path media serve view (CONCERNS.md gap)
    └──reopens──> Owner-only access control on evidence media
                     (moving serving to the proxy drops the LoginRequiredMixin check
                      that (partially) gated /media/ before — must be re-solved,
                      e.g. signed/expiring URLs or an authenticated Django view that
                      streams the file, not a bare static file_server on /media/)

Off-device SQLite + media backup (cron)
    └──enables──> Healthchecks.io dead-man's-switch ping (nothing to monitor without the backup existing)

Cloudflare Tunnel running (cloudflared systemd service)
    └──requires──> Real domain + DNS configured in Cloudflare
    └──enables──> Cloudflare Access policy (Access wraps a tunnel hostname)
    └──enables──> Cloudflare WAF / rate limiting rules (apply to the proxied hostname)

Cloudflare Access (Zero Trust) enabled
    └──reduces priority of──> Cloudflare's 1 free rate-limit rule on /login
                                 (if Access already gates all traffic with edge auth,
                                  brute-forcing Django's login becomes unreachable
                                  without first passing Access — the rate-limit rule
                                  is then better spent elsewhere, e.g. general path abuse)

External uptime monitor (Uptime Kuma / hosted)
    └──conflicts with──> Running the monitor ON the same Pi being monitored
                            (can't detect "the whole Pi is down" from inside the Pi)
```

### Dependency Notes

- **Reverse proxy reopens the media access-control gap:** CONCERNS.md flags Django's current media-serve view as "not production-safe," but its `LoginRequiredMixin` gap is arguably worse if simply replaced by a bare `file_server /media/` directive in Caddy/nginx — that would serve evidence images to anyone with the URL, no login check at all. The reverse-proxy fix must pair with either (a) an authenticated Django view that streams the file after an owner check, with the proxy only handling `/static/` (compiled assets, safe to serve publicly), or (b) short-lived signed URLs generated by Django and validated by the proxy. Table-stakes claim above is scoped to `/static/`; `/media/` needs the access-control question resolved explicitly, not assumed away.
- **Cloudflare Access vs. the single free rate-limit rule:** these overlap in purpose (both blunt automated/brute-force attacks on login). If Access is adopted, the free rate-limit rule is better spent on a secondary target (e.g., a general request-flood rule) rather than `/login`, since Access already blocks unauthenticated traffic from ever reaching Django's login form.
- **Backup must precede monitoring the backup:** the dead-man's-switch pattern (Healthchecks.io-style) only has value once an automated backup cron job exists to monitor — sequence backup before its monitoring wrapper.
- **Domain acquisition gates almost everything Cloudflare-side:** per PROJECT.md, no domain is owned yet; `CSRF_TRUSTED_ORIGINS`, the Cloudflare Tunnel hostname, Access policy, WAF rules, and rate-limiting rules all attach to that domain and can't be finalized before it exists.

## MVP Definition

### Launch With (v1) — Table Stakes, matches PROJECT.md Active requirements

- [ ] Gunicorn as a systemd service (`Restart=on-failure`, non-root user, starts on boot) — required for the app to survive a Pi reboot/crash unattended
- [ ] `cloudflared` as a systemd service (`Restart=on-failure`, starts on boot) — required for continuous internet reachability
- [ ] Django production settings hardened (`DEBUG=False`, `SECURE_SSL_REDIRECT`, `SECURE_PROXY_SSL_HEADER`, secure cookies, HSTS, real `CSRF_TRUSTED_ORIGINS`) — already an Active PROJECT.md item
- [ ] Reverse proxy (Caddy recommended for simplicity) serving `/static/` directly, dynamic requests to gunicorn — closes the CONCERNS.md "media served through Django" gap for static assets
- [ ] Evidence media access resolved explicitly (authenticated streaming view or signed URLs) rather than a bare `file_server /media/` — closes the gap the reverse-proxy migration would otherwise reopen
- [ ] File upload validation (extension allowlist + size cap) on evidence images — already a CONCERNS.md immediate item, now more urgent once internet-facing
- [ ] Automated nightly cron backup of SQLite (`VACUUM INTO`) + `media/` directory, copied off the Pi to a second location — non-negotiable given this is the sole record of financial data on a single SD card
- [ ] Written deployment runbook covering cold-start after reboot/outage, restore-from-backup steps, and `.env` variable reference — already an Active PROJECT.md item

### Add After Validation (v1.x)

- [ ] Cloudflare Access (Zero Trust free tier) in front of the tunnel hostname — highest-value, lowest-effort addition; add once the base deployment is confirmed working, since it's dashboard-only configuration with no app changes
- [ ] Cloudflare WAF custom rules (5 free) + Bot Fight Mode — add alongside Access, same dashboard, same effort tier
- [ ] Cloudflare rate limiting (1 free rule) on the login path or general abuse pattern, prioritized against whatever Access does/doesn't cover
- [ ] External uptime monitor (off-Pi) pinging the public hostname — add once the deployment has been stable for a bit and the owner wants to stop manually checking
- [ ] Dead-man's-switch ping (Healthchecks.io-style) wrapping the backup cron — add immediately after the backup cron itself, same phase

### Future Consideration (v2+)

- [ ] `log2ram` / journald size caps for SD card longevity — pure maintenance-burden reduction, no functional urgency
- [ ] WatchedFileHandler + logrotate for app-level log files — only relevant if/when the app is configured to log to a file beyond what journald already captures from gunicorn's stdout/stderr
- [ ] SQLite → PostgreSQL migration, audit log/soft deletes, bulk import, tax-year filtering — all explicitly out of scope per PROJECT.md/CONCERNS.md; belong to a future application-features milestone, not this deployment milestone

## Feature Prioritization Matrix

| Feature | User Value | Implementation Cost | Priority |
|---------|------------|---------------------|----------|
| Gunicorn as systemd service | HIGH | LOW | P1 |
| cloudflared as systemd service | HIGH | LOW | P1 |
| Django hardened settings | HIGH | LOW | P1 |
| Reverse proxy for /static + resolved /media access | HIGH | MEDIUM | P1 |
| File upload validation | MEDIUM | LOW | P1 |
| Automated off-device backup | HIGH | MEDIUM | P1 |
| Deployment runbook | HIGH | LOW | P1 |
| Cloudflare Access (Zero Trust) | HIGH | LOW | P2 |
| Cloudflare WAF rules + Bot Fight Mode | MEDIUM | LOW | P2 |
| Cloudflare rate limiting (1 rule) | MEDIUM | LOW | P2 |
| External uptime monitor | MEDIUM | LOW | P2 |
| Dead-man's-switch on backup cron | MEDIUM | LOW | P2 |
| log2ram / journald caps | LOW | LOW | P3 |
| App-level log rotation (WatchedFileHandler) | LOW | MEDIUM | P3 |

**Priority key:**
- P1: Must have for launch (table stakes — a deployment without these is fragile or unsafe)
- P2: Should have, add when possible (differentiators — meaningfully raises the bar, low effort)
- P3: Nice to have, future consideration

## Competitor Feature Analysis

Not applicable in the traditional sense (single-user hobby deployment, no competitors) — the equivalent comparison here is reverse-proxy and monitoring tool choice.

| Concern | Option A | Option B | Our Approach |
|---------|----------|----------|--------------|
| Reverse proxy | nginx (mature, ubiquitous, more config surface) | Caddy (simpler config, less relevant auto-HTTPS since Cloudflare Tunnel terminates TLS) | Caddy — lower config/maintenance burden fits a single-operator hobby deployment better than nginx's flexibility, which isn't needed here |
| Uptime monitoring | Uptime Kuma (self-hosted, must run off-Pi to detect Pi-down) | Hosted free-tier status checker (zero infra, but another account to manage) | Either is fine; only requirement is it must run somewhere other than the Pi itself |
| Cron job monitoring | Healthchecks.io hosted free tier | Self-hosted healthchecks | Hosted free tier — avoids running yet another service just to monitor one cron job |

## Sources

- [How to Configure systemd for Gunicorn and Django](https://django-deployment.com/deploy/setup-systemd-for-gunicorn-django/) — MEDIUM confidence (web search, cross-corroborated pattern)
- [Set Up Django with Postgres, Nginx, and Gunicorn on Ubuntu — DigitalOcean](https://www.digitalocean.com/community/tutorials/how-to-set-up-django-with-postgres-nginx-and-gunicorn-on-ubuntu) — MEDIUM confidence
- [(Semi-)correct handling of log rotation in multiprocess Python applications](https://medium.com/@rui.jorge.rei/semi-correct-handling-of-log-rotation-in-multiprocess-python-applications-75c56eca6780) — MEDIUM confidence
- [Configure and use logrotate — Bitnami docs](https://docs.bitnami.com/aws/infrastructure/django/administration/configure-use-logrotate/) — MEDIUM confidence
- [Cron-based backup — Litestream](https://litestream.io/alternatives/cron/) — MEDIUM confidence
- [Backup strategies for SQLite in production — Oldmoe's blog](https://oldmoe.blog/2024/04/30/backup-strategies-for-sqlite-in-production/) — MEDIUM confidence
- [Pi Reliability: Reduce writes to your SD card — Chris Dzombak](https://www.dzombak.com/blog/2024/04/pi-reliability-reduce-writes-to-your-sd-card/) — MEDIUM confidence
- [Give Your Raspberry Pi SD Card A Break: Log To RAM — Hackaday](https://hackaday.com/2019/04/08/give-your-raspberry-pi-sd-card-a-break-log-to-ram/) — MEDIUM confidence
- [Cloudflare Access — Zero Trust Network Access](https://www.cloudflare.com/sase/products/access/) — MEDIUM confidence (official product page)
- [Overview · Cloudflare One docs](https://developers.cloudflare.com/cloudflare-one/) — MEDIUM confidence (official docs)
- [Rate limiting rules · Cloudflare WAF docs](https://developers.cloudflare.com/waf/rate-limiting-rules/) — MEDIUM confidence (official docs)
- [Cloudflare WAF: Free Tier Firewall Rules — SumGuy's Ramblings](https://sumguy.com/cloudflare-waf-rate-limiting/) — MEDIUM confidence
- [Uptime Kuma vs Healthchecks.io for Solo Self-Hosters](https://futurion.blog/self-hosting-uptime-kuma-vs-healthchecks-io-honest-trade-offs-for-solo-builders/) — MEDIUM confidence
- [Uptime Kuma — official site](https://uptime.kuma.pet/) — MEDIUM confidence
- [TIL: Using Caddy with Django apps instead of Nginx](https://rtl.chrisadams.me.uk/2023/01/til-using-caddy-with-django-apps-instead-of-nginx/) — MEDIUM confidence
- `.planning/PROJECT.md` and `.planning/codebase/CONCERNS.md` — HIGH confidence (curated, project-internal)

---
*Feature research for: self-hosted single-user Django deployment (Raspberry Pi 4 + Cloudflare Tunnel)*
*Researched: 2026-07-19*
