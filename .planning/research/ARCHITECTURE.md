# Architecture Research

**Domain:** Django app deployment behind Cloudflare Tunnel (home/Raspberry Pi self-hosting)
**Researched:** 2026-07-19
**Confidence:** MEDIUM (cross-checked across Cloudflare official docs, Django docs/forum, and multiple independent deployment write-ups; no single source is a primary spec for this exact combination)

## Standard Architecture

### System Overview

```
┌───────────┐      HTTPS       ┌─────────────────────────────┐
│  Browser  │ ───────────────▶ │   Cloudflare Edge (global)   │
│ (any host)│ ◀─────────────── │  TLS term, WAF, DDoS, CDN    │
└───────────┘                  └───────────────┬──────────────┘
                                                │ 1 of 4 pre-established
                                                │ outbound QUIC/HTTP2
                                                │ connections (edge→origin,
                                                │ opened by cloudflared)
                                                ▼
                          ┌─────────────────────────────────────┐
                          │   Raspberry Pi 4 (home network)      │
                          │  ┌─────────────────────────────┐    │
                          │  │  cloudflared (systemd unit)  │    │
                          │  │  reads config.yml ingress    │    │
                          │  │  rules; no inbound port open │    │
                          │  └───────────────┬───────────────┘   │
                          │                  │ plain HTTP,        │
                          │                  │ loopback only      │
                          │                  ▼                    │
                          │  ┌─────────────────────────────┐    │
                          │  │ Gunicorn (WSGI, systemd unit)│    │
                          │  │ bound to 127.0.0.1:8000      │    │
                          │  │ (or unix socket)             │    │
                          │  └───────────────┬───────────────┘   │
                          │                  ▼                    │
                          │  ┌─────────────────────────────┐    │
                          │  │  Django app (config.wsgi)     │    │
                          │  │  portfolio/ views→services→   │    │
                          │  │  models → SQLite (db.sqlite3) │    │
                          │  └───────────────────────────────┘   │
                          └─────────────────────────────────────┘
```

### Component Responsibilities

| Component | Responsibility | Typical Implementation |
|-----------|----------------|-------------------------|
| Cloudflare Edge | TLS termination, WAF/DDoS filtering, CDN, sets `X-Forwarded-*` headers, terminates the public HTTPS connection so the Pi never needs its own cert | Managed by Cloudflare; configured via dashboard/DNS + Access policies (not app code) |
| cloudflared | Establishes outbound-only tunnel to the edge; proxies matched hostnames to a local service per `config.yml` ingress rules; runs as a systemd service so it survives reboot | `cloudflared` binary, `~/.cloudflared/config.yml`, one systemd unit (`cloudflared.service`) |
| Gunicorn (WSGI server) | Runs the actual Django process(es); handles concurrency (worker processes/threads), request timeouts, graceful restarts | `gunicorn config.wsgi:application --bind 127.0.0.1:8000`, managed by its own systemd unit |
| Django app | Business logic, auth, ORM, templates — unchanged from current app | `config/wsgi.py`, `portfolio/` (no code changes needed beyond settings) |
| systemd | Process supervision for both cloudflared and gunicorn: auto-start on boot, auto-restart on crash, structured logs via journalctl | Two unit files: `cloudflared.service` (installed by `cloudflared service install`), `gunicorn.service` (hand-written) |
| SQLite | Data store, unchanged for this milestone | `db.sqlite3` on local disk |

**No local reverse proxy (Nginx) is required for this project's scale.** See rationale below.

## Recommended Project Structure

This milestone does not change the Django project's internal folder layout (see `.planning/codebase/STRUCTURE.md` — `config/`, `portfolio/` stay as-is). What's new is *deployment* scaffolding, conventionally kept outside the Django project tree (or in a small `deploy/` folder if you want it version-controlled):

```
stock-fifo-django/
├── config/, portfolio/, manage.py, ...   # unchanged app code
├── deploy/                                # NEW — optional, for versioned deploy assets
│   ├── gunicorn.service                   # systemd unit template (not secrets)
│   ├── cloudflared-config.yml.example      # ingress rule template (no tunnel UUID/creds)
│   └── RUNBOOK.md                          # "how to bring the Pi back up" doc (per PROJECT.md Active requirement)
├── .env                                    # unchanged — gains real domain values, not committed
```

### Structure Rationale

- **No app-code changes for the tunnel itself:** cloudflared and Gunicorn are infrastructure, not application code — they live in systemd unit files and `~/.cloudflared/config.yml` on the Pi, not in the git repo (the tunnel's actual `config.yml` and credentials file must never be committed — they contain a tunnel secret).
- **`deploy/` folder (optional but recommended):** template versions of the systemd unit and ingress config, with secrets/UUIDs stripped, let you reconstruct the deployment after an SD-card failure — directly serving the "deployment runbook" requirement already in PROJECT.md's Active section.

## Architectural Patterns

### Pattern 1: Trust the edge, verify what it tells you

**What:** Cloudflare terminates TLS and forwards to your origin over its own encrypted tunnel; the origin (Gunicorn/Django) only ever sees plain HTTP on loopback. Django is told to trust one specific header (`X-Forwarded-Proto`) as the source of truth for "was this HTTPS," because the connection it actually sees is not.
**When to use:** Any time TLS terminates upstream of Django (true for Cloudflare Tunnel, and would also be true with Nginx-as-TLS-terminator).
**Trade-offs:** Simple and correct *only if* Django cannot be reached by any other path that could spoof the header. Because cloudflared connects to Gunicorn over `127.0.0.1` only (no LAN/public bind), nothing except cloudflared itself can present that header to Django — Cloudflare's edge overwrites/sets `X-Forwarded-Proto` itself, and the loopback-only path prevents a rogue LAN device from forging it.

**Example (settings.py — already partially in place per the uncommitted diff):**
```python
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')  # already added
CSRF_TRUSTED_ORIGINS = ["https://<real-domain>"]                # TODO real domain (Phase 4 per PROJECT.md)
ALLOWED_HOSTS = config('ALLOWED_HOSTS', cast=Csv())              # must include the real public hostname, not just localhost
SECURE_SSL_REDIRECT = not DEBUG                                  # flagged missing in CONCERNS.md — add this
```

### Pattern 2: Two independently-supervised systemd services, one dependency edge

**What:** cloudflared and Gunicorn are separate OS processes, each with its own systemd unit, each independently restartable. cloudflared depends on Gunicorn being reachable but should still *start* even if Gunicorn briefly isn't (it will just return 502s to the edge until Gunicorn comes up) — don't hard-fail one on the other.
**When to use:** Any headless/always-on box (Pi) where you need survive-reboot + survive-crash without a human SSHing in.
**Trade-offs:** Two units to manage instead of one, but each fails/restarts independently, which is easier to debug (`journalctl -u gunicorn` vs `journalctl -u cloudflared` are cleanly separated) than one supervisor process babysitting both.

**Example (`gunicorn.service`, illustrative):**
```ini
[Unit]
Description=Gunicorn for stock-fifo-django
After=network.target

[Service]
User=pi
WorkingDirectory=/home/pi/stock-fifo-django
EnvironmentFile=/home/pi/stock-fifo-django/.env
ExecStart=/home/pi/stock-fifo-django/.venv/bin/gunicorn config.wsgi:application --bind 127.0.0.1:8000 --workers 2
Restart=on-failure

[Install]
WantedBy=multi-user.target
```
Note: `EnvironmentFile=` with a `python-decouple`-style `.env` works for simple `KEY=value` files, but decouple's own `.env` parsing is what the app already uses at runtime via `config()` — gunicorn doesn't need to inject those vars itself as long as the process's CWD lets `python-decouple` find `.env`. Verify this at rollout time rather than assuming both mechanisms agree on parsing.

### Pattern 3: Ingress rules as the single hostname→service map

**What:** `cloudflared`'s `config.yml` ingress list is the only place that maps a public hostname to a local port; it must end in a catch-all `- service: http_status:404`.
**When to use:** Always, for any Cloudflare Tunnel deployment — this is not optional structure, it's how cloudflared resolves which local service to proxy to.
**Trade-offs:** None really — it's declarative and low-risk. The catch-all is easy to forget and causes cryptic startup errors if omitted.

**Example:**
```yaml
tunnel: <tunnel-uuid>
credentials-file: /home/pi/.cloudflared/<tunnel-uuid>.json

ingress:
  - hostname: stocks.example.com
    service: http://127.0.0.1:8000
  - service: http_status:404
```

## Data Flow

### Request Flow

```
Browser (HTTPS to stocks.example.com)
    ↓
Cloudflare Edge — TLS terminated here; WAF/DDoS applied;
sets X-Forwarded-Proto: https, X-Forwarded-For: <real client IP>, CF-Connecting-IP, Host: stocks.example.com
    ↓ (over pre-established outbound tunnel connection — no inbound port on the Pi)
cloudflared on the Pi — matches Host header against config.yml ingress rules
    ↓ (plain HTTP, loopback only)
Gunicorn (127.0.0.1:8000) — WSGI worker picks up the request
    ↓
Django SecurityMiddleware → SessionMiddleware → CommonMiddleware → CsrfViewMiddleware → AuthenticationMiddleware
    ↓
config/urls.py → portfolio/urls.py → View (existing app logic, unchanged)
    ↓
Response ← Django ← Gunicorn ← cloudflared ← Cloudflare Edge ← Browser
```

### Header Implications (the core of this research question)

| Setting | Why it matters here | Current state (per uncommitted settings.py diff) |
|---|---|---|
| `ALLOWED_HOSTS` | Django validates the `Host` header cloudflared forwards (which is the browser's original `Host`, e.g. `stocks.example.com`) against this list; a mismatch is a hard `400 Bad Request` before any view runs. | Currently `127.0.0.1,localhost` via `.env` default — **must add the real domain** once acquired (Active requirement in PROJECT.md, tracked as Phase 4 TODO). |
| `CSRF_TRUSTED_ORIGINS` | Django 4+ requires the full scheme+host (`https://stocks.example.com`) of any origin allowed to submit cross-origin-looking POSTs; because the tunnel means the browser's actual origin *is* the real domain (not `127.0.0.1`), this must match exactly or all POST forms (buy/sell) will 403. | Placeholder `https://placeholder.example.com` already in settings.py with an explicit TODO — flagged as immediate priority in CONCERNS.md. |
| `SECURE_PROXY_SSL_HEADER` | Without this, Django's `request.is_secure()` returns `False` even though the browser used HTTPS (because Gunicorn only ever sees plain HTTP from cloudflared) — breaks `SECURE_SSL_REDIRECT`, secure cookies, and any `{% if request.is_secure %}` logic, and can cause redirect loops if `SECURE_SSL_REDIRECT` is also on. | Already set to `('HTTP_X_FORWARDED_PROTO', 'https')` — correct, since Cloudflare sets this header automatically (no proxy config needed to add it, unlike a raw Nginx setup). |
| `SESSION_COOKIE_SECURE` / `CSRF_COOKIE_SECURE` | Should only be sent over HTTPS; correctly detected via the header above once `is_secure()` works. | Already conditional on `not DEBUG` — correct. |
| `SECURE_SSL_REDIRECT` | Forces plain-HTTP requests to redirect to HTTPS — but note cloudflared→Gunicorn is *always* plain HTTP by design, so this must rely on `SECURE_PROXY_SSL_HEADER` (not the literal loopback scheme) to avoid an infinite redirect loop. | **Missing** — explicitly flagged in CONCERNS.md ("`SECURE_SSL_REDIRECT` Not Enforced"). Add `SECURE_SSL_REDIRECT = not DEBUG` only after confirming `SECURE_PROXY_SSL_HEADER` works, or the Pi's local `runserver` HTTP dev flow will start redirect-looping too if `DEBUG` is ever accidentally `False` locally. |
| `X-Forwarded-For` / real client IP | Cloudflare sets this (and `CF-Connecting-IP`) automatically; Django doesn't currently use client IP for anything (no rate limiting/logging by IP visible in the codebase), so no `USE_X_FORWARDED_FOR` change is strictly required for this milestone, but note it for any future rate-limiting work. | Not currently consumed by the app — no action needed now. |

### Key Data Flows

1. **TLS termination happens once, at Cloudflare's edge — never on the Pi.** The Pi does not need its own TLS certificate, does not need Let's Encrypt/Certbot, and does not need port 443 open. This is the single biggest simplification Cloudflare Tunnel provides over a traditional Nginx+Certbot setup, and it directly satisfies the "no port forwarding, no exposed IP" constraint in PROJECT.md.
2. **The tunnel is outbound-only from the Pi's perspective.** cloudflared dials out to Cloudflare; nothing needs to be reachable inbound on the home router. This is what removes the port-forwarding requirement entirely (PROJECT.md constraint: "No port forwarding or static IP on the home network").
3. **Gunicorn↔cloudflared is loopback-only, plain HTTP, and untrusted by nothing else on the LAN.** Binding Gunicorn to `127.0.0.1` (not `0.0.0.0`) means even a compromised device on the home Wi-Fi cannot reach Django directly, bypassing Cloudflare's WAF/Access controls — this boundary is what makes trusting `X-Forwarded-Proto` blindly (Pattern 1) safe.

## Scaling Considerations

Explicitly *not* the concern for this milestone (PROJECT.md: single user, out of scope for multi-user/concurrency hardening) — included briefly since it affects the "should there be an Nginx" decision.

| Scale | Architecture Adjustments |
|-------|---------------------------|
| Single user (this milestone) | cloudflared → Gunicorn direct, no Nginx. Gunicorn 1–2 sync workers is plenty for a personal FIFO tracker on a Pi 4. |
| Small multi-user (future, out of scope) | Add Nginx in front of Gunicorn mainly for efficient static/media file serving (Django serving media directly is already flagged as not production-safe in CONCERNS.md) and to offload some request buffering from Gunicorn workers. |
| Not applicable here | This app will never need to scale past a handful of users per PROJECT.md — no further tiers are relevant. |

### Scaling Priorities

1. **First real bottleneck at this scale is SQLite write contention, not the tunnel or WSGI layer** — already flagged in CONCERNS.md as a known future risk, explicitly deferred out of this milestone.
2. **Second, if ever relevant:** Django directly serving media files (evidence uploads) under a public tunnel — already flagged in CONCERNS.md as "not production-safe"; worth a lightweight fix (e.g., a permission-checked serving view, or capping file size/type) within *this* milestone since PROJECT.md's Active requirements explicitly call out "review of Django's direct media-file serving under the tunnel."

## Anti-Patterns

### Anti-Pattern 1: Running `manage.py runserver` behind the tunnel

**What people do:** Point cloudflared straight at `python manage.py runserver 0.0.0.0:8000` since it's already what's running on the Pi today (per PROJECT.md context: "runs via `manage.py runserver` locally on the Pi").
**Why it's wrong:** Django's own docs are explicit that `runserver` "has not gone through security audits or performance tests" and is single-threaded — one slow request (e.g., a yfinance dashboard fetch that already has a 5s per-symbol timeout per the app's service layer) blocks every other concurrent request, including the owner's own next click. It also auto-reloads on file changes, which is undesirable for a stable always-on deployment.
**Do this instead:** Run Gunicorn (already Django-native, no new framework) as a systemd-supervised WSGI server bound to loopback, and point cloudflared's ingress rule at Gunicorn's port instead of runserver's.

### Anti-Pattern 2: Adding Nginx "just because tutorials show it"

**What people do:** Copy the generic "Nginx + Gunicorn + Django" tutorial stack (what most WebSearch results above default to) without questioning whether Nginx's role is actually needed when Cloudflare's edge already does TLS termination, static asset CDN caching, WAF, and DDoS protection.
**Why it's wrong:** For a single-user personal app on a resource-constrained Pi 4, an extra Nginx process is additional attack surface, additional systemd unit to supervise, and additional config to keep in sync with `ALLOWED_HOSTS`/`X-Forwarded-*` — for a benefit (static file serving efficiency, connection buffering) that's negligible at this traffic volume and this app's already-small static footprint (Bootstrap/Chart.js are CDN-loaded per ARCHITECTURE.md; local static assets are minimal CSS/JS).
**Do this instead:** Point cloudflared directly at Gunicorn (`http://127.0.0.1:8000`). Serve Django's own `STATIC_ROOT` via `collectstatic` + `whitenoise` middleware (a single `pip install` and one `MIDDLEWARE` line) if static-file performance ever becomes a concern, rather than standing up a second reverse-proxy process. Revisit Nginx only if this app grows into multi-service/multi-user territory (explicitly out of scope for this milestone).

### Anti-Pattern 3: Trusting `X-Forwarded-*` headers without a loopback-only origin

**What people do:** Set `SECURE_PROXY_SSL_HEADER` and call it done, without also ensuring the WSGI server is unreachable except via cloudflared.
**Why it's wrong:** If Gunicorn were bound to `0.0.0.0` (reachable from the LAN or, worse, misconfigured router), any client could forge an `X-Forwarded-Proto: https` header directly, tricking Django into treating an insecure request as secure — defeating the entire point of `SECURE_PROXY_SSL_HEADER`.
**Do this instead:** Bind Gunicorn to `127.0.0.1` (or a Unix socket) so cloudflared is the *only* possible path to Django, making the forwarded-header trust boundary airtight.

## Integration Points

### External Services

| Service | Integration Pattern | Notes |
|---------|----------------------|-------|
| Cloudflare (DNS + Tunnel) | `cloudflared` outbound daemon + `cloudflared tunnel route dns` CNAME record | Requires domain's nameservers on Cloudflare (or at least the zone added) before `route dns` will work — domain acquisition is a hard prerequisite, already reflected as a blocking Active requirement in PROJECT.md. |
| Frankfurter API / yfinance | Unchanged by this migration — both are outbound calls made *from* Django to third parties, unrelated to inbound tunnel routing | No settings interaction with the tunnel; already gracefully degraded per existing ARCHITECTURE.md. |

### Internal Boundaries

| Boundary | Communication | Notes |
|----------|----------------|-------|
| cloudflared ↔ Gunicorn | Plain HTTP over loopback (`127.0.0.1:8000` or Unix socket) | This is the one new internal boundary this milestone introduces; must not be exposed beyond loopback. |
| Gunicorn ↔ Django (WSGI) | In-process, unchanged (`config/wsgi.py:application`) | No app code changes required — Gunicorn is a drop-in replacement process manager for what `runserver` did locally. |
| systemd ↔ cloudflared / Gunicorn | Process supervision, auto-restart, boot-time start | Two independent units; this is what makes the deployment survive a Pi reboot/power outage without manual intervention — directly serving the "runbook after reboot" Active requirement in PROJECT.md. |

## Suggested Build/Rollout Order

Ordered by hard dependency, mapped to what's already done vs. still needed per PROJECT.md's Active requirements and the uncommitted `settings.py` diff:

1. **Settings hardening (mostly started already)** — Finish `config/settings.py`: keep the already-added `SECURE_PROXY_SSL_HEADER`, `SESSION_COOKIE_SECURE`/`CSRF_COOKIE_SECURE` (conditional on `DEBUG`), `SECURE_HSTS_SECONDS`; add the still-missing `SECURE_SSL_REDIRECT = not DEBUG` and `SECURE_HSTS_INCLUDE_SUBDOMAINS = not DEBUG` (both flagged in CONCERNS.md). Leave `CSRF_TRUSTED_ORIGINS`/`ALLOWED_HOSTS` as placeholders for now — they can't be finalized until step 5 (domain). *Why first:* these are pure code changes, independently testable locally with `DEBUG=True`, and don't depend on any infrastructure being up yet.
2. **WSGI server (Gunicorn)** — Add `gunicorn` to `requirements.txt`; verify `gunicorn config.wsgi:application --bind 127.0.0.1:8000` serves the app correctly *before* wiring any supervision or tunnel around it. *Why second:* validates the app runs correctly under a real WSGI server (thread/worker behavior differs from `runserver`) while still only reachable from the Pi itself — cheap to debug in isolation.
3. **systemd service for Gunicorn** — Wrap step 2 in a `gunicorn.service` unit; enable + start; reboot-test. *Why third:* depends on step 2 working manually first; must be solid before cloudflared depends on it being "always up."
4. **File-upload validation / media-serving review** — Since this app will be reachable from the internet after step 6, close the CONCERNS.md gaps that are only risky *once public*: evidence file-upload type/size validation, and reconsider Django's direct media serving (`re_path(r'^media/...')` in `config/urls.py`) now that unauthenticated requests could theoretically hit that URL from anywhere. *Why here:* logically a "before going live" gate, but doesn't depend on cloudflared/DNS — can be done in parallel with steps 2–3.
5. **Domain acquisition + DNS/CSRF finalization** — Buy the domain, add its zone to Cloudflare, then fill in real values for `ALLOWED_HOSTS` and `CSRF_TRUSTED_ORIGINS` (replacing the `placeholder.example.com` TODO). *Why here:* `cloudflared tunnel route dns` in the next step requires the zone to already be on Cloudflare; settings can't be finalized without knowing the real hostname.
6. **cloudflared tunnel** — `cloudflared tunnel login` → `cloudflared tunnel create <name>` → write `config.yml` ingress rule pointing at `http://127.0.0.1:8000` with a catch-all 404 → `cloudflared tunnel route dns` → `cloudflared service install` (systemd) → reboot-test both units together. *Why last before go-live:* this is the step that actually exposes the app to the internet — everything before it (settings, WSGI, systemd, domain) is a prerequisite that must be correct first, since misconfigured `ALLOWED_HOSTS`/`CSRF_TRUSTED_ORIGINS` at this point manifests as confusing 400/403 errors that look like tunnel problems but aren't.
7. **Go live + runbook** — Confirm end-to-end (login, buy/sell, PDF/CSV export, evidence upload/view) over the real HTTPS domain; write the deployment runbook (already an Active requirement) covering: what to do after a Pi reboot/power outage (verify both systemd units via `systemctl status gunicorn cloudflared`), and how to rotate/renew if the tunnel credentials or domain ever change.

**Ordering rationale:** Settings and WSGI/systemd work (1–4) is entirely local to the Pi and testable without any public exposure, so it should be solid *before* the domain and tunnel (5–6) make the app internet-reachable — this avoids debugging security-header behavior (CSRF, secure cookies, SSL redirect) simultaneously with tunnel/DNS propagation issues, which are a different failure class with different symptoms (400/403 vs. connection refused/DNS not resolving).

## Sources

- [Cloudflare Tunnel · Cloudflare One docs](https://developers.cloudflare.com/cloudflare-one/networks/connectors/cloudflare-tunnel/) — MEDIUM confidence (official docs, cross-checked against community write-ups)
- [Cloudflare Tunnel · Cloudflare Docs](https://developers.cloudflare.com/tunnel/)
- [Routing · Cloudflare Docs](https://developers.cloudflare.com/tunnel/routing/)
- [Run as a service on Linux · Cloudflare One docs](https://developers.cloudflare.com/cloudflare-one/networks/connectors/cloudflare-tunnel/do-more-with-tunnels/local-management/as-a-service/linux/)
- [Security in Django — Django documentation](https://django.readthedocs.io/en/stable/topics/security.html) — MEDIUM confidence (official Django docs)
- [#34855 Document CSRF_TRUSTED_ORIGINS relation to SECURE_PROXY_SSL_HEADER — Django ticket tracker](https://code.djangoproject.com/ticket/34855)
- [CSRF verification failed after putting behind SSL proxy — Django Forum](https://forum.djangoproject.com/t/csrf-verification-failed-request-aborted-after-putting-behind-ssl-proxy/29130)
- [Stop Trusting Your Reverse Proxy: Secure Django the Right Way](https://www.mybluelinux.com/stop-trusting-your-reverse-proxy-secure-django-the-right-way/)
- [Securely Deploy a Django App With Gunicorn, Nginx, & HTTPS — Real Python](https://realpython.com/django-nginx-gunicorn/) — MEDIUM confidence (well-established reference tutorial)
- [Installing Cloudflare Tunnel (cloudflared) on Raspberry Pi 5](https://www.mykolaaleksandrov.dev/posts/2025/07/cloudflare-tunnel-raspberrypi5/) — LOW-MEDIUM confidence (single blog post, Pi-specific, cross-checked against official docs for the general mechanics)
- [Exposing a web service with Cloudflare Tunnel - Erisa A](https://erisa.dev/exposing-a-web-service-with-cloudflare-tunnel/)

---
*Architecture research for: Django app deployment behind Cloudflare Tunnel on Raspberry Pi 4*
*Researched: 2026-07-19*
