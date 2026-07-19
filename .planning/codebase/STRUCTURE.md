# Codebase Structure

**Analysis Date:** 2026-07-19

## Directory Layout

```
stock-fifo-django/
├── config/                      # Django project configuration (settings, URLs, WSGI/ASGI)
│   ├── __init__.py
│   ├── settings.py              # Project settings, installed apps, middleware, database config
│   ├── urls.py                  # Root URL router, includes portfolio.urls, auth views, media serve
│   ├── wsgi.py                  # WSGI application entry point
│   ├── asgi.py                  # ASGI application entry point
│
├── portfolio/                   # Main Django application (stock tracking, FIFO logic)
│   ├── __init__.py
│   ├── admin.py                 # Django admin registration (empty or minimal)
│   ├── apps.py                  # App configuration
│   ├── models.py                # Data models: Symbol, StockLot, Sale, SaleAllocation
│   ├── views.py                 # Class-based views (ListView, CreateView, FormView, DetailView)
│   ├── forms.py                 # Form classes: StockLotForm, SellForm, BootstrapAuthenticationForm
│   ├── urls.py                  # URL patterns for portfolio routes
│   ├── services.py              # Business logic: FIFO allocation, reporting, API integrations
│   ├── reports.py               # CSV/PDF report generation using ReportLab
│   ├── tests.py                 # Unit tests
│   │
│   ├── migrations/              # Database migration files
│   │   ├── __init__.py
│   │   ├── 0001_initial.py
│   │   ├── 0002_sale_evidence_stocklot_evidence.py
│   │
│   ├── templates/portfolio/     # Django templates (HTML)
│   │   ├── base.html                    # Base template (navbar, footer, blocks)
│   │   ├── lot_list.html                # Home page: dashboard + lots table + buy form modal
│   │   ├── lot_form.html                # Buy form standalone page
│   │   ├── sale_list.html               # Sales table + sell form modal
│   │   ├── sell_form.html               # Sell form standalone page
│   │   ├── lot_evidence.html            # Detail page: display evidence image for a lot
│   │   ├── sale_evidence.html           # Detail page: display evidence image for a sale
│   │   ├── partials/                    # Reusable template fragments
│   │   │   ├── lot_form.html            # Buy form partial (for AJAX modal re-render)
│   │   │   ├── sell_form.html           # Sell form partial (for AJAX modal re-render)
│   │
│   ├── templates/registration/ # Django auth templates
│   │   ├── login.html                   # Login page (custom Bootstrap styling)
│   │
│   ├── static/portfolio/        # Static files (CSS, JavaScript)
│   │   ├── style.css                    # Custom CSS (overrides Bootstrap, component styles)
│   │   ├── modal-forms.js               # AJAX modal form submission + error handling
│   │   ├── tokens/                      # Design system tokens
│   │   │   ├── colors.css               # Color variables
│   │   │   ├── spacing.css              # Spacing/layout variables
│   │   │   ├── typography.css           # Font/text variables
│   │
├── manage.py                    # Django management CLI entry point
├── requirements.txt             # Python dependencies (Django, yfinance, ReportLab, etc.)
├── db.sqlite3                   # SQLite database file (development, created after migrate)
├── .env                         # Environment variables (SECRET_KEY, DEBUG, etc.) — NOT in git
├── .gitignore                   # Git ignore rules
├── README.md                    # Project documentation, feature overview, getting started
├── skills-lock.json             # GSD skills lockfile
│
├── .claude/                     # Claude Code configuration
│   ├── skills/                  # Project-specific skills
│   │   └── django-fifo-conventions/   # Conventions skill for this Django project
│
├── .planning/                   # GSD planning artifacts
│   ├── codebase/                # Codebase mapping documents (ARCHITECTURE.md, STRUCTURE.md, etc.)
│
├── .git/                        # Git repository
└── .venv/                       # Python virtual environment (local development, not committed)
```

## Directory Purposes

**config/:**
- Purpose: Project-wide configuration, routing, application setup
- Contains: Django settings module, URL dispatcher, WSGI/ASGI applications
- Key files: `settings.py` (database, installed apps, middleware, auth config), `urls.py` (root routes)

**portfolio/:**
- Purpose: Core application — models, business logic, views, forms, templates
- Contains: All application code except project config
- Key files: `models.py` (data schema), `services.py` (FIFO logic), `views.py` (request handlers), `forms.py` (validation)

**portfolio/migrations/:**
- Purpose: Database migration history
- Contains: Auto-generated migration files tracking schema changes
- Key files: `0001_initial.py` (Symbol, StockLot, Sale, SaleAllocation tables), `0002_...` (evidence image fields)

**portfolio/templates/portfolio/:**
- Purpose: Django template files (HTML + template tags)
- Contains: List pages, form pages, evidence detail pages, base layout
- Key patterns: {% url %} for reverse routing, {% if request.user.is_authenticated %} for auth checks, AJAX form handling

**portfolio/templates/registration/:**
- Purpose: Django auth templates (separate app namespace)
- Contains: Login page
- Key: Custom `BootstrapAuthenticationForm` applied in config/urls.py

**portfolio/static/portfolio/:**
- Purpose: Frontend assets (CSS, JavaScript)
- Contains: Custom styles, AJAX modal form behavior, design tokens
- Served by: Django's static file handler (dev) or collected to STATIC_ROOT (production)

**.env file:**
- Purpose: Environment-specific configuration
- Contains: SECRET_KEY, DEBUG, ALLOWED_HOSTS, database credentials (if not SQLite)
- **Never committed to git**

**db.sqlite3:**
- Purpose: SQLite database file (development only)
- Created: After running `python manage.py migrate`
- **Not committed to git** (generated per environment)

## Key File Locations

**Entry Points:**
- `manage.py`: Django management CLI (`python manage.py runserver`, `python manage.py migrate`, etc.)
- `config/wsgi.py`: WSGI application (for production servers like Gunicorn)
- `config/asgi.py`: ASGI application (for async servers like Daphne)
- `config/urls.py`: Root URL dispatcher (routes all requests to views)

**Configuration:**
- `config/settings.py`: Django settings (database, installed apps, middleware, auth, static files, media, etc.)
- `.env`: Environment variables (not in repo; created locally)
- `requirements.txt`: Python package dependencies

**Core Logic:**
- `portfolio/models.py`: Data models (Symbol, StockLot, Sale, SaleAllocation)
- `portfolio/services.py`: Business logic (record_sale, build_fifo_report, build_dashboard_summary, API integrations)
- `portfolio/forms.py`: Form validation, auto-fetch logic
- `portfolio/views.py`: HTTP request handlers (class-based views)

**Database:**
- `portfolio/migrations/`: Migration files (track schema changes)
- `db.sqlite3`: Database file (created locally)

**Templates:**
- `portfolio/templates/portfolio/lot_list.html`: Home page (dashboard + lots table)
- `portfolio/templates/portfolio/sale_list.html`: Sales history
- `portfolio/templates/portfolio/base.html`: Base layout (navbar, blocks)
- `portfolio/templates/registration/login.html`: Login form

**Styling & Interaction:**
- `portfolio/static/portfolio/style.css`: Custom CSS (overrides Bootstrap)
- `portfolio/static/portfolio/modal-forms.js`: AJAX form submission behavior
- `portfolio/static/portfolio/tokens/`: Design tokens (colors, spacing, typography)

**Testing:**
- `portfolio/tests.py`: Unit tests for models, forms, services

**Reporting:**
- `portfolio/reports.py`: CSV/PDF export generation (ReportLab)

## Naming Conventions

**Files:**
- Python modules: `lowercase_with_underscores.py` (e.g., `services.py`, `models.py`)
- Templates: `lowercase_with_underscores.html` (e.g., `lot_list.html`, `base.html`)
- Static files: `lowercase-with-hyphens` or `.scss`/`.css` (e.g., `modal-forms.js`, `style.css`)
- Migrations: `NNNN_description.py` (auto-generated; e.g., `0001_initial.py`)

**Directories:**
- Django apps: `app_name/` (e.g., `portfolio/`)
- Config: `config/`
- Namespaced dirs: `lowercase/` (e.g., `migrations/`, `templates/`, `static/`, `tokens/`)
- Versioned/feature dirs: Match kebab-case (e.g., `.agents/`, `.claude/`, `.planning/`)

**Python Symbols:**
- Classes: `PascalCase` (e.g., `StockLot`, `SellForm`, `LotListView`)
- Functions: `lowercase_with_underscores` (e.g., `record_sale`, `build_fifo_report`)
- Constants: `UPPERCASE_WITH_UNDERSCORES` (e.g., `PRICE_FETCH_TIMEOUT_SECONDS` in services.py)
- Private/internal: Leading underscore (e.g., `_fetch_last_price`, `_fmt_qty` in reports.py)

**URL Names:**
- Format: `lowercase_with_underscores` (e.g., `lot_list`, `sell_create`, `fifo_report`)
- Pattern: `{action}_{resource}` (e.g., `lot_create`, `sale_list`) or just `{resource}_{action}` if ambiguous
- Location: Defined in `portfolio/urls.py`, referenced in templates as `{% url 'lot_list' %}`

**Model Fields:**
- Format: `lowercase_with_underscores` (e.g., `buy_date`, `price_usd`, `fx_rate_usd_thb`)
- Suffix convention: `_date` for DateField, `_usd` for USD amounts, `_thb` for THB amounts
- Relationship fields: Singular (e.g., `owner`, `symbol`) or descriptive plural (e.g., `allocations` for reverse FK)

## Where to Add New Code

**New Feature (e.g., "add position averaging"):**
- **Primary code:** `portfolio/services.py` — Add service function (e.g., `compute_position_average()`)
- **Tests:** `portfolio/tests.py` — Add test cases for service function
- **Models:** `portfolio/models.py` — Add computed properties or new model if needed
- **Forms:** `portfolio/forms.py` — Modify existing form or add new form class if user input required
- **Views:** `portfolio/views.py` — Add new view class or modify existing (e.g., extend LotListView to pass new data)
- **Templates:** `portfolio/templates/portfolio/` — Add new page or modify existing template to display data
- **URL:** `portfolio/urls.py` — Add new route if new page view added

**New Component/Module (e.g., "add expense tracking"):**
- **Directory:** Create new Django app (e.g., `expenses/`) at project root level with same structure as `portfolio/`
- **Models:** `expenses/models.py` — Define data schema
- **Services:** `expenses/services.py` — Encapsulate business logic
- **Views:** `expenses/views.py` — Handle HTTP requests
- **Forms:** `expenses/forms.py` — Validation
- **Templates:** `expenses/templates/expenses/` — HTML pages
- **URL inclusion:** Add `path('expenses/', include('expenses.urls'))` in `config/urls.py`
- **Installation:** Add `'expenses'` to INSTALLED_APPS in `config/settings.py`

**Utilities/Helpers:**
- **Shared helpers across views:** Add to `portfolio/services.py` or create `portfolio/utils.py`
- **Form-specific helpers:** Keep in `portfolio/forms.py`
- **Template tag/filter:** Create `portfolio/templatetags/` directory with `__init__.py` and custom tags file (e.g., `portfolio_filters.py`)

**Static assets (CSS, JS):**
- **Component-specific CSS:** Add to `portfolio/static/portfolio/style.css` under a `.component-name {}` block
- **Global CSS tokens:** Modify `portfolio/static/portfolio/tokens/colors.css`, `spacing.css`, or `typography.css`
- **Interaction logic:** Add to `portfolio/static/portfolio/modal-forms.js` or create new JS file in `portfolio/static/portfolio/`

**Database changes:**
- **Model schema changes:** Modify `portfolio/models.py`, then run `python manage.py makemigrations portfolio` to auto-generate migration file
- **Migration review:** Check generated file in `portfolio/migrations/` before applying with `python manage.py migrate`

**Tests:**
- **Unit tests:** Add test functions/classes to `portfolio/tests.py` (or split into `portfolio/tests/` directory if growing large)
- **Run tests:** `python manage.py test portfolio`

## Special Directories

**portfolio/migrations/:**
- Purpose: Track database schema changes over time
- Generated: Automatically by `python manage.py makemigrations`
- Committed: Yes, to git (ensures team stays in sync)
- Manual edits: Rare; use Django's `RunPython()` operation if custom logic needed

**portfolio/static/:**
- Purpose: Static assets (CSS, JS, images) served to browser
- Generated: Hand-written, not auto-generated
- Committed: Yes, to git
- Production: Collected to STATIC_ROOT via `python manage.py collectstatic`

**portfolio/templates/:**
- Purpose: HTML templates rendered by Django
- Generated: Hand-written, not auto-generated
- Committed: Yes, to git
- APP_DIRS: Configured in settings.py so Django auto-discovers templates in `app/templates/app/`

**.env:**
- Purpose: Local environment configuration (development only)
- Generated: Hand-created per developer/environment
- Committed: No (in .gitignore)
- Required values: SECRET_KEY, DEBUG=True (dev), ALLOWED_HOSTS=localhost,127.0.0.1

**db.sqlite3:**
- Purpose: SQLite database file (development only)
- Generated: Created by `python manage.py migrate`
- Committed: No (in .gitignore)
- Reset: Delete file and re-run migrate to start fresh

**.planning/codebase/:**
- Purpose: GSD codebase mapping documents (ARCHITECTURE.md, STRUCTURE.md, etc.)
- Generated: By `/gsd-map-codebase` skill
- Committed: Yes, to git
- Consumed by: `/gsd-plan-phase` and `/gsd-execute-phase` for code generation guidance

---

*Structure analysis: 2026-07-19*
