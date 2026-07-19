# Codebase Concerns

**Analysis Date:** 2026-07-19

## Tech Debt

**Domain Configuration Placeholder:**
- Issue: `CSRF_TRUSTED_ORIGINS` is hardcoded to `"https://placeholder.example.com"` with an explicit TODO comment
- Files: `config/settings.py` (line 33)
- Impact: When deployed to production, CSRF protection will be bypassed for invalid domain. Any POST request from the placeholder domain will be accepted, creating a cross-site request forgery vulnerability until the real domain is configured.
- Fix approach: Before production deployment, update `CSRF_TRUSTED_ORIGINS` to the actual domain(s). Replace placeholder with environment variable: `config('CSRF_TRUSTED_ORIGINS', cast=Csv())` and document in .env template.

**ThreadPoolExecutor Created Per Request:**
- Issue: `fetch_current_price()` creates a new `ThreadPoolExecutor` on every call instead of maintaining a singleton pool
- Files: `portfolio/services.py` (lines 128-138)
- Impact: Creates overhead of thread pool initialization for every dashboard render or price lookup. High concurrent load will spawn many short-lived threads, consuming system resources inefficiently.
- Fix approach: Create a module-level `ThreadPoolExecutor` instance initialized once at startup with fixed `max_workers` count.

**No Caching of Expensive External API Calls:**
- Issue: `fetch_usd_thb_rate()` and `fetch_current_price()` make fresh network requests on every invocation with no caching
- Files: `portfolio/services.py` (lines 31-43, 119-138), used in `portfolio/forms.py` (lines 45, 93) and `portfolio/services.py` (line 181)
- Impact: Dashboard render triggers multiple network requests per symbol; if a user has 10 holdings, 10+ outbound HTTP calls happen on every page load. Form validation also triggers FX rate fetches.
- Fix approach: Implement time-based caching (e.g., cache FX rates for 24 hours, prices for 5 minutes). Use Django's cache framework with Redis/memcached in production or `functools.lru_cache` with manual invalidation for development.

**Missing Database Indexes:**
- Issue: Frequently queried fields lack database indexes for performance
- Files: `portfolio/models.py` (StockLot and Sale models)
- Impact: List views and report generation iterate over potentially large datasets without indexed lookups on `(owner, symbol)` and `(owner, sell_date)`. Queries will slow significantly as transaction history grows.
- Fix approach: Add `db_index=True` to frequently filtered fields: `StockLot.owner`, `StockLot.symbol`, `Sale.owner`, `Sale.symbol`. Run `makemigrations` and `migrate`.

**No List Pagination:**
- Issue: `LotListView` and `SaleListView` return all records for a user without pagination
- Files: `portfolio/views.py` (lines 36-50, 111-124)
- Impact: A user with thousands of transactions will download/render all records on page load. Memory and network overhead scales linearly with history size.
- Fix approach: Add `paginate_by = 50` to both ListView classes. Update templates to render pagination controls.

**SQLite as Primary Database:**
- Issue: Project uses SQLite for all environments including local server deployment
- Files: `config/settings.py` (lines 85-90)
- Impact: SQLite has poor concurrent write performance. On Raspberry Pi or multi-threaded server, simultaneous FIFO record attempts will serialize and timeout. Not suitable for production.
- Fix approach: Switch to PostgreSQL or MySQL for deployment. Keep SQLite for development only. Use `config('DATABASE_ENGINE', default='sqlite3')` and corresponding settings.

---

## Known Bugs

**Form AJAX Error Handling Injects Unsanitized HTML:**
- Symptoms: AJAX form submission errors re-render the form HTML inside the modal via `innerHTML`, which could allow JavaScript injection if form rendering isn't perfectly escaped
- Files: `portfolio/static/portfolio/modal-forms.js` (line 30), `portfolio/views.py` (lines 66-72, 102-108)
- Trigger: Fill AJAX form with data that triggers rendering error; the error HTML is injected directly into DOM
- Workaround: Django's template rendering escapes variables by default, but explicit `|safe` filters on form errors could break this. Validate no form fields use `|safe`.

**Price Fetch Timeout Doesn't Propagate Gracefully on Dashboard Timeout:**
- Symptoms: If yfinance is rate-limited or slow for one ticker, dashboard waits 5 seconds per symbol sequentially instead of in parallel, causing cumulative timeouts on large portfolios
- Files: `portfolio/services.py` (lines 179-191), `portfolio/views.py` (line 49)
- Trigger: Dashboard load with 5+ holdings when yfinance API is slow
- Workaround: Currently shows `None` for unrealized gains when price fetch fails. User must refresh dashboard or view holdings without live values.

**Platform-Specific Deployment Issues:**
- Symptoms: Recent commit "Fixing bug to run on local server (Raspberry pi 4 x64 OS lite)" indicates environment-specific failures
- Files: Unclear which files — check git diff on commit `091d58c`
- Trigger: Deployment to non-standard hardware or OS versions
- Workaround: Document platform requirements in README and test on target platform before deployment.

---

## Security Considerations

**File Upload Validation Missing:**
- Risk: Users can upload evidence images (`portfolio/models.py` line 31, 62) with no file type or size validation
- Files: `portfolio/models.py` (evidence fields), `portfolio/forms.py` (lines 29, 82)
- Current mitigation: `ImageField` restricts to image formats, but max file size is unlimited
- Recommendations: Add `validators=[FileExtensionValidator(['jpg', 'jpeg', 'png', 'gif', 'webp'])]` and implement file size limit in form `clean_evidence()`. Cap upload size in Django settings: `FILE_UPLOAD_MAX_MEMORY_SIZE = 5242880  # 5MB`.

**Media Files Served Through Django (Not Production-Safe):**
- Risk: Evidence images served via `re_path(r'^media/(?P<path>.*)$', serve, {'document_root': settings.MEDIA_ROOT})` in `config/urls.py` (line 32)
- Files: `config/urls.py` (line 32)
- Current mitigation: LoginRequiredMixin on views, but URLs to media files aren't protected
- Recommendations: Disable direct media serving in production. Use S3/Cloudflare R2 for file storage. Or wrap media serving in a view with explicit permission checks.

**SECURE_SSL_REDIRECT Not Enforced in Development:**
- Risk: `SESSION_COOKIE_SECURE` and `CSRF_COOKIE_SECURE` are conditional on `DEBUG`, but HTTPS redirect isn't configured
- Files: `config/settings.py` (lines 35-36)
- Current mitigation: Cookies marked secure when DEBUG=False
- Recommendations: Add `SECURE_SSL_REDIRECT = not DEBUG` and `SECURE_HSTS_INCLUDE_SUBDOMAINS = not DEBUG` to settings.

**External API Dependency Without Fallback:**
- Risk: Dashboard and forms fail if Frankfurter API is down or rate-limited
- Files: `portfolio/services.py` (lines 31-43), used in forms and dashboard
- Current mitigation: Returns `None` for FX rates on fetch failure; dashboard shows incomplete data
- Recommendations: Cache historical FX rates in database. Implement backup rate source (ECB directly, or hardcoded rates with warning). Document SLA expectations for external APIs.

**Cross-User Data Access Not Explicitly Tested:**
- Risk: All views use `LoginRequiredMixin` but permission filtering relies on `filter(owner=self.request.user)` which could be bypassed if a view is forgotten
- Files: `portfolio/views.py` (all list/detail views), `portfolio/services.py` (all query functions)
- Current mitigation: Evidence views filter by `owner` in `get_queryset()`. No tests verify this isolation.
- Recommendations: Add explicit integration tests that attempt cross-user access on each view/API endpoint. Ensure no user can see another user's data via manipulation of query parameters or direct URL access.

---

## Performance Bottlenecks

**N+1 Query on Report Generation:**
- Problem: `build_fifo_report()` calls `sale.allocations.all()` and then sorts by `alloc.lot.buy_date` (line 85 in `services.py`), triggering N separate queries for lot details
- Files: `portfolio/services.py` (lines 65-105)
- Cause: Allocations are prefetched in `get_user_sales()` but lot details aren't; sorting in Python forces lot access after prefetch completes
- Improvement path: Replace `prefetch_related('allocations__lot')` with explicit `Prefetch` using `queryset` to prefetch sorted allocations. Or sort allocations by lot ID in Python after ensuring lots are prefetched.

**Dashboard Sequentially Fetches Prices:**
- Problem: Loop in `build_dashboard_summary()` calls `fetch_current_price()` once per symbol in sequence (lines 166-195)
- Files: `portfolio/services.py` (lines 166-195)
- Cause: No parallel fetching; each 5-second timeout is serial
- Improvement path: Use `concurrent.futures.ThreadPoolExecutor` with `map()` to fetch prices for all symbols in parallel, capping workers at CPU count or 10 (whichever is smaller).

**Form Validation Blocks on FX Rate Fetch:**
- Problem: `StockLotForm.clean_fx_rate_usd_thb()` and `SellForm.clean_fx_rate_usd_thb()` make synchronous HTTP requests during form validation (lines 44-47 in forms.py, 92-95 in forms.py)
- Files: `portfolio/forms.py` (lines 37-47, 85-95)
- Cause: AJAX form submission waits for network I/O, blocking the user
- Improvement path: Make FX rate fetch optional in form (show "not available" in UI if fetch fails rather than blocking the form). Or fetch rates asynchronously after form submission.

---

## Fragile Areas

**Complex Graceful Degradation in Dashboard:**
- Files: `portfolio/services.py` (lines 141-219)
- Why fragile: Multiple conditional branches handle missing FX rates, missing prices, missing both. Flag `has_full_value` is mutated conditionally. If one condition changes, related flags may become inconsistent, causing None/partial data to slip through silently.
- Safe modification: Add explicit logging at each degradation point: `logger.warning("Price fetch failed for %s", symbol.ticker)`. Add unit tests asserting specific degradation scenarios (no FX, has FX + no price, etc.). Use dataclass-like return type to document expected None fields.
- Test coverage: Currently no tests for price fetch failures or partial degradation.

**Transaction Atomic Block in `record_sale()`:**
- Files: `portfolio/services.py` (lines 222-286)
- Why fragile: `@transaction.atomic` decorator rolls back on ANY exception in the function. If an unrelated exception occurs after allocations are created but before return, the entire sale is rolled back without the user knowing why. No error logging.
- Safe modification: Wrap only the allocation creation and sale creation in transaction. Log exceptions before raising. Add unit tests for error cases (InsufficientLotsError, database errors).
- Test coverage: No tests for `record_sale()` or error handling in FIFO matching.

**Report Generation with No Validation:**
- Files: `portfolio/reports.py` (lines 53-314)
- Why fragile: CSV and PDF generation assume all sections, lots, and sales have valid numeric data. If a field is unexpectedly None or NaN, formatting functions (`_money()`, `_fmt_qty()`) may crash during report export.
- Safe modification: Add assertions or try-except in report functions. Validate data before report generation. Document assumptions about data integrity.
- Test coverage: No tests for report generation with malformed or edge-case data (zero quantities, negative gains, missing allocations).

**Admin `StockLotAdmin.list_display` Calls Property `qty_remaining`:**
- Files: `portfolio/admin.py` (line 17)
- Why fragile: Django admin renders `qty_remaining` property on every row, triggering a `Sum()` query per lot. Admin list page for 100 lots = 100 queries.
- Safe modification: Remove `qty_remaining` from `list_display`. Add a computed column using `annotate()` in `get_queryset()` instead.
- Test coverage: No tests for admin interface performance.

---

## Scaling Limits

**yfinance Rate Limiting:**
- Current capacity: ~2 tickers per 10 seconds (yfinance enforces rate limits)
- Limit: Dashboard with >10 holdings hits rate limits during peak hours
- Scaling path: Implement quote provider fallback (Alpha Vantage, IEX Cloud). Cache prices in Redis with minute-level TTL. Use async fetching with futures and timeout handling per symbol.

**SQLite Write Contention:**
- Current capacity: Single-digit concurrent transactions
- Limit: Multiple users recording sales simultaneously will experience lock timeouts on Raspberry Pi
- Scaling path: Migrate to PostgreSQL. Use connection pooling (PgBouncer). Enable WAL mode for SQLite if staying on local server, but this doesn't solve write contention.

**Media Storage on Local Filesystem:**
- Current capacity: Limited by disk space on Raspberry Pi or server
- Limit: ~GB of evidence images will exhaust typical single-board computer storage
- Scaling path: Migrate to S3/Cloudflare R2. Implement image compression. Add storage quota per user.

**Report Generation Memory:**
- Current capacity: ~5000 transactions before ReportLab PDF generation OOMs
- Limit: Portfolio with year+ of daily trades will hit memory limits
- Scaling path: Implement pagination in PDF (multiple files). Stream CSV generation. Use ReportLab's platypus without building full element list before doc.build().

---

## Dependencies at Risk

**yfinance Reliability:**
- Risk: yfinance is community-maintained and frequently breaks due to upstream Yahoo Finance API changes. No SLA.
- Impact: Dashboard shows stale/missing prices without warning. Users can't see live portfolio value.
- Migration plan: Implement pluggable price provider interface. Add Alpha Vantage as fallback (requires API key but more stable). Accept manual price input if all automated sources fail.

**Frankfurter API Dependency:**
- Risk: ECB-backed FX rate API has no SLA and can be slow or unavailable during market hours
- Impact: Form submission is delayed if FX fetch hangs. Users can't record transactions if rate fetch fails.
- Migration plan: Cache FX rates by (date, currency_pair) in database. Allow manual override. Fetch rates asynchronously (don't block form submission).

**Python 3.x Version Dependency:**
- Risk: Project doesn't specify minimum Python version (no `python_requires` in setup.py or pyproject.toml)
- Impact: Could fail on Python 2 (legacy) or very old Python 3 (missing features)
- Migration plan: Add `python_requires = ">=3.9"` to project metadata.

**Pillow Version (Image Handling):**
- Risk: `pillow==12.3.0` is a recent major version. Known breaking changes in image processing between versions.
- Impact: Evidence image uploads could fail or corrupt if deployment uses different Pillow version
- Migration plan: Pin all dependencies in `requirements.txt` with exact versions (already done). Test deployment environment with same Python+dependencies.

---

## Missing Critical Features

**No Transaction Audit Log:**
- Problem: Users can't see who created a lot/sale or when it was modified. No undo/correction mechanism.
- Blocks: Tax compliance (can't prove who authorized a transaction). Fraud detection (can't trace changes).
- Fix: Add `created_by` and `created_at` (already present). Implement soft deletes instead of hard deletes. Add admin-only audit log view.

**No Bulk Import for Historical Transactions:**
- Problem: Users must manually enter each buy/sell one-by-one via forms
- Blocks: Migrating existing portfolios from spreadsheets is tedious (100s of transactions = hours of data entry)
- Fix: Add CSV import view with validation. Parse `[symbol, buy_date, qty, price_usd, fx_rate]` rows. Bulk create with transactional safety.

**No Tax-Year Filtering or Reporting:**
- Problem: Report doesn't support filtering by tax year; reports all transactions
- Blocks: Users can't isolate realized gains by tax year for tax return filing
- Fix: Add `tax_year` parameter to report views. Filter allocations by `sell_date.year`. Add separate tax-year summary page.

**No Account Reconciliation or Validation:**
- Problem: No automated check that holdings match broker statements
- Blocks: Users can't verify data integrity. Manual errors aren't caught.
- Fix: Add optional broker data upload/sync. Calculate portfolio value checksum. Show warnings if calculated holdings don't match uploaded statement.

---

## Test Coverage Gaps

**Missing FIFO Allocation Tests:**
- What's not tested: `record_sale()` function — the core FIFO matching logic
- Files: `portfolio/services.py` (lines 222-286)
- Risk: Bugs in FIFO ordering could silently produce wrong cost basis or capital gains
- Priority: **HIGH** — This is the financial calculation engine; must be thoroughly tested

**Missing View Tests:**
- What's not tested: StockLotCreateView, SellView, LotListView, SaleListView, PortfolioReportView, evidence views
- Files: `portfolio/views.py` (entire file)
- Risk: AJAX form handling, permission filtering, and report generation errors won't be caught
- Priority: **HIGH** — Views handle all user interaction; must verify correctness and security

**Missing Permission/Isolation Tests:**
- What's not tested: Cross-user data isolation (user A can't see user B's lots/sales)
- Files: All views and query functions
- Risk: Critical security bug — users could access each other's financial data
- Priority: **CRITICAL** — Security regression could go unnoticed

**Missing Error Handling Tests:**
- What's not tested: FX rate fetch errors (URLError, HTTPError, timeout), price fetch errors, insufficient lots error, form validation errors
- Files: `portfolio/services.py` (fetch functions), `portfolio/forms.py` (clean methods), `portfolio/views.py` (form handling)
- Risk: Errors are silently converted to user messages without verification that messages are correct
- Priority: **HIGH** — User-facing error messages must be tested for accuracy

**Missing Report Tests:**
- What's not tested: CSV generation (formatting, correctness of values), PDF generation (no crashes on edge cases), report filtering by symbol
- Files: `portfolio/reports.py` (entire file)
- Risk: Reports could contain wrong numbers or crash on certain data
- Priority: **MEDIUM** — Reports are critical for tax filing; must be reliable

**No Integration Tests:**
- What's not tested: Full end-to-end flows (create user, record buy, record sale, view report)
- Files: N/A (test suite)
- Risk: Interactions between models, views, and services aren't verified
- Priority: **MEDIUM** — Integration tests catch configuration and cross-layer bugs

**No Load Tests:**
- What's not tested: Performance with large portfolios (1000+ transactions), concurrent price fetches, report generation under load
- Files: N/A (performance test suite)
- Risk: Scalability issues only surface in production
- Priority: **MEDIUM** — Should test dashboard response time with realistic data

---

## Recommendations Priority

### Immediate (Before Production Deployment)
1. Replace `CSRF_TRUSTED_ORIGINS` placeholder with actual domain
2. Add explicit cross-user data access tests to verify security isolation
3. Test on target deployment platform (Raspberry Pi) to verify stability
4. Add file upload validation (size, type)
5. Document deployment checklist in README

### Short-term (Next Sprint)
1. Write unit tests for `record_sale()` and error cases
2. Write view tests for AJAX forms and permission filtering
3. Add database indexes on frequently queried fields
4. Implement FX rate caching (at least 24-hour cache)
5. Add logging to price fetch failures and FIFO matching

### Medium-term (Next Release)
1. Migrate from SQLite to PostgreSQL for production deployments
2. Add list pagination to prevent large data loads
3. Implement parallel price fetching instead of sequential
4. Add tax-year filtering to reports
5. Document deployment architecture and capacity planning

### Long-term (Future Work)
1. Bulk import for historical transactions
2. Broker statement reconciliation
3. Additional price provider fallbacks
4. Async FX rate fetching in forms
5. Load testing with realistic portfolios

---

*Concerns audit: 2026-07-19*
