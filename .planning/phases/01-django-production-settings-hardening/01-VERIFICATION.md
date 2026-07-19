---
phase: 01-django-production-settings-hardening
verified: 2026-07-19T12:00:00Z
status: passed
score: 7/7 must-haves verified
behavior_unverified: 0
overrides_applied: 0
---

# Phase 1: Django Production Settings Hardening Verification Report

**Phase Goal:** Django's security settings are production-ready and verified locally — `SECURE_PROXY_SSL_HEADER`, `SECURE_SSL_REDIRECT`, secure cookies, HSTS, and `.env`-driven `CSRF_TRUSTED_ORIGINS`/`ALLOWED_HOSTS` — so the app behaves correctly once it sits behind Cloudflare's tunnel and doesn't leak debug information in production.
**Verified:** 2026-07-19T12:00:00Z
**Status:** passed
**Re-verification:** No — initial verification

**Note on scope:** SUMMARY.md documents the initial plan execution only. A subsequent code-review pass (`01-REVIEW.md`) found 3 warnings, all fixed in `01-REVIEW-FIX.md` (commits `14f27b4`, `667f1cd`, `785a34e`). This verification checks the CURRENT state of `config/settings.py` and `portfolio/tests_deploy.py` — i.e., post-fix — not the original SUMMARY.md snapshot.

## Goal Achievement

### Observable Truths

Merged from ROADMAP.md Success Criteria (4) and PLAN frontmatter `must_haves.truths` (7, superset — SC1↔T1, SC2↔T2/T3, SC3↔T4, SC4↔T5, plus two plan-only truths on cookies/HSTS detail).

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | With `DEBUG=False`, `python manage.py check --deploy --fail-level WARNING` exits 0 with zero warnings (SETTINGS-02, SETTINGS-04; ROADMAP SC1) | VERIFIED | Ran independently (not via SUMMARY claim): `DEBUG=False SECRET_KEY=<test-key> ALLOWED_HOSTS=testserver CSRF_TRUSTED_ORIGINS= manage.py check --deploy --fail-level WARNING` → `System check identified no issues (0 silenced)`, exit code 0. Also proven by `test_check_deploy_exits_clean_with_debug_false`, which since WR-02's fix pins `ALLOWED_HOSTS`/`CSRF_TRUSTED_ORIGINS` in the subprocess env so it no longer falls through to the untracked local `.env` (hermeticity gap from `01-REVIEW.md` is closed). |
| 2 | A forwarded-https request (`X-Forwarded-Proto: https`) is trusted as secure and NOT redirected (SETTINGS-01; ROADMAP SC2) | VERIFIED | Ran `manage.py test portfolio.tests_deploy` directly: `test_forwarded_https_request_is_not_redirected` — `SecurityMiddleware` instantiated directly, asserts `response.status_code == 200`. Passed. |
| 3 | A plain-HTTP request with NO forwarded header is redirected (301) to `https://` (SETTINGS-01; absent-header edge) | VERIFIED | `test_plain_http_request_without_header_is_redirected_to_https` passed — asserts status 301 and `Location.startswith('https://')`. |
| 4 | `CSRF_TRUSTED_ORIGINS` and `ALLOWED_HOSTS` are read from the environment via `python-decouple`, no hardcoded domain literal remains (SETTINGS-03; ROADMAP SC3) | VERIFIED | `config/settings.py:30,34` use `config('ALLOWED_HOSTS', default='127.0.0.1,localhost', cast=Csv())` and `config('CSRF_TRUSTED_ORIGINS', default='', cast=Csv())`. Grep for `.com` in the file finds only the pre-existing `docs.djangoproject.com` doc-comment URLs (lines 7, 10, 22, etc.) — no CSRF/domain literal. `test_settings_source_is_env_driven_and_fail_closed` passed, and specifically asserts the removed literal `placeholder.example.com` is absent. |
| 5 | `DEBUG` resolves to `False` when unset in the environment — fails closed, not open (SETTINGS-04; ROADMAP SC4) | VERIFIED | Isolated test bypassing the repo's real (git-ignored, DEBUG=True-for-local-dev) `.env`: `decouple.Config(RepositoryEmpty())('DEBUG', default=False, cast=bool)` → `False`. This exercises the exact expression at `config/settings.py:28` with no environment source present, proving the default itself is fail-closed. (A naive test that merely unset `os.environ['DEBUG']` while running inside the repo falls through to the project's real local `.env`, which intentionally sets `DEBUG=True` for dev — that is expected `decouple` fallback behavior, not a code defect, and is a different scenario than "variable unset in the environment.") |
| 6 | When `DEBUG=False`, `SESSION_COOKIE_SECURE`, `CSRF_COOKIE_SECURE`, and `SECURE_SSL_REDIRECT` are all `True` (SETTINGS-02) | VERIFIED | Ran the plan's Task 1 verify command directly against the live file: prints `settings-ok`, asserting all three are `True`. |
| 7 | HSTS is configured: `SECURE_HSTS_SECONDS=31536000` (when not DEBUG), plus include-subdomains and preload for production (SETTINGS-02) | VERIFIED | `config/settings.py:44-46`: `SECURE_HSTS_SECONDS = 31536000 if not DEBUG else 0`, `SECURE_HSTS_INCLUDE_SUBDOMAINS = not DEBUG`, `SECURE_HSTS_PRELOAD = not DEBUG`. This is the post-review-fix state (WR-01 fixed in commit `14f27b4`) — `SECURE_HSTS_SECONDS` is now correctly gated on `DEBUG` like its siblings, closing the footgun the original SUMMARY.md's implementation left open (bare `31536000` regardless of `DEBUG`). Confirmed via `settings-ok` check with `DEBUG=False` → `SECURE_HSTS_SECONDS==31536000`. |

**Score:** 7/7 truths verified (0 present-but-behavior-unverified)

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `config/settings.py` | Env-driven CSRF/ALLOWED_HOSTS, SSL redirect, secure cookies, HSTS, fail-closed DEBUG | VERIFIED | All settings present, correctly gated, imports cleanly (`django.setup()` succeeds), no hardcoded domain literal. |
| `.env.example` | Tracked template documenting `SECRET_KEY`, `DEBUG`, `ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS` | VERIFIED | Confirmed tracked via `git ls-files` (not git-ignored — only `.env` is ignored, `.env.example` is explicitly the template). Contains all 4 keys each at start of line, with safe/fake placeholder for `SECRET_KEY`, per-variable guidance comments. |
| `portfolio/tests_deploy.py` | Deterministic test module proving forwarded-proto behavior + clean deploy check | VERIFIED | 6 tests, all pass on independent run (`manage.py test portfolio.tests_deploy -v 2` → `OK`). |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|----|--------|---------|
| `SECURE_PROXY_SSL_HEADER` | `SECURE_SSL_REDIRECT` non-loop behavior | `request.is_secure()` trusts forwarded header | WIRED | `test_forwarded_https_request_is_not_redirected` proves a forwarded-https request returns 200, not 301 — no redirect loop. |
| `not DEBUG` | `SESSION_COOKIE_SECURE`/`CSRF_COOKIE_SECURE`/`SECURE_SSL_REDIRECT`/HSTS trio | Boolean expression at settings load | WIRED | All 5 settings derive from `not DEBUG`; `settings-ok` check confirms values under `DEBUG=False`. |
| `.env` | `CSRF_TRUSTED_ORIGINS` | `config('CSRF_TRUSTED_ORIGINS', cast=Csv())` | WIRED | `.env.example` documents the key with intentionally-empty placeholder; `Csv()` cast confirmed to return `[]` on empty string (per `01-REVIEW.md`, independently re-confirmed by `isinstance(s.CSRF_TRUSTED_ORIGINS, list)` in the settings-ok check). |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|--------------|--------|----------|
| SETTINGS-01 | 01-01-PLAN.md | `SECURE_PROXY_SSL_HEADER` trusts `X-Forwarded-Proto`, no redirect loop | SATISFIED | Truths #2, #3 verified; key link 1 wired. |
| SETTINGS-02 | 01-01-PLAN.md | `SECURE_SSL_REDIRECT`, secure cookies, HSTS enabled for production | SATISFIED | Truths #1, #6, #7 verified; `check --deploy` clean. |
| SETTINGS-03 | 01-01-PLAN.md | `CSRF_TRUSTED_ORIGINS`/`ALLOWED_HOSTS` driven by `.env` | SATISFIED | Truth #4 verified; `.env.example` artifact present. |
| SETTINGS-04 | 01-01-PLAN.md | `DEBUG` fails closed; `check --deploy` passes | SATISFIED | Truths #1, #5 verified. |

No orphaned requirements — REQUIREMENTS.md maps exactly SETTINGS-01..04 to Phase 1, and all 4 appear in `01-01-PLAN.md`'s `requirements` frontmatter.

### Anti-Patterns Found

Scanned `config/settings.py`, `portfolio/tests_deploy.py`, and `.env.example` for `TBD|FIXME|XXX|TODO|HACK|PLACEHOLDER` and stub patterns.

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `portfolio/tests_deploy.py` | 101 | `placeholder.example.com` string literal | none | This is the intentional negative assertion (`assertNotIn`) proving the old placeholder literal was removed — not a debt marker. |
| `.env.example` | 19 | "do not add a placeholder domain here" | none | Explanatory comment, not a debt marker or stub. |

No blockers. No unresolved `TBD`/`FIXME`/`XXX` markers in any phase-modified file.

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Full settings-hardening test module passes | `manage.py test portfolio.tests_deploy -v 2` | `Ran 6 tests ... OK` | PASS |
| Real `check --deploy` exits clean (independent of the test's subprocess call) | `DEBUG=False SECRET_KEY=<test> ALLOWED_HOSTS=testserver CSRF_TRUSTED_ORIGINS= manage.py check --deploy --fail-level WARNING` | `System check identified no issues (0 silenced)`, exit 0 | PASS |
| `settings-ok` behavior assertion (Task 1 verify command) | Direct `django.setup()` + attribute assertions | `settings-ok` | PASS |
| `DEBUG` config default fails closed in isolation (no real `.env` involved) | `decouple.Config(RepositoryEmpty())('DEBUG', default=False, cast=bool)` | `False` | PASS |
| Full project test suite (regression check, run once) | `DEBUG=True manage.py test` | `Ran 9 tests ... OK` | PASS |

### Human Verification Required

None. All must-haves are settings/behavior assertions verifiable programmatically; no UI, visual, or external-service-dependent behavior in this phase.

### Gaps Summary

None. All 7 merged truths (covering all 4 ROADMAP success criteria and all 4 requirement IDs) are verified against the CURRENT code state — i.e., after the code-review fixes in `01-REVIEW-FIX.md` (WR-01 HSTS/DEBUG gating, WR-02 test hermeticity, WR-03 inline risk documentation) were applied. All fixes were independently confirmed present in `config/settings.py`/`portfolio/tests_deploy.py`, not merely trusted from `01-REVIEW-FIX.md`'s claims.

One item is explicitly out of Phase 1's scope by the plan's own threat model, not a gap: `SECURE_PROXY_SSL_HEADER` trusting `X-Forwarded-Proto` is only safe once Gunicorn is bound to loopback-only, which is Phase 2's explicit success criterion #1 (`PROC-01`: "gunicorn bound to 127.0.0.1 only"). Phase 1 correctly sets the trust and documents the dependency inline (`config/settings.py:35-39`, added in commit `785a34e` per WR-03); the enforcing control lands in Phase 2 as designed.

---

_Verified: 2026-07-19T12:00:00Z_
_Verifier: Claude (gsd-verifier)_
