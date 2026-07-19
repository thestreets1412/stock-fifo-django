# Stack Research

**Domain:** Self-hosted Django deployment on Raspberry Pi 4, exposed via Cloudflare Tunnel (single-user, personal, low-traffic)
**Researched:** 2026-07-19
**Confidence:** MEDIUM (official Cloudflare/Django/PyPI docs cross-checked; some ARM/Pi-specific specifics are LOW — flagged individually)

## Recommended Stack

### Core Technologies

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| **gunicorn** | 26.0.0 (pin `gunicorn>=26,<27`) | WSGI application server running Django | Simple, battle-tested, low-overhead prefork WSGI server. Right-sized for a single synchronous Django app with no WebSockets/async requirement — uWSGI's extra tunables and Daphne's ASGI/WebSocket machinery are unneeded complexity for this app. Confirms it declares support through Python 3.13 (no explicit 3.14 support yet as of this writing — see "What NOT to Use"). Confidence: MEDIUM (PyPI classifiers checked directly). |
| **cloudflared** | 2026.7.x (latest at deploy time, `apt` package `cloudflared`) | Outbound tunnel daemon; publishes the Pi's local Django server to the internet without opening router ports | Official Cloudflare Zero Trust connector. Installs via Cloudflare's own apt repo with confirmed `arm64` support, runs as a systemd service with `cloudflared service install`, auto-reconnects, and terminates TLS at Cloudflare's edge (so the Pi never needs its own certificate). Confidence: MEDIUM (official docs + community install guides cross-checked). |
| **whitenoise** | 6.12.x | Serves Django static files (CSS/JS/admin assets) directly from the app process, compressed and cache-busted | Eliminates the need for nginx (or any second process) to serve static assets. Add `whitenoise.middleware.WhiteNoiseMiddleware` immediately after `SecurityMiddleware`; set `STORAGES["staticfiles"]["BACKEND"] = "whitenoise.storage.CompressedManifestStaticFilesStorage"` and run `collectstatic` as a deploy step. Confidence: MEDIUM. |
| **systemd** (OS-provided, no install) | Whatever ships with Raspberry Pi OS Trixie | Process supervision for both `gunicorn` and `cloudflared` — boot-time start, crash auto-restart, centralized logs via `journalctl` | Raspberry Pi OS Lite has no other init system; systemd unit files are the standard, zero-extra-dependency way to keep both processes alive across reboots and crashes. Avoid heavier process managers (supervisord, pm2) — they duplicate what systemd already does natively on this OS. Confidence: HIGH (standard Debian/RPi practice). |

### Supporting Libraries

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `python-decouple` | 3.8 (already in use) | Reads `SECRET_KEY`, `DEBUG`, `ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS` from `.env` | Already adopted by the app — extend it: add `CSRF_TRUSTED_ORIGINS = config('CSRF_TRUSTED_ORIGINS', cast=Csv())` reading the real domain instead of the current placeholder. |
| `django-sendfile2` (only if media protection needs to move to nginx later) | latest | Lets Django authorize a file download while a front-end server does the actual byte-serving via `X-Accel-Redirect` | **Not needed now** — since no nginx sits in front, keep serving evidence images through a Django view but require login. Wrap `django.views.static.serve` in a `@login_required` view (or a class-based view with `LoginRequiredMixin`) scoped to `request.user`'s own evidence files, replacing the current unauthenticated `re_path(r'^media/...')` mapping flagged in `CONCERNS.md`. Revisit `django-sendfile2` + nginx only if traffic/file sizes grow enough to matter — irrelevant at single-user scale. |
| `certbot` / any TLS library | — | N/A | **Not needed at all.** Cloudflare Tunnel terminates TLS at its edge; the Pi never needs a certificate or port 443 open. Do not install certbot or configure Django/gunicorn for HTTPS directly. |

## Installation

```bash
# On the Raspberry Pi (arm64, Raspberry Pi OS Trixie / Debian 13), inside the project venv:
pip install gunicorn==26.0.0 whitenoise==6.12.0

# cloudflared — via Cloudflare's official apt repo (arm64-supported):
sudo mkdir -p --mode=0755 /usr/share/keyrings
curl -fsSL https://pkg.cloudflare.com/cloudflare-main.gpg | sudo tee /usr/share/keyrings/cloudflare-main.gpg >/dev/null
echo 'deb [signed-by=/usr/share/keyrings/cloudflare-main.gpg] https://pkg.cloudflare.com/cloudflared trixie main' | \
  sudo tee /etc/apt/sources.list.d/cloudflared.list
sudo apt-get update && sudo apt-get install cloudflared
```

Note: the apt repo path snippet found in current guides references `bookworm` (the prior stable); if the Pi is on Trixie use the `trixie` distribution component shown above — verify with `lsb_release -cs` on the Pi before running the `echo` command, and fall back to `bookworm` only if `trixie` isn't yet published in Cloudflare's repo at deploy time.

## Alternatives Considered

| Recommended | Alternative | When to Use Alternative |
|-------------|-------------|-------------------------|
| gunicorn (WSGI) | uWSGI | Only if you need uWSGI-specific features (emperor mode for multi-app hosting, advanced fine-tuning). Overkill for one Django app on a Pi — steeper config surface for no benefit here. |
| gunicorn (WSGI) | daphne / uvicorn (ASGI) | Only if the app gains real-time features (WebSockets, Django Channels, long-lived SSE connections). This app is fully synchronous request/response (dashboard, forms, PDF/CSV export) — ASGI buys nothing and adds an event-loop model to reason about. |
| No local reverse proxy (cloudflared → gunicorn directly) | nginx in front of gunicorn | Add nginx only if: (a) you later host multiple local services behind one Pi and want path/subdomain based local routing beyond what Cloudflare ingress rules already give you, or (b) you want a local buffering/caching layer independent of Cloudflare. For a single Django app behind Cloudflare's edge (which already does TLS, WAF, DDoS, and caching), nginx is a second process to patch, monitor, and keep alive for no measurable benefit at single-user load. |
| Remotely-managed (dashboard/token) Cloudflare Tunnel | Locally-managed tunnel with `config.yml` | Prefer `config.yml` (locally-managed) if you want the ingress rules version-controlled in the repo/runbook as plain text, or if you're not comfortable routing changes going through the Cloudflare dashboard. Both are supported; dashboard-managed is simpler to bootstrap (one command with `--token`, no `cert.pem`/`config.yml` to keep in sync), which fits a personal single-tunnel setup better. |
| WhiteNoise for static files | nginx `alias`/`location` static serving | Only relevant if nginx is already in the stack for another reason (see above) — then let nginx serve `/static/` directly instead of routing it through gunicorn. Since this deployment skips nginx, WhiteNoise is the simplest way to serve compressed, cache-busted static assets from the same gunicorn process. |

## What NOT to Use

| Avoid | Why | Use Instead |
|-------|-----|-------------|
| Deploying with Python 3.14 on the Pi to match the dev machine's `requirements.txt`-implied version | gunicorn 26.0.0's PyPI trove classifiers currently stop at Python 3.13 — no confirmed 3.14 support as of this research. Raspberry Pi OS's current stable release (Trixie/Debian 13) ships **Python 3.13** by default, not 3.14. Chasing 3.14 on the Pi risks gunicorn install/runtime issues and ARM wheel availability gaps for numpy/pandas/pillow/curl_cffi. | Target **Python 3.13** (the Pi's system/apt Python) for the production venv on the Pi. Confirm this doesn't break app code (Django 6 supports 3.12–3.14, so 3.13 is safe); re-pin `requirements.txt` for the Pi venv if any transitive dependency was pinned to a 3.14-only build. Revisit once gunicorn publishes confirmed 3.14 support. Confidence: MEDIUM — verified via PyPI classifiers and Raspberry Pi OS release notes, but exact current default Python on whatever RPi OS image is actually flashed on this specific Pi should be checked with `python3 --version` before committing to this plan. |
| `runserver` (Django's dev server) as the production process | Django's own docs and every deployment guide are explicit that `runserver` is not hardened or performant for anything but local development — no worker concurrency, no crash resilience, security-relevant warnings suppressed. | gunicorn, supervised by systemd, as above. |
| Opening router ports / port-forwarding to the Pi | Explicitly ruled out in `PROJECT.md` constraints (no static IP, no port forwarding) and defeats the entire purpose of using Cloudflare Tunnel (avoiding home IP exposure). | Cloudflare Tunnel's outbound-only connection — never open inbound ports on the home router. |
| Heavyweight process managers (supervisord, pm2, Docker Compose orchestration) just to keep 2 processes alive | Raspberry Pi OS Lite already has systemd as PID 1; adding another supervisor duplicates restart/boot-start logic and consumes RAM/CPU the Pi doesn't have to spare. | Two plain systemd unit files (`gunicorn.service`, `cloudflared.service`), each with `Restart=on-failure` and `WantedBy=multi-user.target`. |
| Unauthenticated `re_path` media serving (`django.views.static.serve` mounted directly in `urls.py`) | Already flagged in `CONCERNS.md` as not production-safe — with no nginx in front to add an auth layer via `X-Accel-Redirect`, this exposes uploaded evidence images to anyone with the URL. | Wrap media serving in a login-gated Django view scoped to `request.user`, as noted in Supporting Libraries above. |
| Using `cloudflared tunnel --url` "quick tunnels" for anything beyond throwaway testing | Quick tunnels get a random `trycloudflare.com` subdomain that changes on every restart — unusable for a stable domain the user bookmarks/relies on. | A named tunnel (dashboard-managed or `config.yml`-managed) bound to the real, owned domain. |

## Stack Patterns by Variant

**If the Pi's system Python is 3.13 (Trixie default):**
- Use gunicorn 26.0.0 as-is; no compatibility concerns.
- Because gunicorn's PyPI classifiers confirm 3.13 support explicitly.

**If for any reason the Pi ends up on Python 3.14 (e.g. built from source or a non-standard image):**
- Pin gunicorn to whatever the latest release is at deploy time and verify `pip install gunicorn` succeeds and `gunicorn --version` runs before relying on it; have a fallback plan to install Python 3.13 via `apt` alongside if it fails.
- Because 3.14 support was unconfirmed as of this research (2026-07-19) — this should be re-verified at actual deploy time since gunicorn ships frequent releases.

**If the user later adds a second local service on the same Pi (e.g. a monitoring dashboard, another app):**
- Introduce nginx (or just add more `ingress` rules in cloudflared's `config.yml` routing to different local ports) rather than cramming multiple apps behind one gunicorn process.
- Because Cloudflare Tunnel already supports multiple ingress hostnames pointing at different local `service:` targets without any local reverse proxy — this is the natural scaling path before nginx becomes necessary.

## Version Compatibility

| Package A | Compatible With | Notes |
|-----------|-----------------|-------|
| Django 6.0.7 | Python 3.12 / 3.13 / 3.14 | Django itself supports all three; the constraint is gunicorn (see above), not Django. |
| gunicorn 26.0.0 | Python 3.10–3.13 (per PyPI classifiers) | No confirmed 3.14 support at time of research — re-check `pypi.org/project/gunicorn/` before deploying if the Pi runs 3.14. |
| cloudflared (apt package) | Raspberry Pi OS Bookworm and Trixie, arm64 | Cloudflare's apt repo (`pkg.cloudflare.com/cloudflared`) publishes per-Debian-codename components; use whichever codename `lsb_release -cs` reports on the Pi. |
| whitenoise 6.12.x | Django 6.x | WhiteNoise's Django integration doc targets current Django releases; no known incompatibility with Django 6. |

## Sources

- [Cloudflare Tunnel · Cloudflare Docs](https://developers.cloudflare.com/tunnel/) — MEDIUM confidence, official docs, tunnel architecture/request flow
- [Run as a service on Linux · Cloudflare One docs](https://developers.cloudflare.com/cloudflare-one/networks/connectors/cloudflare-tunnel/do-more-with-tunnels/local-management/as-a-service/linux/) — MEDIUM, official docs, systemd service install patterns (token-based and config.yml-based)
- [Configuration file · Cloudflare One docs](https://developers.cloudflare.com/cloudflare-one/networks/connectors/cloudflare-tunnel/do-more-with-tunnels/local-management/configuration-file/) — MEDIUM, official docs, `config.yml`/ingress rule requirements
- [Create a tunnel (dashboard) · Cloudflare One docs](https://developers.cloudflare.com/cloudflare-one/networks/connectors/cloudflare-tunnel/get-started/create-remote-tunnel/) — MEDIUM, official docs, remotely-managed (token) tunnel setup
- [Security in Django | Django documentation](https://docs.djangoproject.com/en/6.0/topics/security/) — MEDIUM, official docs, `SECURE_PROXY_SSL_HEADER`/CSRF/secure-cookie settings
- [How to use Django with Gunicorn — Django docs](https://django.readthedocs.io/en/stable/howto/deployment/wsgi/gunicorn.html) — MEDIUM, official docs
- [gunicorn · PyPI](https://pypi.org/project/gunicorn/) — MEDIUM, verified directly via WebFetch: version 26.0.0, Python 3.10–3.13 classifiers, no 3.14 yet
- [Using WhiteNoise with Django — WhiteNoise docs](https://whitenoise.readthedocs.io/en/stable/django.html) — MEDIUM, official docs
- [Trixie — the new version of Raspberry Pi OS](https://www.raspberrypi.com/news/trixie-the-new-version-of-raspberry-pi-os/) — MEDIUM, official Raspberry Pi Foundation announcement; confirms Debian 13/Trixie is current stable, Python 3.13 default
- Community guides (Pi My Life Up, DoHost, various Medium/DEV.to posts) cross-checked for cloudflared apt-repo install steps, gunicorn systemd unit patterns, and "nginx vs direct tunnel" community consensus — LOW individually, used only where corroborated by 2+ independent sources or an official doc

---
*Stack research for: Django-on-Raspberry-Pi deployment via Cloudflare Tunnel*
*Researched: 2026-07-19*
