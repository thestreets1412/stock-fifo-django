---
phase: 01-django-production-settings-hardening
plan: 01
subsystem: infra
tags: [django, security, decouple, csrf, hsts, ssl-redirect, deploy-check]

requires: []
provides:
  - "Env-driven CSRF_TRUSTED_ORIGINS (fail-closed empty default) in config/settings.py"
  - "SECURE_SSL_REDIRECT / SECURE_HSTS_INCLUDE_SUBDOMAINS / SECURE_HSTS_PRELOAD gated on not DEBUG"
  - "Tracked .env.example documenting SECRET_KEY, DEBUG, ALLOWED_HOSTS, CSRF_TRUSTED_ORIGINS"
  - "portfolio/tests_deploy.py proving forwarded-proto behavior and a clean check --deploy"
affects: [02-raspberry-pi-deployment-hardening, 05-domain-and-tunnel-configuration]

tech-stack:
  added: []
  patterns:
    - "Security settings derived from `not DEBUG` so a single fail-closed DEBUG default drives cookies/redirect/HSTS"
    - "SecurityMiddleware instantiated directly in tests (not via test client) to deterministically read overridden settings at __init__ time"

key-files:
  created:
    - .env.example
    - portfolio/tests_deploy.py
  modified:
    - config/settings.py

key-decisions:
  - "CSRF_TRUSTED_ORIGINS defaults to empty (fail-closed) via decouple Csv() cast rather than a placeholder domain; real https:// origin deferred to Phase 5"
  - "Test SECRET_KEY uses a 52-char mixed-character string, not a repeated character, to avoid tripping Django's own security.W009 low-entropy check"
  - "Source-assertion test checks for the removed literal `placeholder.example.com` specifically, not a blanket '.com' substring, since pre-existing Django doc-comment URLs (docs.djangoproject.com) legitimately contain '.com'"

patterns-established:
  - "Deploy-hardening tests live in portfolio/tests_deploy.py (matches Django's test*.py discovery), separate from portfolio/tests.py's business-logic tests"

requirements-completed: [SETTINGS-01, SETTINGS-02, SETTINGS-03, SETTINGS-04]

coverage:
  - id: D1
    description: "CSRF_TRUSTED_ORIGINS and ALLOWED_HOSTS read from environment via python-decouple, no hardcoded domain literal in settings.py"
    requirement: "SETTINGS-03"
    verification:
      - kind: unit
        ref: "portfolio/tests_deploy.py#SettingsHardeningTests.test_settings_source_is_env_driven_and_fail_closed"
        status: pass
    human_judgment: false
  - id: D2
    description: "SECURE_SSL_REDIRECT, secure session/CSRF cookies, and HSTS (with include-subdomains/preload) enabled when DEBUG=False; check --deploy exits 0"
    requirement: "SETTINGS-02"
    verification:
      - kind: unit
        ref: "portfolio/tests_deploy.py#SettingsHardeningTests.test_check_deploy_exits_clean_with_debug_false"
        status: pass
    human_judgment: false
  - id: D3
    description: "Forwarded-https request is not redirected; plain-HTTP request without the header is redirected to https"
    requirement: "SETTINGS-01"
    verification:
      - kind: unit
        ref: "portfolio/tests_deploy.py#SettingsHardeningTests.test_forwarded_https_request_is_not_redirected"
        status: pass
      - kind: unit
        ref: "portfolio/tests_deploy.py#SettingsHardeningTests.test_plain_http_request_without_header_is_redirected_to_https"
        status: pass
      - kind: unit
        ref: "portfolio/tests_deploy.py#SettingsHardeningTests.test_is_secure_true_with_forwarded_proto_header"
        status: pass
      - kind: unit
        ref: "portfolio/tests_deploy.py#SettingsHardeningTests.test_is_secure_false_without_forwarded_proto_header"
        status: pass
    human_judgment: false
  - id: D4
    description: "DEBUG defaults to False when unset (fail-closed)"
    requirement: "SETTINGS-04"
    verification:
      - kind: unit
        ref: "portfolio/tests_deploy.py#SettingsHardeningTests.test_settings_source_is_env_driven_and_fail_closed"
        status: pass
    human_judgment: false
  - id: D5
    description: ".env.example tracked and documents SECRET_KEY, DEBUG, ALLOWED_HOSTS, CSRF_TRUSTED_ORIGINS with safe placeholders"
    verification:
      - kind: other
        ref: "python -c source-assertion (env-example-ok) — see PLAN.md Task 2 verify"
        status: pass
    human_judgment: false

duration: 12min
completed: 2026-07-19
status: complete
---

# Phase 1 Plan 1: Django Production Settings Hardening Summary

**Completed the CSRF/SSL-redirect/HSTS production hardening of `config/settings.py`, added a tracked `.env.example`, and proved the forwarded-proto/redirect/deploy-check behavior with a new deterministic test module.**

## Performance

- **Duration:** 12 min
- **Started:** 2026-07-19T09:06:32Z
- **Completed:** 2026-07-19T09:18:00Z
- **Tasks:** 3 completed
- **Files modified:** 3 (1 modified, 2 created)

## Accomplishments
- `CSRF_TRUSTED_ORIGINS` now reads from the environment via `python-decouple` (fail-closed empty default), replacing the hardcoded `placeholder.example.com` flagged in CONCERNS.md as a live CSRF risk
- `SECURE_SSL_REDIRECT`, `SECURE_HSTS_INCLUDE_SUBDOMAINS`, and `SECURE_HSTS_PRELOAD` added, all gated on `not DEBUG`, closing the last `check --deploy` warning
- Tracked `.env.example` documents all four `config(...)` keys the app reads, with safe placeholders and per-variable guidance
- `portfolio/tests_deploy.py` (6 tests) mechanically proves: forwarded-https requests are not redirected, plain-HTTP requests without the header get a 301 to `https://`, `is_secure()` honors `SECURE_PROXY_SSL_HEADER`, `check --deploy --fail-level WARNING` exits 0 with `DEBUG=False`, and the settings source is env-driven/fail-closed with no leftover domain literal

## Task Commits

Each task was committed atomically:

1. **Task 1: Complete config/settings.py production hardening** - `64a392d` (feat)
2. **Task 2: Add tracked .env.example documenting required environment variables** - `9a99353` (docs)
3. **Task 3: Add deterministic settings-hardening test module and prove a clean deploy check** - `7466d18` (test)

**Plan metadata:** (pending — final docs commit below)

_Note: Task 3 is tagged `tdd="true"` in the plan, but its implementation (Task 1) intentionally precedes test authoring by plan design — see Deviations for how the RED/GREEN gate was interpreted here._

## Files Created/Modified
- `config/settings.py` - Env-driven `CSRF_TRUSTED_ORIGINS`; added `SECURE_SSL_REDIRECT`, `SECURE_HSTS_INCLUDE_SUBDOMAINS`, `SECURE_HSTS_PRELOAD`
- `.env.example` - New tracked template for `SECRET_KEY`, `DEBUG`, `ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS`
- `portfolio/tests_deploy.py` - New `SettingsHardeningTests` module (6 tests)

## Decisions Made
- Empty-default `Csv()` cast for `CSRF_TRUSTED_ORIGINS` keeps the setting fail-closed until Phase 5 supplies the real domain, rather than any placeholder value
- Test module lives at `portfolio/tests_deploy.py` (separate from `portfolio/tests.py`) since it verifies deployment/settings concerns, not FIFO business logic
- Test `SECRET_KEY` constant uses a 52-character string with mixed case/digits/symbols (not a repeated character) so it doesn't itself trip Django's `security.W009` low-entropy check

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Test SECRET_KEY constant tripped Django's own weak-key check**
- **Found during:** Task 3 (writing `test_check_deploy_exits_clean_with_debug_false`)
- **Issue:** Initial test used `'x' * 60` as the injected `SECRET_KEY`. Although 60 characters, it has only 1 unique character, which `django.core.checks.security.base.check_secret_key` (`security.W009`) flags as weak regardless of length — the subprocess `check --deploy` failed with exit code 1 instead of the expected 0.
- **Fix:** Replaced with a 52-character mixed-case/digit/symbol constant (`a1B2c3D4e5F6...`) that satisfies both the length and unique-character-count checks.
- **Files modified:** `portfolio/tests_deploy.py`
- **Verification:** `python manage.py test portfolio.tests_deploy -v 2` — `test_check_deploy_exits_clean_with_debug_false` now passes.
- **Committed in:** `7466d18` (Task 3 commit)

**2. [Rule 1 - Bug] Source-assertion test's blanket `.com` check collided with pre-existing Django doc-comment URLs**
- **Found during:** Task 3 (writing `test_settings_source_is_env_driven_and_fail_closed`)
- **Issue:** The plan's literal acceptance criterion ("assert `.com` does not appear") was written against the intent of removing the hardcoded CSRF placeholder domain, but `config/settings.py` (as generated by `django-admin startproject`, unrelated to this task's changes) contains several `# See https://docs.djangoproject.com/...` comments that legitimately contain the substring `.com`. A literal `assertNotIn('.com', source)` failed against this pre-existing, out-of-scope content.
- **Fix:** Narrowed the assertion to check for the specific removed literal (`placeholder.example.com`) instead of a blanket substring ban, preserving the actual intent (no hardcoded CSRF domain literal) without breaking on unrelated framework doc-reference comments.
- **Files modified:** `portfolio/tests_deploy.py`
- **Verification:** `python manage.py test portfolio.tests_deploy -v 2` — `test_settings_source_is_env_driven_and_fail_closed` now passes; confirmed via `git diff` that `config/settings.py`'s only `.com` occurrences are pre-existing `docs.djangoproject.com` doc comments, not CSRF-related.
- **Committed in:** `7466d18` (Task 3 commit)

---

**Total deviations:** 2 auto-fixed (both Rule 1 — bugs in the test module itself, not in the settings implementation)
**Impact on plan:** Both fixes were necessary to make the test suite pass and correctly reflect the plan's actual intent. No scope creep — no files outside the plan's declared `files_modified` were touched.

## TDD Gate Compliance

Task 3 is marked `tdd="true"` in the plan, but the plan's own task ordering places the implementation (Task 1: `config/settings.py` hardening) **before** the test-authoring task (Task 3). This means a literal RED phase (test written and failing before any implementation exists) was not possible by plan design — the behavior under test already existed when `portfolio/tests_deploy.py` was created. All 6 tests passed on first successful run (after the two Rule-1 fixes above to the test file itself, not to the settings implementation). Git log confirms:
- `64a392d` — `feat(01-01): harden production security settings in config/settings.py` (implementation)
- `7466d18` — `test(01-01): add deterministic settings-hardening test module` (test, proving the implementation)

No RED→GREEN commit pair exists because the plan sequenced implementation first; this is a plan-structure choice, not a process violation. The tests substantively lock in and mechanically prove every `must_haves.truths` claim in the plan.

## Issues Encountered
None beyond the two Rule-1 auto-fixes documented above.

## User Setup Required

None - no external service configuration required. Note: the real `.env` `SECRET_KEY` strength was not verified by this plan (`.env` is not readable by the executor/planner). Per the plan's flagged assumption, if the operator's real `python manage.py check --deploy` (run manually against the live `.env`) emits `security.W009`, regenerate the key with `python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"` and update `.env`.

## Next Phase Readiness
- `config/settings.py` is fully hardened and verified; ready for Phase 2 (Raspberry Pi deployment hardening), which enforces the loopback-only binding that makes trusting `X-Forwarded-Proto` safe (per this plan's threat model T-01-01)
- `CSRF_TRUSTED_ORIGINS` remains intentionally empty until Phase 5 supplies the real domain — no blocker, this is by design
- No blockers for downstream phases

---
*Phase: 01-django-production-settings-hardening*
*Completed: 2026-07-19*

## Self-Check: PASSED

All created files verified present on disk (`config/settings.py`, `.env.example`, `portfolio/tests_deploy.py`, this SUMMARY.md). All task commit hashes (`64a392d`, `9a99353`, `7466d18`) verified present in git log.
