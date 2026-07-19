---
phase: 01-django-production-settings-hardening
reviewed: 2026-07-19T00:00:00Z
depth: standard
files_reviewed: 3
files_reviewed_list:
  - config/settings.py
  - .env.example
  - portfolio/tests_deploy.py
findings:
  critical: 0
  warning: 3
  info: 2
  total: 5
status: issues_found
---

# Phase 01: Code Review Report

**Reviewed:** 2026-07-19T00:00:00Z
**Depth:** standard
**Files Reviewed:** 3
**Status:** issues_found

## Summary

Reviewed the Django production-settings hardening commit (`64a392d`), the new `.env.example` template (`9a99353`), and the new `portfolio/tests_deploy.py` test module (`7466d18`). The `CSRF_TRUSTED_ORIGINS` env-driven fail-closed default is implemented correctly (verified `Csv()('')` returns `[]`), `DEBUG` fails closed, and the forwarded-proto / SSL-redirect middleware behavior is correctly proven by direct `SecurityMiddleware` instantiation. No critical/blocker-level defects were found — no hardcoded secrets, no injection vectors, no crash paths.

Two categories of real issues remain: (1) an inconsistency in how HSTS settings are gated on `DEBUG` — `SECURE_HSTS_SECONDS` is always active while its sibling `SECURE_HSTS_INCLUDE_SUBDOMAINS`/`SECURE_HSTS_PRELOAD` are correctly gated, which matters specifically for this project's Cloudflare-Tunnel-testing workflow; and (2) the "deterministic" `check --deploy` test is not actually hermetic — it depends on the untracked, unreviewed local `.env` file for `ALLOWED_HOSTS`/`CSRF_TRUSTED_ORIGINS`, contradicting its own docstring claim.

## Warnings

### WR-01: `SECURE_HSTS_SECONDS` is not gated on `DEBUG`, unlike its sibling HSTS settings

**File:** `config/settings.py:39-41`
**Issue:** `SECURE_HSTS_INCLUDE_SUBDOMAINS` and `SECURE_HSTS_PRELOAD` are correctly set to `not DEBUG` specifically so that "HSTS-preload semantics never bind a local dev host" (per the plan's own stated rationale). `SECURE_HSTS_SECONDS = 31536000`, however, is a bare literal with no `DEBUG` gating at all. Django's `SecurityMiddleware.process_response` (verified against the installed Django source) sends the `Strict-Transport-Security` header whenever `self.sts_seconds and request.is_secure()` — it does not check `DEBUG`. So if this app is ever reached over HTTPS while `DEBUG=True` (a realistic scenario for this project, whose entire purpose is validating behavior behind a Cloudflare Tunnel before flipping to full production — e.g. pointing the tunnel at a dev instance to test connectivity), the browser will still receive `max-age=31536000` (1 year) and will force HTTPS for that host for a year, even though the developer only intended a transient debug session. This is the exact class of footgun the sibling settings were deliberately gated to avoid, just left half-applied.
**Fix:**
```python
SECURE_HSTS_SECONDS = 31536000 if not DEBUG else 0
SECURE_HSTS_INCLUDE_SUBDOMAINS = not DEBUG
SECURE_HSTS_PRELOAD = not DEBUG
```

### WR-02: `check --deploy` test is not hermetic — depends on the untracked `.env` file

**File:** `portfolio/tests_deploy.py:71-88`
**Issue:** `test_check_deploy_exits_clean_with_debug_false`'s docstring on the enclosing class claims this is a "Deterministic proof" of the settings hardening. The subprocess env is built as `{**os.environ, 'DEBUG': 'False', 'SECRET_KEY': TEST_SECRET_KEY}` (lines 72-76) — only `DEBUG` and `SECRET_KEY` are overridden. `python-decouple`'s `Config.get()` checks `os.environ` first and only falls back to the `.env` file when the key is absent from `os.environ` (confirmed by reading the installed `decouple` source). Since `ALLOWED_HOSTS` and `CSRF_TRUSTED_ORIGINS` are not set in the parent process's OS environment, decouple falls through to whatever is in the project's real (untracked, gitignored, unreviewed) `.env` file for those two values inside the subprocess. This means: (a) the test's pass/fail outcome for those two settings is not controlled by the test at all — a locally misconfigured `.env` (e.g. an unscoped `ALLOWED_HOSTS=*` or a `CSRF_TRUSTED_ORIGINS` entry missing the `https://` scheme) could make this test fail for reasons unrelated to `config/settings.py`'s correctness, and (b) conversely a permissive local `.env` could mask a real regression that only manifests in CI/deploy where no `.env` file exists. This directly contradicts the "deterministic" claim in the class docstring.
**Fix:**
```python
env = {
    **os.environ,
    'DEBUG': 'False',
    'SECRET_KEY': TEST_SECRET_KEY,
    'ALLOWED_HOSTS': 'testserver',
    'CSRF_TRUSTED_ORIGINS': '',
}
```

### WR-03: Trusting `X-Forwarded-Proto` is unsafe until the Phase 2 loopback binding lands

**File:** `config/settings.py:35`
**Issue:** `SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')` makes Django trust a client-controllable header as proof of a secure connection. The phase's own threat model (T-01-01) documents this is only safe once Gunicorn is bound to loopback-only (deferred to Phase 2) so a LAN/network client cannot forge the header directly against the WSGI process. That sequencing is a reasonable plan-level trade-off, but it means this file, considered in isolation (as reviewed here), currently ships a real header-spoofing bypass of `SECURE_SSL_REDIRECT`/effectively downgrades the "force HTTPS" guarantee if this settings module is deployed before Phase 2's binding change lands, or if Phase 2 is ever reverted/misconfigured. Flagging so the dependency is explicit and tracked at review time, not just in planning docs.
**Fix:** No code change required in this file; ensure Phase 2 (or equivalent loopback-only binding) is verified as a hard prerequisite before this settings module is ever exposed to a non-loopback network interface — consider adding a startup check or deployment runbook assertion, not just a planning-doc note.

## Info

### IN-01: Source-string-matching test is brittle and tests source text, not runtime behavior

**File:** `portfolio/tests_deploy.py:90-99`
**Issue:** `test_settings_source_is_env_driven_and_fail_closed` reads `config/settings.py` as raw text and asserts substrings like `"config('CSRF_TRUSTED_ORIGINS'"` are present. This will silently stop testing anything meaningful if the code is later refactored to equivalent-but-differently-formatted code (e.g. multi-line call, different quote style, a wrapper function) — the test would then fail (or worse, could be trivially "fixed" by restoring the exact string without restoring the actual behavior). It also doesn't verify the *resulting* value is correct, only that certain characters appear in the file.
**Fix:** Prefer asserting on the resolved runtime settings values (already partially done elsewhere in the file via `override_settings`/direct settings access), e.g. `self.assertEqual(settings.CSRF_TRUSTED_ORIGINS, [])` when unset, in addition to (not instead of) the source-text guard against a hardcoded literal reappearing.

### IN-02: Magic number `31536000` lacks an inline comment

**File:** `config/settings.py:39`
**Issue:** `SECURE_HSTS_SECONDS = 31536000` is a well-known Django convention (1 year), but the file has no comment stating that, unlike neighboring lines which do carry explanatory comments (lines 32-33).
**Fix:**
```python
SECURE_HSTS_SECONDS = 31536000  # 1 year, required for HSTS preload eligibility
```

---

_Reviewed: 2026-07-19T00:00:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
