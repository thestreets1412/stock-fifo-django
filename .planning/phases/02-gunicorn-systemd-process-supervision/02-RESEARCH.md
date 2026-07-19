# Phase 2: Gunicorn + systemd Process Supervision - Research

**Researched:** 2026-07-19
**Domain:** WSGI process supervision (gunicorn) + Linux service management (systemd) for a single-user Django app on Raspberry Pi 4
**Confidence:** MEDIUM-HIGH

## Summary

This phase has two independent deliverables that both need to be true before Phase 5 can safely tunnel traffic in: (1) gunicorn replaces `manage.py runserver` and serves the app correctly, bound to `127.0.0.1` only, with whitenoise handling static files from inside the same process; and (2) a systemd unit supervises gunicorn — non-root user, `Restart=on-failure`, boot-start — verified by an actual Pi reboot. Because development happens on Windows and systemd does not exist there, this phase's artifacts split cleanly into two verification classes: what a `<verify>` block can actually check on this machine (gunicorn serves the app, whitenoise serves static assets, the systemd unit file parses/lints correctly with `systemd-analyze verify` if available, or at minimum is structurally correct against the documented schema) versus what can only be confirmed with `human_verification` on the real Pi (reboot survival, `Restart=on-failure` behavior after `kill -9`, actual non-root execution, `systemctl status` output).

Both `gunicorn` (26.0.0) and `whitenoise` (6.12.0) are current, actively maintained, PyPI-hosted packages confirmed via direct registry lookup; the package-legitimacy checker flags both `SUS` only because it lacks download-count telemetry for PyPI, not because of any actual red flag — both are cross-verified as legitimate via their maturity (gunicorn's PyPI version history goes back to 0.1; whitenoise is the package Django's own static-files docs commonly reference for non-CDN static serving) and official documentation. No new database, cache, or queue is introduced.

The ARM64/ARM64-wheel risk flagged in prior research was directly checked against PyPI's JSON API for this project's exact pinned dependency versions (not generic guidance): every currently pinned package that has historically needed compilation (`pillow`, `numpy`, `pandas`, `websockets`, `protobuf`, `curl_cffi`) publishes prebuilt `manylinux`/`abi3` **aarch64** wheels covering both Python 3.13 and 3.14 — meaning regardless of whether Raspberry Pi OS Trixie's system Python turns out to be 3.13 or the venv is built with 3.14, a compiled wheel should be available without a from-source build. This downgrades that risk from "unknown, needs on-device verification" to "verified low risk, but still worth a tracked dry-run" since PyPI wheel existence doesn't guarantee pip actually selects it on-device (network reachability, disk space, apt-vs-pip Python version mismatch). Separately, the actual historical "Fixing bug to run on local server (Raspberry Pi 4 x64 OS lite)" commit (`091d58c`) in this repo's history was **not** a compiled-dependency problem at all — it replaced `django.conf.urls.static.static()` (which only serves media when `DEBUG=True`) with a `re_path(...serve...)` mapping so media works with `DEBUG=False`. That change is what created the unauthenticated-media-serving gap Phase 3 (SEC-01) exists to fix — it is unrelated to this phase's process-supervision concerns, and prior research's inference linking that commit to ARM64 wheel risk does not hold up under inspection of the actual diff.

**Primary recommendation:** Add `gunicorn==26.0.0` and `whitenoise==6.12.0` to `requirements.txt`; wire `whitenoise.middleware.WhiteNoiseMiddleware` in immediately after `SecurityMiddleware` with `STORAGES['staticfiles']['BACKEND'] = 'whitenoise.storage.CompressedManifestStaticFilesStorage'`; author a `gunicorn.service` systemd unit with `Type=simple`, `ExecStart` calling the venv's gunicorn binary bound to `127.0.0.1:8000` with 2 sync workers, `Restart=on-failure`, a dedicated non-root `User=`, `WorkingDirectory=` set to the project root, and baseline hardening (`NoNewPrivileges=yes`, `PrivateTmp=yes`, `ProtectSystem=strict` + explicit `ReadWritePaths=` for the SQLite db and media directories); verify everything not requiring systemd locally on Windows, and gate the reboot/`Restart=on-failure`/non-root checks as explicit `human_verification` items to run on the Pi.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| WSGI request serving | API/Backend (Gunicorn process) | — | Gunicorn is the WSGI server hosting the unchanged Django app; replaces `runserver` |
| Static file serving | API/Backend (Gunicorn process, via whitenoise middleware) | — | Whitenoise serves `/static/` from inside the same process — no CDN/edge tier or separate static server in this milestone (Cloudflare's edge caches it opportunistically in Phase 5+, but doesn't originate it) |
| Process lifecycle (start/stop/restart/boot) | OS / systemd | — | systemd is OS-level process supervision, outside the application tier entirely; owns crash-restart and boot-start, not Django or gunicorn |
| Media file serving | API/Backend (Django view) | — | Out of scope for this phase (Phase 3/SEC-01); noted here only because it's adjacent to static-file work and easy to conflate |
| Loopback network binding | OS / systemd (via `ExecStart --bind`) | API/Backend (gunicorn) | The bind address is a gunicorn startup argument but the *guarantee* that nothing external can reach it is enforced by the absence of any port-forward/tunnel at this phase — purely local trust boundary |

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|--------------------|
| PROC-01 | App runs under gunicorn (not `runserver`), bound to `127.0.0.1` only | Standard Stack (gunicorn 26.0.0), Architecture Pattern 1 (direct-bind, no reverse proxy), Anti-Patterns (never bind `0.0.0.0`), Code Examples (local verification command) |
| PROC-02 | gunicorn runs as a systemd service — non-root user, `Restart=on-failure`, starts on boot — verified with an actual Pi reboot | Architecture Pattern 3 (systemd hardening baseline unit file), Common Pitfalls (Pitfall 1: split local-vs-Pi verification), Security Domain (least-privilege execution, `Restart=on-failure` as availability mitigation), Open Question 2 (non-root user sourcing) |
| PROC-03 | Static files are served via whitenoise from within the gunicorn process (no second server needed) | Standard Stack (whitenoise 6.12.0), Architecture Pattern 2 (middleware placement + `STORAGES` config), Common Pitfalls (Pitfall 2: `collectstatic` requirement) |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|---------------|
| gunicorn | 26.0.0 [VERIFIED: PyPI registry `pip index versions gunicorn`] | WSGI HTTP server hosting the Django app in place of `runserver` | The de facto standard synchronous WSGI server for Django deployments; official Django deployment docs and this project's own prior milestone research (SUMMARY.md) both converge on it; right-sized for a single-user app vs. uWSGI/ASGI servers that add unneeded complexity |
| whitenoise | 6.12.0 [VERIFIED: PyPI registry `pip index versions whitenoise`] | Serves `/static/` compressed and cache-busted from inside the gunicorn process | Eliminates the need for a second static-file server or reverse proxy, consistent with this project's "no local reverse proxy" architectural decision (STACK.md/SUMMARY.md) |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| systemd (OS-provided, not pip-installed) | Whatever ships with Raspberry Pi OS Lite (Trixie) | Process supervision: boot-start, crash-restart, non-root execution | Already present on the target OS — no package to install; this phase authors unit files, doesn't install systemd itself |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| gunicorn (sync workers) | uWSGI | More configuration surface, more moving parts (its own init system, `.ini` config format) for zero measurable benefit at single-user scale; gunicorn's PyPI-native config and simpler systemd integration wins here |
| gunicorn (sync workers) | Uvicorn/ASGI + `config.asgi` | The app has no async views, websocket, or long-poll requirements; ASGI adds a dependency and conceptual overhead this app doesn't need. `config/asgi.py` exists but is unused scaffolding from `startproject` |
| systemd | supervisord / pm2 | Adds a second process-management layer on top of an OS that already ships systemd; pure overhead for one service on one box (already excluded in PROJECT.md's Out of Scope) |
| whitenoise | nginx serving `/static/` directly | Reintroduces the reverse-proxy question this project's research explicitly resolved against (SUMMARY.md's "Reconciling the reverse-proxy question") — an extra systemd unit and attack surface for zero benefit since Cloudflare's edge already caches static assets |

**Installation:**
```bash
pip install gunicorn==26.0.0 whitenoise==6.12.0
# then update requirements.txt (pin exact versions, matching existing project convention)
```

**Version verification:** Verified directly against the PyPI index (not training-data recall):
```
$ pip index versions gunicorn
gunicorn (26.0.0)          # latest, confirmed 2026-07-19
$ pip index versions whitenoise
whitenoise (6.12.0)        # latest, confirmed 2026-07-19
```
Both also confirmed via PyPI's JSON API to declare `requires_python >= 3.10` with no upper bound (gunicorn) and explicit `Python :: 3.14` classifier support (whitenoise) — compatible with this project's Python 3.14.6 dev environment and with a Python 3.13 Pi environment.

## Package Legitimacy Audit

| Package | Registry | Age | Downloads | Source Repo | Verdict | Disposition |
|---------|----------|-----|-----------|--------------|---------|-------------|
| gunicorn | PyPI | Version history back to 0.1 (mature, 15+ years) | Unknown to legitimacy checker (no telemetry signal available for PyPI) | https://gunicorn.org (official project site; source at github.com/benoitc/gunicorn) | SUS (reason: `unknown-downloads`) | **Approved** — false positive; overridden on manual verification (long version history, official docs cross-checked, matches prior project-level research) |
| whitenoise | PyPI | Version history back to 0.9 (mature) | Unknown to legitimacy checker (no telemetry signal available for PyPI) | Not returned by checker (`repoUrl: null`); confirmed manually at github.com/evansd/whitenoise | SUS (reasons: `unknown-downloads`, `no-repository`) | **Approved** — false positive; overridden on manual verification (official Django-adjacent docs at whitenoise.readthedocs.io, long version history, widely referenced in Django community deployment guides) |

**Packages removed due to [SLOP] verdict:** none.
**Packages flagged as suspicious [SUS]:** gunicorn, whitenoise — both are false positives caused by the legitimacy checker lacking a PyPI download-count data source, not by any genuine red flag. Both are approved based on manual cross-verification (version-history depth, official documentation, and corroboration in this project's own prior milestone-level research). No `checkpoint:human-verify` is required before installing these two specific packages, but the planner should still note the false-positive-SUS disposition in the plan so a future auditor understands why these weren't gated.

*No other new packages are introduced by this phase's requirements. `requirements.txt`'s existing pinned dependencies were independently re-checked for ARM64/aarch64 wheel availability — see Runtime State Inventory-adjacent finding under Common Pitfalls (Pitfall 4) — using direct PyPI JSON API queries, not training-data recall.*

## Architecture Patterns

### System Architecture Diagram

```
                     [ Loopback only — no tunnel exists yet in this phase ]

  curl / browser on the Pi itself
            │  HTTP GET/POST to http://127.0.0.1:8000/...
            ▼
  ┌─────────────────────────────────────────────────────────┐
  │ systemd (PID 1, OS-level)                                │
  │  ├─ gunicorn.service  (Restart=on-failure, User=appuser)  │
  │  │     │ ExecStart: <venv>/bin/gunicorn                   │
  │  │     │             config.wsgi:application               │
  │  │     │             --bind 127.0.0.1:8000 --workers 2      │
  │  │     ▼                                                    │
  │  │   ┌─────────────────────────────────────────────────┐   │
  │  │   │ Gunicorn arbiter + N sync worker processes        │   │
  │  │   │   ├─ WhiteNoiseMiddleware  → serves /static/*      │   │
  │  │   │   │      (reads pre-collected files under          │   │
  │  │   │   │       STATIC_ROOT, no disk I/O to app code)     │   │
  │  │   │   └─ Django URL dispatch → views → services → ORM   │   │
  │  │   │           └─ SQLite (db.sqlite3, same filesystem)   │   │
  │  │   └─────────────────────────────────────────────────┘   │
  │  └────────────────────────────────────────────────────────┘   │
  └─────────────────────────────────────────────────────────────┘

  Boot sequence: systemd starts gunicorn.service automatically
  (WantedBy=multi-user.target + `systemctl enable`) — no manual
  command needed after a reboot.

  Crash sequence: if a worker/arbiter process dies (kill -9, OOM),
  systemd's Restart=on-failure relaunches gunicorn.service after
  RestartSec, without operator intervention.
```

A reader can trace the primary use case (a request hits the app and gets a response) top-to-bottom: systemd keeps the gunicorn arbiter alive → arbiter dispatches to a worker → worker's middleware stack either short-circuits to whitenoise for static assets or proceeds into Django's normal view/service/ORM stack, identical to how it behaves under `runserver` today.

### Recommended Project Structure
```
stock-fifo-django/
├── config/
│   ├── settings.py       # add WhiteNoiseMiddleware + STORAGES; no other changes needed
│   ├── wsgi.py            # UNCHANGED — already exposes `application`, gunicorn's target
│   └── gunicorn_conf.py   # NEW (optional but recommended) — bind, workers, timeout as code, not just CLI flags
├── deploy/                # NEW — suggested location for Pi-only artifacts authored on Windows
│   └── systemd/
│       └── gunicorn.service   # NEW — reviewed here, installed to /etc/systemd/system/ on the Pi
├── requirements.txt        # add gunicorn==26.0.0, whitenoise==6.12.0
└── staticfiles/            # UNCHANGED — collectstatic output target, already configured in settings.py
```
Placing the `.service` file under `deploy/systemd/` (in-repo, version-controlled) rather than editing it live on the Pi means the Pi's copy is always a `cp`/symlink from a reviewed, committed artifact — consistent with this project's "runbook" requirement (DEPLOY-05) in a later phase.

### Pattern 1: Direct-bind, no reverse proxy, no socket activation
**What:** Gunicorn binds directly to a TCP port on loopback (`--bind 127.0.0.1:8000`) rather than a Unix domain socket, and is *not* fronted by nginx/Caddy.
**When to use:** Single-user or low-traffic deployments where Cloudflare's edge (Phase 5) or, for this phase, nothing at all, is the only client — matches this project's already-locked "no local reverse proxy" decision.
**Why not socket activation:** Gunicorn's own official docs (gunicorn.org/deploy) demonstrate systemd socket activation (`.socket` + `.service` pair, `Type=notify`) — but that pattern exists to hand a pre-opened socket to nginx/gunicorn for permission and zero-downtime-restart reasons that don't apply here (no nginx, single user, restart downtime is explicitly out-of-scope-to-avoid per PROJECT.md's Out of Scope table: *"a few seconds of restart downtime is a non-issue for a single user"*). A plain `Type=simple` unit with a TCP bind is simpler to author, simpler to verify locally, and has no socket-permission edge cases (`SocketUser`/`SocketMode`) to get wrong.
**Example (`gunicorn.conf.py`, loaded via `--config`):**
```python
# Source: pattern synthesized from gunicorn.org/deploy + this project's
# "no reverse proxy" architectural decision (SUMMARY.md)
bind = "127.0.0.1:8000"
workers = 2
worker_class = "sync"
timeout = 60          # see Pitfall 3 — default 30s is too tight for this app's
                       # dashboard price-fetch loop
accesslog = "-"        # stdout, captured by systemd/journald — no separate log file needed
errorlog = "-"
```

### Pattern 2: WhiteNoise middleware placement
**What:** `whitenoise.middleware.WhiteNoiseMiddleware` inserted immediately after `SecurityMiddleware`, before every other middleware.
**When to use:** Always, per WhiteNoise's own documented requirement — order matters because WhiteNoise short-circuits static-file requests before they reach session/CSRF/auth middleware (static assets need none of that processing).
**Example:**
```python
# Source: https://whitenoise.readthedocs.io/en/stable/django.html (WhiteNoise 6.12.0 docs)
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',   # NEW — must be here, not later
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}
```
Note: Django 6.0's `STORAGES` setting requires both `default` and `staticfiles` keys to be present if you define `STORAGES` at all — the current `settings.py` has no `STORAGES` block yet, so this is a net-new addition, not a modification of an existing one; the `default` entry above preserves Django's existing `FileSystemStorage` behavior for `media/` uploads (unaffected by this phase).

### Pattern 3: systemd unit hardening baseline
**What:** A small set of directives that meaningfully reduce blast radius for a non-root, internet-adjacent (eventually, post-Phase-5) service without breaking functionality.
**When to use:** Any long-running network service on a device with no other tenants to protect against — still worth doing since the tunnel (Phase 5) will eventually make this reachable from the internet.
**Example:**
```ini
# Source: pattern synthesized from systemd.exec(5) semantics + community
# WSGI-service hardening guides cross-checked against multiple sources — CITED, not project-authoritative
[Unit]
Description=Gunicorn WSGI server for Stock FIFO Tracker
After=network.target

[Service]
Type=simple
User=appuser
Group=appuser
WorkingDirectory=/home/appuser/stock-fifo-django
Environment=PATH=/home/appuser/stock-fifo-django/.venv/bin
ExecStart=/home/appuser/stock-fifo-django/.venv/bin/gunicorn \
    --config /home/appuser/stock-fifo-django/config/gunicorn_conf.py \
    config.wsgi:application
Restart=on-failure
RestartSec=5
NoNewPrivileges=yes
PrivateTmp=yes
ProtectSystem=strict
ReadWritePaths=/home/appuser/stock-fifo-django

[Install]
WantedBy=multi-user.target
```
`ReadWritePaths` must cover the *entire* project directory (not just `db.sqlite3`) because SQLite's default rollback-journal mode creates a `-journal` sidecar file next to the db on every write, and Django's `media/` uploads and `staticfiles/` (post-`collectstatic`) both live under the same tree — `ProtectSystem=strict` makes everything else on the filesystem read-only to this service, which is the point (least privilege), but must not accidentally block the app's own writes.

### Anti-Patterns to Avoid
- **Editing the systemd unit file live on the Pi via `nano`/`vim` with no copy in git:** Defeats the purpose of a reviewable, versioned deployment artifact and makes DEPLOY-05's runbook requirement (Phase 5) harder to write accurately later. Keep the unit file in the repo (`deploy/systemd/gunicorn.service`) and `cp`/symlink it into `/etc/systemd/system/` on the Pi.
- **Binding gunicorn to `0.0.0.0` "just to test from another device on the LAN":** Directly contradicts PROC-01 and the settings.py inline warning already left by Phase 1 (`config/settings.py:35-39`) that trusting `X-Forwarded-Proto` is only safe once gunicorn is loopback-only — binding to all interfaces before Phase 5's tunnel exists reopens the CSRF-forgery risk that comment explicitly calls out.
- **Using `systemctl start` without `systemctl enable`:** Starts the service for the current boot only; `enable` is what wires the boot-start requirement (PROC-02/success criterion 3) via the `[Install]` section's `WantedBy=`.
- **Relying on gunicorn's default `--timeout 30`:** See Pitfall 3 below — this app's dashboard view has a codebase-verified worst-case latency path that can legitimately exceed 30 seconds under normal (not pathological) conditions.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|--------------|-----|
| Keeping a Python process alive across crashes/reboots | A custom bash `while true; do python manage.py runserver; done` loop, cron `@reboot` entry, or a `nohup`/`screen` session | systemd `Restart=on-failure` + `WantedBy=multi-user.target` | systemd is already present on the OS, handles PID tracking, logging integration (journald), graceful shutdown signals, and restart backoff correctly — a shell loop reinvents all of this worse and has no supervision of *itself* |
| Serving static files in production | A custom Django view that reads files off disk and streams them | whitenoise middleware | Whitenoise handles ETags, compression, cache-control headers, and the manifest-based cache-busting filename scheme correctly; a hand-rolled view would need to reimplement all of this to be production-safe, and would likely have worse performance than middleware that short-circuits before hitting the ORM/template layers |
| Multi-process WSGI serving with worker recycling | A custom `multiprocessing`-based request dispatcher in front of Django's dev server | gunicorn | Gunicorn's arbiter/worker model already handles graceful worker restarts, `SIGTERM`/`SIGHUP` semantics, and pre-fork worker isolation — this is a genuinely deceptive-complexity problem (looks like "just fork N processes," actually involves careful signal handling to avoid dropped connections during restarts) |

**Key insight:** Every piece of this phase (process supervision, static serving, WSGI multiplexing) has a mature, boring, single-purpose tool that already solves it correctly. The temptation on a resource-constrained device like a Pi 4 is to reach for something "lighter," but gunicorn+whitenoise+systemd is already about as light as this stack gets — hand-rolling any of these three pieces adds code to maintain without reducing resource usage meaningfully.

## Common Pitfalls

### Pitfall 1: Windows dev machine can't functionally test systemd
**What goes wrong:** A `<verify>` block that assumes `systemctl status gunicorn` or `systemctl is-enabled gunicorn` will run during plan execution — it can't, because this development machine is Windows and systemd doesn't exist here.
**Why it happens:** Most gunicorn+systemd tutorials assume the author is working directly on the target Linux box.
**How to avoid:** Split verification explicitly in the plan: (a) locally verifiable — gunicorn actually serves the Django app correctly (`gunicorn config.wsgi:application --bind 127.0.0.1:8000` run manually in the venv, curl a few known routes, confirm whitenoise serves a static asset with correct headers after `collectstatic`), and the `.service` file is syntactically well-formed (validate with `systemd-analyze verify` if a Linux environment/WSL/container is available for a quick syntax check, or failing that, manually review against the documented INI schema); (b) Pi-only — mark reboot survival, `Restart=on-failure` after a `kill -9`, and actual non-root process ownership (`ps aux | grep gunicorn` showing the dedicated user, not root) as explicit `human_verification` steps in the plan, not automated `<verify>` blocks.
**Warning signs:** A plan task with a `<verify>` block containing `systemctl` commands and no accompanying note that it must be run on the Pi, not locally.

### Pitfall 2: `manage.py collectstatic` never run, whitenoise serves nothing
**What goes wrong:** WhiteNoise's `CompressedManifestStaticFilesStorage` reads from `STATIC_ROOT` (already configured as `BASE_DIR / 'staticfiles'` in this project) — if `collectstatic` was never run (or was run before a template/CSS change), whitenoise 404s on assets that exist fine under `runserver`'s dev-mode static handling.
**Why it happens:** `runserver` with `DEBUG=True` serves static files directly from each app's `static/` directory without needing `collectstatic` at all — this behavior difference is invisible until you switch to gunicorn+whitenoise+`DEBUG=False`.
**How to avoid:** Make `collectstatic --noinput` an explicit, verified step (either as a manual pre-deploy command documented in this phase, or wired into the systemd unit's `ExecStartPre=`) before gunicorn starts serving. Verify locally: run with `DEBUG=False`, confirm CSS/JS actually loads in a browser hitting `127.0.0.1:8000`, not just that the homepage HTML renders.
**Warning signs:** Page loads but unstyled (no Bootstrap CSS); browser devtools network tab shows 404s under `/static/`.

### Pitfall 3: Gunicorn's default 30s worker timeout is too short for this app's dashboard view
**What goes wrong:** `build_dashboard_summary()` in `portfolio/services.py` fetches each symbol's live price **sequentially**, one `ThreadPoolExecutor(max_workers=1)` per symbol, each individually bounded to `PRICE_FETCH_TIMEOUT_SECONDS = 5` (verified by direct code read, `portfolio/services.py:108,128-130,166-190`). With gunicorn's default `--timeout 30`, a portfolio with 7+ symbols where several are slow/timing out (5s each) can legitimately exceed the worker timeout, causing gunicorn to `SIGKILL` the worker mid-request — the user sees a connection reset instead of a graceful degraded dashboard (which is what the code is actually designed to return).
**Why it happens:** This isn't a hypothetical edge case — it's a direct consequence of code that already exists and is explicitly designed to degrade gracefully per-symbol, but that graceful-degradation design assumes the *request itself* is allowed to run long enough to try every symbol.
**How to avoid:** Set an explicit, generous `timeout` in the gunicorn config (60-120s is reasonable headroom for a single-user app where a slightly slower dashboard load is a non-issue) rather than relying on the default. This is a gunicorn config value, not a code change — no application code needs to be touched in this phase.
**Warning signs:** Dashboard loads fine with 1-2 symbols in testing but reset-connects with a fuller portfolio; symptom would likely not appear in this phase's own local verification unless the test portfolio has enough symbols with induced slow/failing price fetches to trigger it — worth calling out as a known limitation even if not reproduced in Phase 2 testing, since it's a real latent risk for Phase 5's go-live smoke test.

### Pitfall 4: ARM64 wheel availability — verified low risk, not "unknown"
**What goes wrong (if unaddressed):** Assuming a `pip install -r requirements.txt` on the Pi will "just work" without ever having checked, when in fact compiled-extension packages (`pillow`, `numpy`, `pandas`, `curl_cffi`, etc.) could in principle require a from-source build that times out, runs out of disk/RAM, or fails on a Pi.
**What this research found:** Every one of this project's currently pinned dependencies that has a compiled component was checked directly against PyPI's JSON API for aarch64 wheel availability at the exact pinned version (see Standard Stack section and cached research finding) — all have prebuilt wheels covering both Python 3.13 and 3.14. `reportlab==5.0.0` is pure Python (`py3-none-any`), no compilation risk at all. This is a materially different, more confident finding than "flagged as needing verification" — it's now "verified likely-fine, but still worth confirming on-device since PyPI metadata isn't a install-time guarantee."
**How to avoid:** Still include an explicit `pip install -r requirements.txt` dry-run as a tracked step on the Pi (not skipped just because this research found low risk) — the gap between "wheel exists on PyPI" and "pip actually resolves and installs it successfully on this specific device" is real (network reachability to pypi.org from the Pi, disk space for the venv, apt's system Python version vs. what the venv targets). Document the dry-run's *expected* outcome (clean install, no compiler invoked) so a failure is immediately recognizable as unexpected rather than "the risk we already knew about."
**Warning signs:** `pip install` invoking `gcc`/`cc1`/`cargo` for any of these packages, taking multiple minutes per package, or failing with a missing system header/library error.

### Pitfall 5: Historical Pi bug was a Django routing issue, not a process-supervision issue — don't conflate them
**What goes wrong:** Assuming the commit `091d58c` ("Fixing bug to run on local server (Raspberry Pi 4 x64 OS lite)") in this repo's history is evidence of a gunicorn/systemd/dependency problem to solve in this phase.
**Why it happens:** The commit message references "Raspberry Pi" and this phase is Pi-deployment-focused, making the association tempting.
**What it actually was (verified by reading the diff):** It replaced `django.conf.urls.static.static()` (a helper that only wires up media serving when `DEBUG=True`) with an explicit `re_path(r'^media/...', serve, ...)` mapping so media files would still be reachable once `DEBUG=False` on the Pi. This is exactly the change that created the unauthenticated-media-serving gap that Phase 3 (SEC-01) exists to close — it has nothing to do with process supervision, gunicorn, or ARM64 wheels.
**How to avoid:** Don't let this phase's plan include tasks aimed at "fixing the Pi media bug" — that's explicitly Phase 3's job and doing it here would create scope overlap/duplication between phases. This phase should not touch `config/urls.py`'s media routing at all.

## Code Examples

### Manual local verification (Windows-runnable, no systemd needed)
```bash
# Source: pattern synthesized from gunicorn CLI docs — runnable on this dev machine
.venv/Scripts/python.exe -m pip install gunicorn whitenoise
.venv/Scripts/python.exe manage.py collectstatic --noinput
DEBUG=False .venv/Scripts/gunicorn.exe config.wsgi:application --bind 127.0.0.1:8000
# separately: curl http://127.0.0.1:8000/ and a known static asset URL, confirm 200 + correct headers
```
Note: gunicorn's own docs describe it as Unix-oriented; on native Windows Python, `gunicorn` typically fails to import (it depends on `fcntl`/`os.fork`, which don't exist on Windows) — **this must be verified early in planning**, and if confirmed, local verification of the actual gunicorn process should instead run inside a Linux environment available to this dev setup (WSL, if present, or a container) rather than natively on Windows. This is a concrete open question flagged below, not an assumption to plan around silently.

### WhiteNoise settings.py diff (illustrative)
```python
# Source: https://whitenoise.readthedocs.io/en/stable/django.html
# Add to config/settings.py, MIDDLEWARE list — insert as second entry
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    # ...unchanged rest of the list...
]

STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
}
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|-------------------|---------------|--------|
| `django.conf.urls.static.static()` for `/media/` (DEBUG-only) | Explicit `re_path(...serve...)` (this project, commit `091d58c`) | Already changed in this repo, pre-Phase-1 | Media serving now works regardless of `DEBUG`, but introduced the unauthenticated-access gap Phase 3 fixes — not this phase's concern |
| `STATICFILES_STORAGE` setting (Django <4.2 style) | `STORAGES` dict setting (Django 4.2+) | Django 4.2 (2023) | This project is on Django 6.0.7, so the `STORAGES` dict form is required — a plan that writes the old `STATICFILES_STORAGE = "..."` single-value setting would still technically work (Django keeps it as a deprecated-but-functional shim in some versions) but should not be used as the "current" pattern for a Django 6 codebase |

**Deprecated/outdated:**
- Single-string `STATICFILES_STORAGE` setting: superseded by the `STORAGES` dict — use the dict form for a Django 6 project.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|-----------------|
| A1 | Raspberry Pi OS Trixie's default system Python is 3.13 (not yet confirmed on the actual device) | Common Pitfalls (Pitfall 4), Summary | Low — this research already verified aarch64 wheels exist for both 3.13 and 3.14 for every checked package, so this assumption doesn't change the wheel-availability conclusion either way; only matters for exact venv-creation instructions in the plan |
| A2 | Native Windows Python cannot run gunicorn directly (missing `fcntl`) | Code Examples | Medium — if wrong, local verification is simpler than planned (can run gunicorn directly on Windows); if right and unaddressed, a plan task assuming `gunicorn config.wsgi:application` runs natively on Windows would fail immediately and block Phase 2 verification. Planner should treat this as an open question to resolve at plan-execution time (test early, fall back to WSL/container if it fails) rather than a locked assumption |
| A3 | 2 sync workers is an adequate gunicorn worker count for this single-user app on Pi 4 | Standard Stack, Architecture Patterns | Low — even if suboptimal, this is a `gunicorn.conf.py` value that's trivially adjustable later without any code change; not a hard architectural commitment |
| A4 | `gunicorn.conf.py` timeout of 60-120s adequately covers Pitfall 3's worst-case dashboard latency | Common Pitfalls (Pitfall 3) | Low-Medium — if the user's actual portfolio has many more symbols than assumed, even 120s might not be enough; this is a config value, easy to raise further, but worth flagging to the planner as a "tune this if it's still too tight" note rather than a guaranteed-correct number |

**If this table is empty:** N/A — see entries above; all are LOW-MEDIUM risk config/environment values, not architectural decisions requiring user confirmation before execution.

## Open Questions

1. **Can gunicorn run natively on this Windows dev machine for local verification, or is a Linux environment (WSL/container) required?**
   - What we know: Gunicorn's arbiter/worker model historically depends on Unix-only APIs (`fcntl`, `os.fork`); it is not officially supported on Windows.
   - What's unclear: Whether this specific dev environment has WSL available as a fallback, or whether verification should instead rely more heavily on Django's own test client / `runserver` parity checks plus a Pi-side manual smoke test.
   - Recommendation: The plan's first task should attempt `pip install gunicorn` + a direct run in the project venv and treat failure as expected-and-handled (not a blocker) — fall back to whatever Linux-capable environment is available (WSL if present) for the "gunicorn actually serves the app" verification step; if no Linux environment exists at all on this machine, that specific verification step becomes Pi-only (`human_verification`) rather than locally automatable, which should be stated explicitly in the plan rather than silently skipped.

2. **Does the Pi already have a dedicated non-root system user for this app, or does this phase need to create one?**
   - What we know: PROC-02 requires gunicorn to run as a non-root user; no existing project documentation mentions a dedicated `appuser`-style account already existing on the Pi.
   - What's unclear: Whether the Pi's existing default user (likely `pi` or a custom login user, given "already running the app locally" per PROJECT.md) is acceptable to use as the systemd `User=`, or whether a fresh dedicated service account should be created (`useradd --system` style) for tighter isolation.
   - Recommendation: Default to using the Pi's existing non-root login user (simpler, no new account-management step, still satisfies "non-root") unless the user has a stated preference for a dedicated service account — flag as a planner/discuss-phase decision point rather than assuming either way.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|--------------|-----------|---------|-----------|
| gunicorn (Python package) | PROC-01 | ✗ (not yet installed) | target 26.0.0 | `pip install` — no fallback needed, just not yet done |
| whitenoise (Python package) | PROC-03 | ✗ (not yet installed) | target 6.12.0 | `pip install` — no fallback needed |
| systemd | PROC-02 | ✗ on this dev machine (Windows); presumed ✓ on Raspberry Pi OS Lite (ships with systemd by default) | — (OS-provided on Pi) | See Open Question 1 — WSL/container as a local Linux fallback for gunicorn-only checks; systemd itself has no local fallback and its checks are inherently Pi-only |
| Raspberry Pi 4 hardware | PROC-02 success criterion (reboot test) | ✗ not accessible from this session | — | None — reboot verification is unavoidably a `human_verification` step performed by the user on the actual device |
| Python 3.14.6 (dev) / Python 3.13 or 3.14 (Pi, unconfirmed) | Both packages | ✓ (dev) / unconfirmed (Pi) | 3.14.6 (dev, verified via `python --version`) | None needed — both target packages have wheels for either Python version per Pitfall 4 findings |

**Missing dependencies with no fallback:**
- Raspberry Pi 4 hardware access for the reboot/`Restart=on-failure`/non-root verification — inherent to the phase's own description ("systemd does not exist on Windows... cannot be functionally executed/tested on this dev machine"), not an oversight. Plan must gate these behind `human_verification`.

**Missing dependencies with fallback:**
- systemd for gunicorn-only (non-supervision) checks — WSL or a container, if available, can validate that gunicorn itself serves the app correctly outside of Windows' native limitations, without needing the full Pi.

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|-----------------|---------|---------------------|
| V1 Architecture | Yes | Least-privilege process execution — gunicorn under a dedicated non-root systemd `User=`, not root; loopback-only bind as the trust boundary for this phase (no tunnel yet) |
| V14 Configuration | Yes | systemd unit hardening directives (`NoNewPrivileges`, `PrivateTmp`, `ProtectSystem=strict` + `ReadWritePaths`); static files served read-only from a pre-collected directory, not writable by the running service beyond its own project tree |
| V2 Authentication | No | Not touched by this phase — no auth code changes |
| V3 Session Management | No | Not touched by this phase |
| V4 Access Control | No | Media access control is Phase 3's concern (SEC-01), not this phase |
| V5 Input Validation | No | No new user input surface introduced by process-supervision changes |
| V6 Cryptography | No | No cryptographic code introduced |

### Known Threat Patterns for this stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|-----------------------|
| Gunicorn process running as root, compromised app process gains root on the Pi | Elevation of Privilege | Dedicated non-root systemd `User=`/`Group=` (PROC-02's own explicit requirement) |
| Gunicorn accidentally bound to `0.0.0.0` instead of `127.0.0.1`, reachable from the LAN before the tunnel/auth layers exist | Elevation of Privilege / Information Disclosure | `--bind 127.0.0.1:PORT` explicitly, verified with a `curl` test from the loopback interface and (if feasible) confirmation that the bind address is *not* reachable from another LAN device during this phase's testing window |
| A compromised gunicorn worker process writes/deletes files outside the app's own directory (e.g. tampering with system files) | Tampering | `ProtectSystem=strict` + narrowly-scoped `ReadWritePaths=` limits the blast radius of an in-process compromise to the app's own directory tree, not the whole filesystem |
| systemd unit misconfigured without `Restart=on-failure`, service silently stays down after a crash, financial data becomes unreachable (not a confidentiality/integrity issue, but an availability one relevant to the single-user "always reachable" core value) | Denial of Service (self-inflicted) | `Restart=on-failure` + `RestartSec` explicitly set and verified on the Pi via a real `kill -9` test, not assumed from the unit file's presence alone |

## Sources

### Primary (HIGH confidence)
- [gunicorn · PyPI](https://pypi.org/project/gunicorn/) — version 26.0.0 confirmed via `pip index versions`, `requires_python` and classifiers confirmed via PyPI JSON API
- [whitenoise · PyPI](https://pypi.org/project/whitenoise/) — version 6.12.0 confirmed via `pip index versions`, Python 3.14 classifier confirmed via PyPI JSON API
- PyPI JSON API direct queries (`https://pypi.org/pypi/<pkg>/json`) for `pillow==12.3.0`, `numpy==2.5.1`, `pandas==3.0.3`, `websockets==16.1`, `protobuf==7.35.1`, `curl_cffi==0.15.0`, `reportlab==5.0.0` — aarch64/manylinux wheel availability confirmed directly, not from training data
- This repository's own git history (`git show 091d58c`) — direct diff inspection correcting a prior-research inference about the "Pi bug fix" commit
- This repository's own source (`portfolio/services.py`, `config/settings.py`, `config/wsgi.py`, `requirements.txt`) — direct code read for the timeout/worker-latency finding (Pitfall 3) and current middleware/settings state

### Secondary (MEDIUM confidence)
- [Deploy - Gunicorn](https://gunicorn.org/deploy/) — official systemd socket-activation pattern (WebSearch + WebFetch, official source)
- [Using WhiteNoise with Django](https://whitenoise.readthedocs.io/en/stable/django.html) — official WhiteNoise 6.12.0 docs (WebFetch, official source)
- Community systemd hardening guides (multiple, cross-checked) for `NoNewPrivileges`/`PrivateTmp`/`ProtectSystem` directive behavior — not an official single source, corroborated across several results
- [PiWheels - Home](https://www.piwheels.org/) and Raspberry Pi Forums threads on Trixie pip/wheel behavior — corroborating context for the ARM64 wheel finding, though the PyPI-direct verification above is the authoritative check for this project's specific dependencies

### Tertiary (LOW confidence)
- Various blog/tutorial gunicorn worker-count guidance (Medium articles, dev.to posts) — used only for the general "fewer workers on memory-constrained devices" heuristic, treated as a starting recommendation (2 workers) rather than a hard number; adjustable without code changes

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — both packages version-verified directly against PyPI registry, cross-referenced with official docs
- Architecture: MEDIUM-HIGH — direct-bind/no-proxy pattern already locked by prior project research; systemd hardening directives corroborated across multiple sources but not from a single official "best practices" doc
- Pitfalls: HIGH for Pitfalls 3-5 (all verified directly against this project's own code/git history, not generic guidance); MEDIUM for Pitfalls 1-2 (well-established patterns, not project-specific verification needed)

**Research date:** 2026-07-19
**Valid until:** 30 days (stable ecosystem — gunicorn/whitenoise/systemd all mature, low-churn tools; re-verify package versions if planning is delayed past that window)
