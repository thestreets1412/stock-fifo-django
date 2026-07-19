# Technology Stack

**Analysis Date:** 2026-07-19

## Languages

**Primary:**
- Python 3.14.6 - Backend web application and services

## Runtime

**Environment:**
- Python 3.14.6

**Package Manager:**
- pip
- Lockfile: `requirements.txt` (present)

## Frameworks

**Core:**
- Django 6.0.7 - Web framework for portfolio management application
- Django built-in authentication - User login/logout and session management
- Django ORM - Database abstraction layer

**Templating:**
- Django Template Engine - Server-side HTML rendering

**Testing:**
- Django TestCase - Built-in testing framework (used in `portfolio/tests.py`)

**Build/Dev:**
- Python standard library tooling (no webpack/npm)

## Key Dependencies

**Critical:**
- yfinance 1.5.1 - Fetches real-time stock prices from Yahoo Finance
- urllib (standard library) - Used for Frankfurter API integration
- json (standard library) - Parsing API responses
- concurrent.futures - Thread pool for timeout management on price fetches

**Data & Processing:**
- pandas 3.0.3 - Data analysis and manipulation (used by yfinance)
- numpy 2.5.1 - Numerical computing (required by pandas)
- Decimal (standard library) - High-precision financial calculations

**PDF & Document Generation:**
- reportlab 5.0.0 - PDF report generation (FIFO reports)
- beautifulsoup4 4.15.0 - HTML parsing
- pillow 12.3.0 - Image handling (for evidence photos in forms)

**Database:**
- sqlparse 0.5.5 - SQL formatting

**Utilities:**
- python-decouple 3.8 - Environment variable management
- pytz 2026.2 - Timezone support
- python-dateutil 2.9.0 - Advanced date handling
- requests 2.34.2 - HTTP client (optional, yfinance handles most HTTP)
- curl_cffi 0.15.0 - Advanced HTTP handling with curl backend
- websockets 16.1 - WebSocket support (imported but usage unclear)
- Pygments 2.20.0 - Syntax highlighting
- markdown-it-py 4.2.0 - Markdown parsing
- rich 15.0.0 - Rich text formatting in terminal
- multitasking 0.0.13 - Task scheduling (used by yfinance)
- peewee 4.2.6 - Alternative ORM (not primary, imported but not used)

**Security & Validation:**
- certifi 2026.6.17 - SSL/TLS certificate validation
- cffi 2.1.0 - C Foreign Function Interface
- pycparser 3.0 - C parser

**Framework Support:**
- asgiref 3.11.1 - ASGI compatibility layer
- typing_extensions 4.16.0 - Type hint backports
- platformdirs 4.10.0 - Platform-specific directory paths
- charset-normalizer 3.4.9 - Character encoding detection
- idna 3.18 - Internationalized domain names
- urllib3 2.7.0 - HTTP utilities
- six 1.17.0 - Python 2/3 compatibility
- soupsieve 2.8.4 - CSS selector library
- protobuf 7.35.1 - Protocol buffers
- tzdata 2026.3 - Timezone database

## Configuration

**Environment:**
- Managed via `python-decouple` using `.env` file (`.env` file present but not readable)
- `config/settings.py` contains all Django configuration

**Key Environment Variables (from settings.py):**
- `SECRET_KEY` - Django secret key (required)
- `DEBUG` - Debug mode toggle (default: False)
- `ALLOWED_HOSTS` - Comma-separated list of allowed hosts (default: '127.0.0.1,localhost')

**Build:**
- No build configuration (Django runs directly via `manage.py`)
- Static files served from `STATIC_ROOT = BASE_DIR / 'staticfiles'` (`config/settings.py:128`)
- Media uploaded to `MEDIA_ROOT = BASE_DIR / 'media'` (`config/settings.py:134`)

## Platform Requirements

**Development:**
- Python 3.14.6
- Virtual environment (`.venv` present)
- Local SQLite database (`db.sqlite3`)
- File system access for media uploads and static files

**Production:**
- Python 3.14.6 runtime
- WSGI server required (Django WSGI application at `config/wsgi.py`)
- ASGI alternative available (`config/asgi.py`) for async deployment
- Static file serving (via whitenoise or reverse proxy)
- SQLite database (or migrate to PostgreSQL/MySQL for production scale)
- Network access to:
  - `https://api.frankfurter.app/` (USD/THB exchange rates)
  - `https://query*.finance.yahoo.com/` (stock prices via yfinance)

## Database

**Current:**
- SQLite3 - File-based database at `db.sqlite3`
- Configuration: `config/settings.py:85-90`

**Models:**
- `Symbol` - Stock tickers and names
- `StockLot` - Buy transactions with FIFO ordering
- `Sale` - Sell transactions
- `SaleAllocation` - Links sales to the specific lots they consumed (FIFO tracking)

---

*Stack analysis: 2026-07-19*
