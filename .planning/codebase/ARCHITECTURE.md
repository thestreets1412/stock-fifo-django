<!-- refreshed: 2026-07-19 -->
# Architecture

**Analysis Date:** 2026-07-19

## System Overview

```text
┌─────────────────────────────────────────────────────────────────┐
│                   Presentation Layer (Templates)                │
│  `portfolio/templates/` + Bootstrap 5 + Chart.js (CDN)          │
│  (lot_list, sale_list, forms, evidence, login)                  │
└────────────────────┬────────────────────────────────────────────┘
                     │
┌────────────────────┴────────────────────────────────────────────┐
│                 View Layer (CBVs + Forms)                       │
│  `portfolio/views.py` + `portfolio/forms.py`                    │
│  (LotListView, SellView, PortfolioReportView, etc.)             │
└────────────────────┬────────────────────────────────────────────┘
                     │
┌────────────────────┴────────────────────────────────────────────┐
│            Service / Business Logic Layer                        │
│  `portfolio/services.py`                                         │
│  (record_sale, build_fifo_report, build_dashboard_summary)      │
│  + External API integrations (Frankfurter, yfinance)            │
└────────────────────┬────────────────────────────────────────────┘
                     │
┌────────────────────┴────────────────────────────────────────────┐
│              ORM Model Layer & Database                          │
│  `portfolio/models.py` + `config/settings.py`                   │
│  (Symbol, StockLot, Sale, SaleAllocation → SQLite)              │
└─────────────────────────────────────────────────────────────────┘
```

## Component Responsibilities

| Component | Responsibility | File |
|-----------|----------------|------|
| Views | HTTP routing, request handling, user authentication, response generation | `portfolio/views.py` |
| Forms | Input validation, FX rate auto-fetch, widget styling | `portfolio/forms.py` |
| Services | FIFO allocation logic, reporting, dashboard calculations, price/FX fetches | `portfolio/services.py` |
| Models | Data schema, query ordering (FIFO), cost basis properties | `portfolio/models.py` |
| Reports | CSV/PDF export formatting and generation | `portfolio/reports.py` |
| Templates | HTML rendering, AJAX form submission, dashboard UI | `portfolio/templates/` |
| Static Assets | CSS overrides, AJAX modal form behavior | `portfolio/static/` |
| Config | Project settings, middleware, database, authentication | `config/settings.py`, `config/urls.py` |

## Pattern Overview

**Overall:** Standard Django MVT (Model-View-Template) with an explicit service layer for business logic and external integrations.

**Key Characteristics:**
- **User-scoped data isolation** — All queries filter by `owner = request.user`; no cross-user data leakage
- **Immutable transaction records** — StockLots and Sales never edited; corrections use offsetting transactions
- **FIFO enforcement in DB** — Lot ordering hardcoded in Meta.ordering; FIFO driven by database sort, not code
- **Atomic transaction handling** — Sale creation + allocation locked via `@transaction.atomic` + `select_for_update()`
- **Graceful degradation** — Dashboard price fetches time out per-symbol without breaking overall page load

## Layers

**Presentation Layer:**
- Purpose: Render HTML, handle AJAX form submissions, display user-facing data
- Location: `portfolio/templates/`, `portfolio/static/`
- Contains: HTML templates (base, list views, form partials), CSS overrides, JavaScript (AJAX modal forms)
- Depends on: View layer (for context data), Bootstrap 5 (CDN), Chart.js (CDN)
- Used by: Web browser

**View & Form Layer:**
- Purpose: Parse HTTP requests, validate input, dispatch to services, format responses
- Location: `portfolio/views.py`, `portfolio/forms.py`
- Contains: Class-based views (ListView, CreateView, FormView), form classes (StockLotForm, SellForm)
- Depends on: Service layer (business logic), Models (data access), Django auth
- Used by: URL router, templates (for rendering context)

**Service Layer:**
- Purpose: Encapsulate business logic — FIFO allocation, reporting, dashboard calculations, external API calls
- Location: `portfolio/services.py`
- Contains: `record_sale()`, `build_fifo_report()`, `build_dashboard_summary()`, `fetch_usd_thb_rate()`, `fetch_current_price()`
- Depends on: Models (data queries/creation), external APIs (Frankfurter, yfinance)
- Used by: Views, forms (validation during form clean)

**Model / ORM Layer:**
- Purpose: Define data schema, enforce database constraints, provide query interface
- Location: `portfolio/models.py`
- Contains: Symbol, StockLot, Sale, SaleAllocation models with Meta.ordering and property methods
- Depends on: Django ORM, SQLite database
- Used by: Service layer, views, forms

**Report Generation Layer:**
- Purpose: Format and export FIFO data as CSV or PDF
- Location: `portfolio/reports.py`
- Contains: CSV writer, PDF/table builders, styling, formatting functions
- Depends on: Models (data), ReportLab (PDF), stdlib csv
- Used by: PortfolioReportView

**Configuration Layer:**
- Purpose: Project-wide settings, routing, middleware, database, authentication
- Location: `config/settings.py`, `config/urls.py`, `config/wsgi.py`, `config/asgi.py`
- Contains: Django settings, URL patterns, WSGI/ASGI application
- Depends on: Django core
- Used by: Entire application

## Data Flow

### Primary Request Path: Record a Buy

1. **Browser → View** (`portfolio/views.py:StockLotCreateView`) — POST to `/buy/` with form data
2. **View → Form validation** (`portfolio/forms.py:StockLotForm`) — Validates fields; auto-fetches FX rate via `fetch_usd_thb_rate()` if blank
3. **View → Model create** (`portfolio/models.py:StockLot.objects.create()`) — Inserts buy lot, sets owner
4. **Response** — JSON (AJAX) or redirect (non-AJAX) to lot list
5. **Template render** (`portfolio/templates/portfolio/lot_list.html`) — Lists all user's lots, showing qty_remaining per lot

### Primary Request Path: Record a Sell

1. **Browser → View** (`portfolio/views.py:SellView`) — POST to `/sell/` with form data (symbol, qty_sold, etc.)
2. **View → Form validation** (`portfolio/forms.py:SellForm`) — Auto-fetches FX rate if needed
3. **View → Service** (`portfolio/services.py:record_sale()`) — Atomically locks StockLots, creates Sale, allocates qty FIFO
4. **Service → FIFO Allocation** — Walks lots oldest-first, creates SaleAllocation rows, rolls back if insufficient qty
5. **View → Response** — JSON (AJAX) or redirect to sale list
6. **Template render** (`portfolio/templates/portfolio/sale_list.html`) — Lists all sales; shows per-sale capital gain

### Dashboard Summary Generation

1. **Browser → View** (`portfolio/views.py:LotListView.get_context_data()`) — GET `/` (home)
2. **View → Service** (`portfolio/services.py:build_dashboard_summary()`) — Builds portfolio stats
3. **Service flow**:
   - Calls `build_fifo_report()` to get per-symbol remaining qty and cost basis
   - Fetches today's USD/THB rate (Frankfurter API, degradable if timeout)
   - Per-symbol: Fetches current price (yfinance, 5s timeout per ticker, per-symbol degradation)
   - Computes: unrealized_gain_thb = (current_price × qty_remaining × fx_rate) - cost_basis
   - Returns dashboard dict with totals and per-symbol rows
4. **Template render** (`portfolio/templates/portfolio/lot_list.html`) — Renders dashboard stat cards + holdings table

### Report Export Flow

1. **Browser → View** (`portfolio/views.py:PortfolioReportView`) — GET `/reports/fifo/?format=pdf&symbol=123`
2. **View → Service** (`portfolio/services.py:build_fifo_report()`) — Builds report data structure (sections by ticker)
3. **View → Report generator**:
   - If `format=pdf`: calls `portfolio/reports.py:fifo_report_pdf_response()` → ReportLab → BytesIO → HTTP response (PDF)
   - If `format=csv`: calls `portfolio/reports.py:fifo_report_csv_response()` → stdlib csv → HTTP response (CSV)
4. **Response** — File download (attachment)

**State Management:**
- User authentication state: Django sessions + `LoginRequiredMixin` on all user-facing views
- No client-side state beyond form inputs (all state lives in database)
- AJAX modal forms reset after success; partial re-renders on validation error

## Key Abstractions

**StockLot (Buy Transaction):**
- Purpose: Represents an immutable purchase record
- Examples: `portfolio/models.py:StockLot`
- Pattern: Model with computed properties (`qty_remaining`, `cost_thb`); never edited after creation
- Invariant: `qty_remaining = qty - sum(allocations.qty_allocated)` — kept consistent by FIFO allocation logic

**Sale (Sell Transaction):**
- Purpose: Represents an immutable sale record
- Examples: `portfolio/models.py:Sale`
- Pattern: Model with computed properties (`proceeds_thb`, `capital_gain_thb`); foreign key to allocations
- Invariant: `capital_gain_thb = proceeds_thb - total_cost_basis_thb` — always recalculated from allocations

**SaleAllocation (FIFO Link):**
- Purpose: Joins a Sale to the specific Lots it drew from; records qty and cost basis per lot
- Examples: `portfolio/models.py:SaleAllocation`
- Pattern: Through-model with qty_allocated and cost_basis_thb; created atomically during sale recording
- Invariant: Qty and cost basis never changed; records are immutable

**FIFO Report (Data Transfer Object):**
- Purpose: Packages per-symbol totals and transaction history for display/export
- Examples: Data structure returned by `build_fifo_report()` in `portfolio/services.py`
- Pattern: Dict with keys (symbol, lots, sales, total_bought_qty, remaining_qty, realized_gain_thb, etc.)
- Invariant: Lots ordered oldest-first; allocations pre-sorted per sale

**Dashboard Summary (Data Transfer Object):**
- Purpose: Packages portfolio-wide live metrics (cost basis, market value, unrealized gain)
- Examples: Data structure returned by `build_dashboard_summary()` in `portfolio/services.py`
- Pattern: Dict with keys (rows=[per-symbol row], allocation=[allocation array], totals)
- Invariant: Per-symbol current_value_thb and unrealized_gain_thb can be None if price fetch fails; graceful degradation

## Entry Points

**Web Server Entry Point:**
- Location: `config/wsgi.py` (WSGI) or `config/asgi.py` (ASGI)
- Triggers: HTTP request to deployed server
- Responsibilities: Load Django application, route request to URL dispatcher

**URL Dispatcher:**
- Location: `config/urls.py`
- Triggers: HTTP request arrival
- Responsibilities: Route to portfolio URLs (`portfolio/urls.py`), admin, login/logout, media serve

**Portfolio URL Dispatcher:**
- Location: `portfolio/urls.py`
- Triggers: Request to `/`, `/buy/`, `/sell/`, `/sales/`, `/lots/<id>/evidence/`, `/reports/fifo/`
- Responsibilities: Map routes to views

**Primary Views:**
- `LotListView` (`portfolio/views.py`) — GET `/` (home/lot list) → dashboard + lots table
- `StockLotCreateView` (`portfolio/views.py`) — POST `/buy/` → create StockLot → redirect/JSON
- `SellView` (`portfolio/views.py`) — POST `/sell/` → call record_sale() → redirect/JSON
- `SaleListView` (`portfolio/views.py`) — GET `/sales/` → sales table + sales form
- `PortfolioReportView` (`portfolio/views.py`) — GET `/reports/fifo/?format=[csv|pdf]` → file download
- `LotEvidenceView`, `SaleEvidenceView` (`portfolio/views.py`) — GET `/lots/<id>/evidence/` / `/sales/<id>/evidence/` → evidence image

**Authentication Entry Point:**
- Location: `config/urls.py:LoginView` (Django auth view)
- Triggers: GET `/login/` or redirect after unauthenticated access
- Responsibilities: Render login form, validate credentials, set session cookie

## Architectural Constraints

- **Threading:** Django serves requests in an HTTP thread pool (WSGI/ASGI). Service layer uses `concurrent.futures.ThreadPoolExecutor` for yfinance price fetches to enforce timeout without blocking other requests. All database queries are single-threaded per request (Django ORM is thread-safe; SQLite is single-writer).
- **Global state:** No module-level singletons or shared mutable state; all state in database or request context.
- **Circular imports:** None detected. Layers import downward only: views → services → models; no reverse imports.
- **Database transactions:** FIFO sale recording uses `@transaction.atomic` + `select_for_update()` to prevent race conditions on concurrent sales of the same symbol.
- **User scoping:** Every query explicitly filters by `owner=request.user`; no `select_related()` or `prefetch_related()` that bypasses this filter. LoginRequiredMixin enforces auth on all views.
- **External API dependencies:** Frankfurter API (USD/THB rates) and yfinance (prices) are gracefully degraded — failures don't crash the page, just show "—" or None in the UI.
- **Immutability:** StockLot and Sale records are never edited after creation; all corrections via offsetting transactions. This ensures FIFO ledger stays trustworthy and audit-friendly.

## Error Handling

**Strategy:** Exceptions raised in service layer; caught and re-displayed in forms (form.add_error()); users see validation messages in the modal or form page.

**Patterns:**
- `InsufficientLotsError` (services.py) — Raised by record_sale() if total remaining qty can't cover sale; caught in SellView.form_valid() → form.add_error()
- `FxRateFetchError` (services.py) — Raised by fetch_usd_thb_rate() if API unreachable; caught in form clean methods → ValidationError
- `PriceFetchError` (services.py) — Raised by fetch_current_price() if yfinance fails or times out; caught in build_dashboard_summary() → symbol shows None in dashboard (graceful degradation)
- Constraint violations (models.py) — Database-level CHECK constraint on SaleAllocation.qty_allocated > 0; would surface as IntegrityError if violated (shouldn't happen if allocation logic is correct)

## Cross-Cutting Concerns

**Logging:** No explicit logging framework configured; uses Django's default console logging (see `LOGGING` in `config/settings.py` — not present, so Django defaults apply). Can be added per project requirements.

**Validation:** Two-tier validation: form-level (Django forms, custom clean methods) + model-level (Meta.constraints on SaleAllocation). Forms auto-fetch FX rates and validate before submission; models enforce immutability and positive allocations.

**Authentication:** Django's built-in auth (`django.contrib.auth`). LoginRequiredMixin on all user-facing views; unauthenticated requests redirect to login. No role-based access control (no admin vs. regular user distinction in UI); all users have same capabilities within their own data.

**File uploads:** Evidence images (StockLot.evidence, Sale.evidence) handled by Django's FileField; stored in MEDIA_ROOT (`media/`), served via URL redirect in templates. No size limits set (Django defaults to max 2.5GB per file).

---

*Architecture analysis: 2026-07-19*
