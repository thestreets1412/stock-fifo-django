# Pitfalls Research

**Domain:** Self-hosting Django behind Cloudflare Tunnel on a Raspberry Pi 4 (single-user, SQLite-backed)
**Researched:** 2026-07-19
**Confidence:** MEDIUM (web-sourced, cross-checked across multiple independent sources including Django/SQLite/Cloudflare official docs; no project-specific load testing performed)

## Critical Pitfalls

### Pitfall 1: `SECURE_PROXY_SSL_HEADER` missing or wrong once traffic arrives via the tunnel

**What goes wrong:**
Cloudflare Tunnel terminates TLS at Cloudflare's edge and forwards plain HTTP to `cloudflared` on the Pi, which forwards it to Django over `localhost`. Django therefore sees every request as `http://`, not `https://`. If `SECURE_SSL_REDIRECT = True` (or is derived from `not DEBUG`, as this project's uncommitted settings diff does) but `SECURE_PROXY_SSL_HEADER` is not set, Django redirects every request to HTTPS, the redirect gets stripped back to HTTP at the proxy hop, and the browser hits an infinite redirect loop. The site becomes completely unreachable — indistinguishable from an outage.

**Why it happens:**
Locally (`DEBUG=True`, direct connection) there is no proxy in the loop, so this setting is invisible in dev and easy to forget when flipping `DEBUG=False` for the Pi.

**How to avoid:**
Set `SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')` in settings whenever `DEBUG=False`. Cloudflare Tunnel sets `X-Forwarded-Proto: https` automatically — no extra Cloudflare-side config needed, but if a local Nginx/reverse proxy is added in front of Gunicorn, it must be configured to also set/forward that header (`proxy_set_header X-Forwarded-Proto $scheme;`), and it must not be overwritten anywhere in the chain.

**Warning signs:** `ERR_TOO_MANY_REDIRECTS` in the browser, or `curl -v https://yourdomain` showing endless `301`/`308` responses after go-live.

**Phase to address:** Settings hardening (before tunnel is wired up — test with `curl` locally simulating the header: `curl -H "X-Forwarded-Proto: https" ...`).

---

### Pitfall 2: `CSRF_TRUSTED_ORIGINS` left as a placeholder or scheme-mismatched

**What goes wrong:**
`CONCERNS.md` already flags `CSRF_TRUSTED_ORIGINS = "https://placeholder.example.com"` as a hardcoded TODO. Two distinct failure modes follow from this: (a) if left as the placeholder, every POST from the real domain (login, buy/sell forms, evidence upload) is rejected with `403 CSRF verification failed` — the app looks broken the moment it goes live; (b) if fixed but entered as `yourdomain.com` instead of `https://yourdomain.com` (Django 4+ requires the scheme), CSRF still fails silently the same way.

**Why it happens:** `CSRF_TRUSTED_ORIGINS` is easy to treat as a "set once, forget" value, but it must exactly match the origin the browser sends (scheme + host), and Django is strict about the scheme prefix.

**How to avoid:** Read `CSRF_TRUSTED_ORIGINS` from `.env` (matching this project's existing `python-decouple` pattern for `DEBUG`/`SECRET_KEY`/`ALLOWED_HOSTS`) as a comma-separated `Csv()` value, e.g. `CSRF_TRUSTED_ORIGINS=https://yourdomain.com`. Add it to `.env.example`/deployment docs. After go-live, log in and submit one real form (a lot or sale) as a smoke test — don't just load the homepage, since CSRF only bites on POST.

**Warning signs:** `403 Forbidden — CSRF verification failed. Request aborted.` on any form submit; GET pages loading fine while all POSTs fail.

**Phase to address:** Settings hardening (domain-dependent — can't be finalized until the real domain is acquired, but the `.env`-driven mechanism should be built before that). Verify at go-live.

---

### Pitfall 3: SQLite corruption from unclean power loss on SD-card storage

**What goes wrong:**
A Raspberry Pi run as a "leave it on forever" home server has no UPS by default. Storms, Wi-Fi router power-cycling on the same outlet, or someone unplugging the wrong adapter causes an unclean shutdown mid-write. SQLite's default rollback-journal mode requires an `fsync` at commit; if the SD card's write cache lies about durability (common on cheap microSD) or the write is interrupted, the database file or its `-journal`/`-wal` sidecar file can be left corrupted or orphaned, and the FIFO ledger (the entire point of this app) becomes unreadable or silently wrong.

**Why it happens:** SD cards are not designed for database-grade write durability the way SSDs are; consumer cards especially lack power-loss protection circuitry. This is a known, reported failure mode specifically on Raspberry Pi SD-card deployments, separate from normal SD wear.

**How to avoid:**
- Enable SQLite **WAL mode** (`PRAGMA journal_mode=WAL;`) — it is more forgiving of out-of-order writes and reduces (but does not eliminate) corruption risk versus the default rollback journal. Django can set this via `DATABASES['default']['OPTIONS'] = {'init_command': 'PRAGMA journal_mode=WAL;'}` or a post-connect signal.
- Never let the WAL/journal sidecar file get separated from the main `.sqlite3` file (matters for backup scripts — always copy/back up all three files together, or use `sqlite3 .backup`, not a raw `cp` while the app is running).
- Set up a scheduled backup (e.g., nightly cron running `sqlite3 db.sqlite3 ".backup backup.sqlite3"`, which is safe to run on a live DB) copied off the SD card (to a USB drive, NAS, or cloud target) — this is the actual mitigation, not corruption-proofing the primary copy.
- If budget allows, put a small UPS HAT on the Pi, or at minimum plug it into a battery-backed outlet, so `shutdown -h now` can run cleanly on power loss instead of an abrupt cut.

**Warning signs:** `sqlite3.DatabaseError: database disk image is malformed`; Django admin/queries suddenly erroring after a power blip; `PRAGMA integrity_check;` returning anything other than `ok`.

**Phase to address:** Server setup (enable WAL + backup cron before go-live). This directly protects the "preserving the FIFO ledger's integrity" core value stated in PROJECT.md.

---

### Pitfall 4: `cloudflared` run ad-hoc (foreground process / Quick Tunnel) instead of a proper systemd service with a named tunnel

**What goes wrong:**
Two related mistakes compound here. First, running `cloudflared tunnel run` in a terminal (or via `nohup`/screen) means the tunnel dies the moment the SSH session closes or the Pi reboots — the whole point of this milestone ("reachable securely, at all times") silently fails. Second, using a **Quick Tunnel** (`cloudflared tunnel --url http://localhost:8000`, no `config.yml`) is explicitly documented by Cloudflare as testing-only: it generates a random, unmemorable `trycloudflare.com` subdomain on every restart, has no persistent credentials, caps at 200 concurrent requests, and offers no path to attach a custom domain or Cloudflare Access — none of which fit the "real domain + always-on" requirement in this project's Active requirements.

**Why it happens:** Quick Tunnels are the fastest way to verify Cloudflare Tunnel works at all during initial testing, so it's tempting to leave that config in place rather than switching to a named tunnel + systemd service before go-live.

**How to avoid:**
- Create a **named tunnel** (`cloudflared tunnel create <name>`), which generates a stable UUID and credentials JSON file — this identity is what survives reboots, not the process itself.
- Write `/etc/cloudflared/config.yml` with `tunnel:`, `credentials-file:`, and `ingress:` rules mapping the real hostname to `http://localhost:<port>`, ending with the **mandatory catch-all** `- service: http_status:404` (cloudflared refuses to start without it).
- Install as a systemd service: `sudo cloudflared service install`, then `sudo systemctl enable --now cloudflared`. This gives automatic start-on-boot and (via systemd's default restart policy for the generated unit) recovery after a crash.
- Actually reboot the Pi once during setup and confirm both `cloudflared` and the Django/Gunicorn service come back automatically — don't assume `enable` alone proves it.

**Warning signs:** Domain works right after manual setup but goes dark after any Pi reboot or power blip; tunnel URL changes on every restart; `systemctl status cloudflared` shows `inactive` after boot.

**Phase to address:** Tunnel setup phase, verified explicitly at go-live with a real reboot test (this should be a named acceptance check, not just "systemctl enable was run").

---

### Pitfall 5: `DEBUG=True` (or a stray fallback default) reaching the internet-facing deployment

**What goes wrong:**
`DEBUG=True` in Django dumps full stack traces, local variable values, the `SECRET_KEY`-derived cookies, installed apps, and settings on any unhandled exception — including from this app's own service layer (`fetch_current_price`, `fetch_usd_thb_rate`, `record_sale`), which per `CONCERNS.md` already has known un-handled edge cases. Once the tunnel exposes the app publicly, an error triggered by literally anyone (bots scanning the tunnel hostname, not just the owner) turns into an information-disclosure incident: source paths, installed packages, and potentially the DB path are exposed. Separately, `ALLOWED_HOSTS` misconfiguration combines badly here — if it's left overly permissive (`['*']`) "to make the tunnel work," Host-header attacks become possible even with `DEBUG=False`.

**Why it happens:** `.env` already differentiates `DEBUG=True` locally per PROJECT.md context, so the risk isn't the default — it's a bad `.env` on the Pi (copy-paste from a local `.env`, or a `python-decouple` default of `True` if the Pi's `.env` is ever missing/misread) never getting caught before go-live.

**How to avoid:**
- Set `DEBUG` with `config('DEBUG', default=False, cast=bool)` (default **False**, not `True`) so any missing/misread `.env` on the Pi fails closed, not open.
- Set `ALLOWED_HOSTS` explicitly to the real domain (and `localhost`/Pi LAN IP only if still needed for local debugging), never `['*']`.
- Run `python manage.py check --deploy` against the Pi's actual settings before every go-live and after any settings change — it specifically flags `DEBUG=True`, missing `ALLOWED_HOSTS`, missing secure-cookie flags, etc.
- Change the Django admin URL from `/admin/` to something non-default (defense in depth against the automated `/admin/` brute-force scans that hit any public IP/hostname), and ensure the admin superuser has a strong, unique password (it's the only account, but it's also the highest-value target).

**Warning signs:** Any 500 page showing a Django traceback/technical 500 page to the public instead of a generic error page; `manage.py check --deploy` producing warnings that were previously ignored.

**Phase to address:** Settings hardening, with `check --deploy` as an explicit go/no-go gate before the tunnel phase begins routing real traffic.

---

### Pitfall 6: Media files (evidence uploads) become internet-readable once the tunnel is live, even though views are login-gated

**What goes wrong:**
This is already flagged in `CONCERNS.md` as a known issue — `config/urls.py` serves media via Django's raw `serve()` view at `/media/<path>`, and while every *view* uses `LoginRequiredMixin`, the media URL pattern itself has no permission check. Locally ("runs on my machine," LAN-only) this was low-risk because nobody outside the household could reach the URL at all. **Once Cloudflare Tunnel exposes the app to the whole internet, this changes from a theoretical gap to an actual one**: anyone who can guess or enumerate an evidence-image filename/UUID can fetch it directly with a plain unauthenticated `GET /media/...` request, bypassing login entirely. Given this app stores personal financial trade evidence, that's a real data-exposure path, not a cosmetic one.

**Why it happens:** Django's `serve()` helper (typically used only for local dev via `static()`) has no concept of ownership/auth — it just streams whatever file matches the path, which is fine in a closed LAN and dangerous once tunneled to the public internet.

**How to avoid (pick one, matching PROJECT.md's Active requirement to review this):**
- **Minimum viable fix for a single-user personal deployment:** put media serving behind Cloudflare Access (Zero Trust) at the edge — require the owner's identity/login (e.g., email OTP or a hardware key) for the whole hostname or specifically the `/media/*` path, before any request even reaches the Pi. This is free at this scale (Cloudflare Access is free under ~50 seats) and closes the gap without touching Django code.
- **App-level fix:** replace the raw `serve()` URL with a small authenticated view (`@login_required`, filtered by `owner=request.user`) that streams the file only after an ownership check — matches the pattern already used elsewhere in the codebase (evidence views already filter by owner per `CONCERNS.md`).
- Do **not** rely on "unguessable filenames" alone as the security boundary — treat it as defense in depth at most.
- Out of scope for this milestone but worth flagging: object storage (S3/Cloudflare R2) with signed URLs is the eventual production-correct answer per `CONCERNS.md`'s own recommendation; not required to ship this milestone.

**Warning signs:** `curl -I https://yourdomain/media/evidence/<any-known-or-guessed-filename>` returning `200` from an incognito/unauthenticated session.

**Phase to address:** This is explicitly called out in PROJECT.md's Active requirements ("review of Django's direct media-file serving under the tunnel") — treat as a go-live blocker, addressed in the security-gaps-closing phase, verified before the tunnel routes public traffic.

---

### Pitfall 7: ARM64 wheel gaps break `pip install` on first Pi deployment (or silently after a dependency bump)

**What goes wrong:**
Some Python packages either ship no prebuilt `aarch64`/`manylinux_aarch64` wheel on PyPI, or the Pi's pip/setuptools is too old to select the wheel tag that does exist, causing pip to fall back to building from source. Building from source needs a full toolchain (`gcc`, `python3-dev`, and for `cryptography` specifically, a **Rust compiler**) that a fresh Raspberry Pi OS Lite image does not have by default — the build fails outright, or (worse) succeeds after a very long compile that looks like a hang on a Pi 4's limited cores. This project's `requirements.txt` includes `Pillow==12.3.0` (image handling for evidence uploads) and likely `cryptography` transitively (via Django's crypto/session signing stack) — both are packages with a documented history of ARM64 build friction.

**Why it happens:** Most Django tutorials/CI are written and tested against x86_64; ARM64-specific wheel availability lags behind and isn't obvious until you actually run `pip install -r requirements.txt` on the Pi.

**How to avoid:**
- On the Pi, before installing project requirements: `sudo apt-get install -y build-essential python3-dev libjpeg-dev zlib1g-dev` (covers Pillow's C deps) and upgrade pip first — `pip install --upgrade pip setuptools wheel` (pip ≥ 22.x correctly resolves `manylinux_aarch64` wheel tags where older pip silently falls back to source builds).
- Prefer **piwheels.org** as an extra index for Raspberry Pi OS if any package still fails to find a prebuilt wheel (`pip install --extra-index-url https://www.piwheels.org/simple/ ...`) — it hosts ARM-built wheels for common packages including Pillow.
- If `cryptography` needs to build from source, install `cargo`/`rustc` via `apt` first rather than letting pip attempt and fail deep into the install.
- Do the full `pip install -r requirements.txt` on the Pi **once, early**, as a dry-run — don't discover ARM64 wheel gaps for the first time during the actual go-live deploy window.

**Warning signs:** `ERROR: Failed building wheel for <package>`; install appears to hang for many minutes on `Pillow`/`cryptography`/`psycopg2` (this project doesn't use `psycopg2` since it's staying on SQLite, but any future dependency addition should get this same treatment).

**Phase to address:** Server setup phase — as an explicit dependency-install verification step on the actual Pi hardware, ideally the very first thing done in that phase (matches PROJECT.md's constraint that the Pi is "already running the app locally," so this may already be resolved — but worth a `pip check`/clean-reinstall verification since the recent commit history shows a Pi-specific bug fix was already needed once).

---

### Pitfall 8: Sustained load causes SoC thermal throttling and undervoltage brownouts, which look like app bugs

**What goes wrong:**
The Pi 4's BCM2711 SoC begins throttling clock speed as it approaches 80–85°C under sustained load (report generation with ReportLab, which `CONCERNS.md` already flags as memory-heavy at scale, is exactly the kind of CPU burst that triggers this) and can hit a hard throttle/reduced-voltage state that manifests as unexplained slowness or intermittent failures rather than a clean crash. Separately, a weak/cheap USB-C power supply or long/thin cable causes **undervoltage**, which Raspberry Pi OS reports via a lightning-bolt icon and `dmesg`/`vcgencmd get_throttled` codes but which, if ignored, can cause silent data corruption on the attached SD card mid-write (compounding Pitfall 3) or spontaneous reboots.

**Why it happens:** A stock Pi 4 in a bare case or the manufacturer's minimal case has no active cooling, and undervoltage is easy to introduce with an underspecced or third-party power adapter — both are invisible until the device is under real, sustained load (which "runs on my machine" testing may not have exercised).

**How to avoid:**
- Use the official (or equivalent 5V/3A USB-C, short well-made cable) Raspberry Pi 4 power supply — this alone eliminates most undervoltage reports.
- Add at minimum a heatsink, ideally a small fan/active-cooling case, especially since this Pi will run 24/7 as an always-on server (not intermittent hobby use).
- After deployment, check `vcgencmd get_throttled` (a nonzero result, especially bits indicating "currently throttled" or "under-voltage now," is the smoking gun) and `vcgencmd measure_temp` under a deliberate load test (e.g., generate a large FIFO PDF report) as part of go-live verification.
- This is unlikely to matter at single-user scale most of the time — flag as a monitoring/verification step, not a blocking redesign.

**Warning signs:** Dashboard/report generation becomes progressively slower over a session then recovers after idling; `vcgencmd get_throttled` returns nonzero; Pi reboots unexpectedly under load with no corresponding software error in logs.

**Phase to address:** Go-live verification (a load-test smoke check, e.g. generate a report and hit the dashboard repeatedly while watching `vcgencmd`), not a settings/code change.

---

## Technical Debt Patterns

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|--------------------|-----------------|------------------|
| Leaving `cloudflared` as a Quick Tunnel during setup | Fast to verify the tunnel concept works at all | Random URL, no persistent identity, 200-req cap, dies on reboot — unusable for "always reachable" goal | Only during the very first connectivity smoke test; must be replaced with a named tunnel + systemd service before any real domain/go-live |
| Serving media via Django's raw `serve()` view instead of an authenticated view or edge-level Access rule | Zero extra code, works immediately | Public, unauthenticated read access to personal financial evidence files once tunneled | Never acceptable once the tunnel is live and the domain is public — this is explicitly a pre-production gap per PROJECT.md/CONCERNS.md |
| Keeping SQLite default rollback-journal mode instead of enabling WAL | No config change needed | Slightly higher corruption exposure on unclean power loss vs. WAL | Acceptable only if a tested, off-device backup cron is already in place; better to just enable WAL, it's a one-line setting |
| Skipping the `pip install` dry-run on the actual Pi before go-live | Saves 15–30 minutes during setup | First real deploy attempt can fail on ARM64 wheel gaps at the worst possible time (during a maintenance/cutover window) | Never — do this dry run early in server-setup phase regardless of time pressure |

## Integration Gotchas

| Integration | Common Mistake | Correct Approach |
|-------------|-----------------|-------------------|
| Cloudflare Tunnel + Django | Pointing `cloudflared` at `manage.py runserver` directly | Run Gunicorn (or similar WSGI server) as a systemd service bound to `localhost`/a unix socket; point `cloudflared`'s ingress rule at that, not at the dev server |
| Cloudflare Tunnel + Django settings | Assuming HTTPS is "automatic" once tunneled and skipping `SECURE_PROXY_SSL_HEADER` | Explicitly set `SECURE_PROXY_SSL_HEADER` — Cloudflare sets the header, but Django won't trust it unless told to |
| Cloudflare Tunnel `config.yml` | Omitting the catch-all `- service: http_status:404` ingress rule | Always include it as the last ingress entry — `cloudflared` will refuse to start otherwise |
| Cloudflare Access (optional hardening) | Assuming Cloudflare Access replaces Django's own login | Layer them — Access gates entry at the edge (extra MFA layer for a single-owner site), Django's own auth/`LoginRequiredMixin` still does per-object owner checks; don't remove Django auth in favor of Access alone |

## Performance Traps

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|-----------------|
| Sequential per-symbol price/FX fetches (already flagged in CONCERNS.md) combined with a public tunnel inviting bot/crawler traffic to the dashboard | Dashboard load time balloons; on the Pi this also drives CPU/thermal load noted in Pitfall 8 | Not a blocker for this milestone (single user), but note that a publicly reachable dashboard is more likely to get incidental bot traffic than a LAN-only one — consider `robots.txt` disallow-all and/or Cloudflare Access to keep unauthenticated crawler hits off the app entirely | Becomes noticeable once dashboard is loaded repeatedly by scanners hitting the public hostname |
| SQLite under Gunicorn with >1 worker | `database is locked` errors on concurrent writes even at "single user" scale, because a browser can fire multiple requests (AJAX form + dashboard poll) concurrently | Keep Gunicorn worker count low (1–2 sync workers is plenty for one user) and ensure `timeout` in SQLite connection settings is set (Django's default SQLite `OPTIONS.timeout` is 5s; consider raising it) so concurrent writes wait briefly instead of failing immediately | Any time two write requests land in the same ~second window, regardless of "single user" framing — a form submit racing a background price fetch is enough |

## Security Mistakes

| Mistake | Risk | Prevention |
|---------|------|------------|
| Treating "Cloudflare Tunnel means no open ports" as "means fully secure" | Owner assumes network-level security is the whole story and skips Django-level hardening (secure cookies, CSRF origins, DEBUG=False) | Tunnel only solves *network exposure* (no port-forward/public IP); Django-level hardening is still fully required — treat as additive, not substitutive |
| Leaving `/admin/` at the default path with only a login form | Django admin is a well-known bot-scanned target; a single leaked/weak credential = full data access | Rename the admin URL, use a strong unique password, and optionally require Cloudflare Access before `/admin/*` reaches the Pi at all |
| Unauthenticated media URL (Pitfall 6) treated as low-risk because "it's just images" | Evidence images are personal financial documents (proof of trades) tied to a single owner's identity — this is sensitive personal data, not throwaway content | Fix before go-live per PROJECT.md's own Active requirement — don't defer past this milestone |

## "Looks Done But Isn't" Checklist

- [ ] **Tunnel survives reboot:** Often "looks done" right after manual setup but was never actually tested across a real Pi reboot — verify by physically power-cycling (or `sudo reboot`) and confirming the domain resolves within a minute, not just checking `systemctl enable` was run.
- [ ] **CSRF/HTTPS settings:** Often "looks done" because the homepage loads fine over HTTPS — verify by actually submitting a real POST form (login, add a lot, add a sale) end-to-end through the public domain, not just GET-ing pages.
- [ ] **Media file protection:** Often "looks done" because the UI never links to raw `/media/` URLs for anyone but the logged-in owner — verify by hitting a known evidence file URL directly, unauthenticated (incognito window / `curl` with no cookies), and confirming it's rejected.
- [ ] **SQLite backup:** Often "looks done" because the database file obviously exists on disk — verify a backup actually exists *off* the SD card and that a restore from it has been test-run at least once, not just that a cron job "should" be running.
- [ ] **`DEBUG=False` on the Pi:** Often assumed true because `.env` "should" differ per environment — verify by triggering a real error path (e.g., temporarily breaking the yfinance call) on the live Pi deployment and confirming a generic error page, not a traceback, is shown.

## Recovery Strategies

| Pitfall | Recovery Cost | Recovery Steps |
|---------|-----------------|------------------|
| CSRF/redirect-loop misconfiguration after go-live | LOW | Fix the relevant setting (`SECURE_PROXY_SSL_HEADER` / `CSRF_TRUSTED_ORIGINS`), `systemctl restart` the Gunicorn service — no data at risk, purely a config error |
| `cloudflared` not surviving reboot | LOW | Re-run `cloudflared service install` + `systemctl enable cloudflared`, verify with a real reboot; no data loss, just downtime until fixed |
| SQLite corruption from power loss | HIGH if no backup exists, LOW if a recent off-device backup exists | Attempt `sqlite3 db.sqlite3 "PRAGMA integrity_check;"` and `.recover` first; if unrecoverable, restore the latest off-device backup and accept loss of transactions recorded since that backup — this is exactly why the backup cron (Pitfall 3) must exist before go-live, not after an incident |
| Unauthenticated media exposure discovered post-launch | MEDIUM | Immediately restrict via a Cloudflare Access rule on `/media/*` (fastest, no deploy needed) as a stopgap, then ship the proper authenticated-view fix; rotate/consider evidence files potentially already accessed as exposed |

## Pitfall-to-Phase Mapping

| Pitfall | Prevention Phase | Verification |
|---------|-------------------|----------------|
| `SECURE_PROXY_SSL_HEADER` missing → redirect loop | Settings hardening | `curl -H "X-Forwarded-Proto: https" -I https://<domain>` returns 200, not a redirect loop |
| `CSRF_TRUSTED_ORIGINS` placeholder/scheme mismatch | Settings hardening (domain-dependent step) | Submit a real form (login or add-lot) through the public domain and confirm no 403 |
| SQLite corruption from unclean power loss | Server setup | `PRAGMA journal_mode` returns `wal`; a scheduled off-device backup file exists and is dated within the last 24h |
| `cloudflared` not a proper systemd service / Quick Tunnel left in place | Tunnel setup | Reboot the Pi and confirm the domain resolves and serves the app without any manual intervention |
| `DEBUG=True` / permissive `ALLOWED_HOSTS` reaching production | Settings hardening | `python manage.py check --deploy` run against the Pi's actual `.env` reports no critical warnings |
| Unauthenticated media file access | Security-gaps-closing phase (explicit PROJECT.md Active item) | Unauthenticated request to a known evidence file URL is rejected (401/403), not streamed |
| ARM64 wheel/build failures | Server setup | Clean `pip install -r requirements.txt` on the actual Pi completes without falling back to a source build for `Pillow` (and any future compiled dependency) |
| Thermal throttling / undervoltage under load | Go-live verification | `vcgencmd get_throttled` returns `0x0` after a deliberate load test (e.g., generate a large report while polling the dashboard) |

## Sources

- [Security in Django — Django 6.0.4 documentation](https://django.readthedocs.io/en/stable/topics/security.html) — official, HIGH-tier
- [Deployment checklist | Django documentation](https://docs.djangoproject.com/en/6.0/howto/deployment/checklist/) — official, HIGH-tier
- [CSRF verification failed after putting behind SSL proxy — Django Forum](https://forum.djangoproject.com/t/csrf-verification-failed-request-aborted-after-putting-behind-ssl-proxy/29130)
- [Broken when Reverse Proxy - CSRF_TRUSTED_ORIGINS Missing — healthchecks/healthchecks Discussion](https://github.com/healthchecks/healthchecks/discussions/851)
- [Django ticket #34855 — Document CSRF_TRUSTED_ORIGINS relation to SECURE_PROXY_SSL_HEADER](https://code.djangoproject.com/ticket/34855)
- [Write-Ahead Logging — SQLite official docs](https://sqlite.org/wal.html) — official, HIGH-tier
- [How To Corrupt An SQLite Database File — SQLite official docs](https://www.sqlite.org/howtocorrupt.html) — official, HIGH-tier
- [Raspberry Pi 5 Randomly Corrupting Data During Long-Term SD Card Logging — Raspberry Pi Forums](https://forums.raspberrypi.com/viewtopic.php?p=2378202)
- [Set up Cloudflare Tunnel — Cloudflare official docs](https://developers.cloudflare.com/tunnel/setup/) — official, HIGH-tier
- [Quick Tunnels — Cloudflare One official docs](https://developers.cloudflare.com/cloudflare-one/networks/connectors/cloudflare-tunnel/do-more-with-tunnels/trycloudflare/) — official, HIGH-tier
- [🐛 Ingress rules ignored when using systemd — cloudflare/cloudflared#1031](https://github.com/cloudflare/cloudflared/issues/1031)
- [Implementing CloudFlare Tunnel for Secure Home Lab Access — DevOpsTales](https://devopstales.com/general/implementing-cloudflare-tunnel-for-secure-home-lab-access-a-complete-technical-guide/)
- [Locking Down Django Admin with Cloudflare Access at Zero Cost — Prodigy 13](https://prodigy13.com/locking-down-django-admin-with-cloudflare-access-at-zero-cost/)
- [Securely Deploy a Django App With Gunicorn, Nginx, & HTTPS — Real Python](https://realpython.com/django-nginx-gunicorn/)
- [Production-Grade Django Deployment with Gunicorn, Nginx, and systemd — Medium](https://tapanbasuli.medium.com/production-grade-django-deployment-with-gunicorn-nginx-and-systemd-76bc2b76585b)
- [Cannot install cryptography - newer version of pip required — Raspberry Pi Forums](https://forums.raspberrypi.com/viewtopic.php?t=343187)
- [psycopg2-binary wheels — piwheels/piwheels#68](https://github.com/bennuttall/piwheels/issues/68)
- [Raspberry Pi 4 Cases, Temperature and CPU Throttling Under Load — Martin Rowan](https://www.martinrowan.co.uk/2019/09/raspberry-pi-4-cases-temperature-and-cpu-throttling-under-load/)
- [Thermal testing Raspberry Pi 4 — Raspberry Pi official news](https://www.raspberrypi.com/news/thermal-testing-raspberry-pi-4/) — official, HIGH-tier
- [Fixing Raspberry Pi Degradation in Industrial Edge Deployments — Industrial Monitor Direct](https://industrialmonitordirect.com/blogs/knowledgebase/raspberry-pi-edge-deployment-failures-root-causes-and-solutions)
- Project-internal: `.planning/codebase/CONCERNS.md` (existing known gaps: `CSRF_TRUSTED_ORIGINS` placeholder, unprotected media serving, missing file-upload validation, `SECURE_SSL_REDIRECT` unset, SQLite write-contention risk)

---
*Pitfalls research for: Django + Cloudflare Tunnel + Raspberry Pi 4 self-hosted deployment*
*Researched: 2026-07-19*
