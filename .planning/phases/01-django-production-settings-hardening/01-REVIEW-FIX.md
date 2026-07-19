---
phase: 01-django-production-settings-hardening
fixed_at: 2026-07-19T11:15:00Z
review_path: .planning/phases/01-django-production-settings-hardening/01-REVIEW.md
iteration: 1
findings_in_scope: 3
fixed: 3
skipped: 0
status: all_fixed
---

# Phase 01: Code Review Fix Report

**Fixed at:** 2026-07-19T11:15:00Z
**Source review:** .planning/phases/01-django-production-settings-hardening/01-REVIEW.md
**Iteration:** 1

**Summary:**
- Findings in scope: 3 (critical_warning scope — 0 critical, 3 warning)
- Fixed: 3
- Skipped: 0

## Fixed Issues

### WR-01: `SECURE_HSTS_SECONDS` is not gated on `DEBUG`, unlike its sibling HSTS settings

**Files modified:** `config/settings.py`
**Commit:** 14f27b4
**Applied fix:** Changed `SECURE_HSTS_SECONDS = 31536000` to `SECURE_HSTS_SECONDS = 31536000 if not DEBUG else 0` on line 39, matching the `DEBUG`-gating pattern already used by `SECURE_HSTS_INCLUDE_SUBDOMAINS` and `SECURE_HSTS_PRELOAD`. Verified with `ast.parse` (syntax OK); source matched the review's cited context exactly.

### WR-02: `check --deploy` test is not hermetic — depends on the untracked `.env` file

**Files modified:** `portfolio/tests_deploy.py`
**Commit:** 667f1cd
**Applied fix:** Added explicit `ALLOWED_HOSTS: 'testserver'` and `CSRF_TRUSTED_ORIGINS: ''` entries to the subprocess `env` dict in `test_check_deploy_exits_clean_with_debug_false`, so the test no longer falls through to the untracked local `.env` file via `python-decouple`'s environment-first lookup. Verified by running the specific test (`python manage.py test portfolio.tests_deploy.SettingsHardeningTests.test_check_deploy_exits_clean_with_debug_false`) against the project's `.venv` — it passed (`OK`, `System check identified no issues`).

### WR-03: Trusting `X-Forwarded-Proto` is unsafe until the Phase 2 loopback binding lands

**Files modified:** `config/settings.py`
**Commit:** 785a34e
**Applied fix:** The review's own Fix guidance states no code change is required in this file for the underlying behavior (the risk is resolved by a future Phase 2 loopback-binding change, not by this file alone). To satisfy the review's explicit request to make "the dependency ... explicit and tracked at review time, not just in planning docs," added an inline warning comment directly above `SECURE_PROXY_SSL_HEADER` referencing threat model T-01-01, explaining the header-spoofing risk, and stating this settings module must not be exposed to a non-loopback interface before Phase 2's loopback binding is verified. Verified with `ast.parse` (syntax OK).

## Skipped Issues

None — all in-scope findings were fixed.

---

_Fixed: 2026-07-19T11:15:00Z_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 1_
