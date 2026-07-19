# External Integrations

**Analysis Date:** 2026-07-19

## APIs & External Services

**Financial Data:**
- **Yahoo Finance** - Real-time stock prices and market data
  - SDK/Client: `yfinance 1.5.1`
  - Implementation: `portfolio/services.py:111-138` (`fetch_current_price()`)
  - Usage: Dashboard displays current market value of holdings
  - Timeout: 5 seconds (enforced via ThreadPoolExecutor)
  - Graceful degradation: If fetch fails, symbol's `current_value_thb` and unrealized gain shown as None

- **Frankfurter API** (Free, no key required) - USD→THB exchange rates
  - API Endpoint: `https://api.frankfurter.app/{date}?from=USD&to=THB`
  - Client: Python `urllib` standard library
  - Implementation: `portfolio/services.py:31-43` (`fetch_usd_thb_rate()`)
  - Data Source: ECB (European Central Bank) + central bank data
  - Usage: Auto-fetches exchange rates for buy dates and sell dates if not manually entered
  - Form integration: `portfolio/forms.py:37-47` (StockLotForm) and `portfolio/forms.py:85-95` (SellForm)
  - Error handling: Raises `FxRateFetchError` on network/parse failure

## Data Storage

**Databases:**
- SQLite3 (development/small-scale)
  - Connection: `config/settings.py:85-90`
  - Database file: `db.sqlite3` (in project root)
  - Client: Django ORM
  - Tables: `portfolio_symbol`, `portfolio_stocklot`, `portfolio_sale`, `portfolio_saleallocation`

**File Storage:**
- Local filesystem only
  - Evidence photos (buy lot receipts): `media/lot_evidence/`
  - Evidence photos (sale confirmation): `media/sale_evidence/`
  - Configuration: `config/settings.py:133-134`
  - Managed by: Django FileField/ImageField

**Caching:**
- None configured
- Database queries cached in memory during request lifecycle via Django ORM queryset caching
- No Redis/Memcached integration

## Authentication & Identity

**Auth Provider:**
- Django built-in authentication system
  - Implementation: `config/urls.py:27-31` (LoginView, LogoutView)
  - Form: `portfolio/forms.py:14-16` (BootstrapAuthenticationForm)
  - Permission: LoginRequiredMixin applied to all portfolio views (`portfolio/views.py`)
  - Session-based authentication (HTTP cookies)
  - Password validation: Full Django password validators in `config/settings.py:96-109`

## Monitoring & Observability

**Error Tracking:**
- None configured
- Custom exceptions defined:
  - `portfolio/services.py:16-18` - `InsufficientLotsError`
  - `portfolio/services.py:21-23` - `FxRateFetchError`
  - `portfolio/services.py:26-28` - `PriceFetchError`

**Logs:**
- No logging framework configured
- Print/debug statements available via Django debug toolbar (if enabled in development)
- Production errors may be logged to Django's default stderr/syslog

## CI/CD & Deployment

**Hosting:**
- Not yet deployed (development stage)
- WSGI application: `config/wsgi.py`
- ASGI application: `config/asgi.py` (for async-capable deployment)
- Deployable to: Heroku, AWS, DigitalOcean, Raspberry Pi (mentioned in git history)

**CI Pipeline:**
- None configured
- Testing: `portfolio/tests.py` contains unit tests (run via `python manage.py test`)

**Security (Phase 1 noted):**
- CSRF protection enabled: `config/settings.py:52-59`
- HTTPS redirect configured for production: `config/settings.py:34-37`
- HSTS enabled: `SECURE_HSTS_SECONDS = 31536000` (`config/settings.py:37`)
- Secure cookies for production: `SESSION_COOKIE_SECURE = not DEBUG` (`config/settings.py:35`)
- Comment in settings: TODO - replace placeholder CSRF origin with real domain in Phase 4 (`config/settings.py:33`)

## Environment Configuration

**Required env vars:**
- `SECRET_KEY` - Django secret key (generated, must be kept secret)
- `DEBUG` - Boolean, defaults to False for security
- `ALLOWED_HOSTS` - Comma-separated hosts (defaults to '127.0.0.1,localhost')

**Secrets location:**
- `.env` file (present, contains configuration and secrets)
- Never committed to git (in `.gitignore`)

## Webhooks & Callbacks

**Incoming:**
- None configured

**Outgoing:**
- None configured
- Potential use case: Could integrate with tax reporting, accounting software in future

## API Endpoints (Internal/UI)

**Stock Lot Management:**
- `GET /` - Dashboard + lot list (`LotListView`)
- `POST /lots/` - Create stock lot (`StockLotCreateView`)
- `GET /lots/<id>/evidence/` - View evidence photo (`LotEvidenceView`)

**Sale Management:**
- `GET /sales/` - Sales list (`SaleListView`)
- `POST /sales/` - Record sale via FIFO (`SellView`)
- `GET /sales/<id>/evidence/` - View evidence photo (`SaleEvidenceView`)

**Reports:**
- `GET /report/?format=csv` - CSV export (all transactions, full precision)
- `GET /report/?format=pdf` - PDF export (formal layout, one ticker per page)
- Optional: `?symbol=<id>` - Filter to single ticker

## Rate Limiting & Quotas

**Yahoo Finance (via yfinance):**
- Rate limits exist but not explicitly enforced by this app
- Free tier has soft limits (typically ~2000 requests/hour)
- 5-second timeout per request to handle rate limiting gracefully

**Frankfurter API:**
- Free tier has soft limits (typically ~300 requests/hour)
- No explicit rate limiting in code

---

*Integration audit: 2026-07-19*
