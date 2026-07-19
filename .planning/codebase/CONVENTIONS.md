# Coding Conventions

**Analysis Date:** 2026-07-19

## Naming Patterns

**Files:**
- Django app structure: lowercase with underscores (`models.py`, `views.py`, `services.py`, `forms.py`, `reports.py`, `tests.py`, `urls.py`, `admin.py`)
- Test files: `tests.py` (co-located with app source)
- Modules: `portfolio/`, `config/` (app and config packages)

**Functions:**
- snake_case for all functions and methods: `fetch_usd_thb_rate()`, `build_fifo_report()`, `record_sale()`, `get_user_lots()`
- Private/internal functions: prefix with `_` (`_fetch_last_price()`, `_fmt_qty()`, `_lot_table()`, `_header_footer()`)
- View classes: PascalCase ending with "View" (`LotListView`, `StockLotCreateView`, `SellView`, `PortfolioReportView`)
- Form classes: PascalCase ending with "Form" (`StockLotForm`, `SellForm`, `BootstrapAuthenticationForm`)
- Model classes: PascalCase singular (`StockLot`, `Sale`, `SaleAllocation`, `Symbol`)

**Variables:**
- snake_case for all local variables and instance attributes
- Decimal precision tracked: `qty_remaining`, `cost_thb`, `capital_gain_thb`, `fx_rate_usd_thb`
- Boolean flags: `has_full_value`, `is_ajax()`

**Types/Models:**
- Django model fields explicitly typed with field type: `CharField()`, `DecimalField()`, `DateField()`, `ForeignKey()`, `ImageField()`
- Constants in UPPERCASE with underscores: `CSV_HEADERS`, `PRICE_FETCH_TIMEOUT_SECONDS`, `GAIN_COLOR`, `LOSS_COLOR`, `HEADER_BG`
- Meta classes on models for ordering and constraints

## Code Style

**Formatting:**
- Spaces around operators: `= `, ` + `, ` - `
- Line length: Generally follows ~80-100 character convention (some lines go longer for readability)
- Indentation: 4 spaces per level (Python standard)
- Blank lines: Two blank lines between top-level definitions, one blank line between methods

**Linting:**
- No explicit linter configuration files found (no `.pylintrc`, `.flake8`, `pyproject.toml`)
- Code follows PEP 8 conventions by default
- Uses Django's code style guidelines

## Import Organization

**Order:**
1. Standard library imports (`json`, `csv`, `decimal`, `urllib`, `datetime`, `concurrent.futures`)
2. Third-party imports (`django.*`, `yfinance`, `reportlab`)
3. Local/relative imports (`.models`, `.forms`, `.services`)

**Path Aliases:**
- No path aliases configured; uses full import paths
- Relative imports used within app: `from .models import`, `from .services import`

**Examples:**
```python
# Standard library first
from decimal import Decimal, InvalidOperation
from urllib.error import URLError, HTTPError
from urllib.request import Request, urlopen

# Third-party
from django.db import transaction
from django.db.models import Q

# Local
from .models import StockLot, Sale, SaleAllocation, Symbol
```

## Error Handling

**Patterns:**
- Custom exceptions inherit from `Exception`: `InsufficientLotsError`, `FxRateFetchError`, `PriceFetchError`
- Exception messages include context: `f"Could not fetch USD/THB rate for {rate_date}: {exc}"`
- Chained exceptions with `from exc` to preserve stack traces
- Specific exception catching: `except (URLError, HTTPError, KeyError, ValueError, InvalidOperation) as exc:`
- Graceful degradation: Functions like `build_dashboard_summary()` catch exceptions and return None for affected fields rather than failing completely
- Transaction rollback on error: `@transaction.atomic` ensures database consistency if sale record creation fails

**Examples:**
```python
class InsufficientLotsError(Exception):
    """Raised when there isn't enough remaining quantity across all lots to cover a sale."""
    pass

try:
    # operation
except FxRateFetchError as exc:
    raise forms.ValidationError(str(exc))

@transaction.atomic
def record_sale(...):
    # If remaining_to_allocate > 0, rollback entire transaction
    raise InsufficientLotsError(...)
```

## Logging

**Framework:** Django's built-in print/logging (no explicit logging library configured)

**Patterns:**
- No formal logging setup detected
- Error messages passed via form validation errors and exception messages
- User-facing messages via Django's messages framework (settings.py includes MESSAGE_TAGS for Bootstrap CSS classes)

**Example:**
```python
# In forms.py
raise forms.ValidationError('Enter a buy date first, or fill in FX rate manually.')

# In settings.py
MESSAGE_TAGS = {
    messages.ERROR: 'alert-danger',
}
```

## Comments

**When to Comment:**
- Docstrings on all classes and public functions (present on models, services, views)
- Inline comments for non-obvious logic or business rules
- Comments explaining FIFO algorithm and allocation strategy

**JSDoc/TSDoc:**
- Not used (Python project, not TypeScript/JavaScript)
- Triple-quoted docstrings used instead

**Examples:**
```python
class StockLot(models.Model):
    """
    One BUY transaction. Immutable once created — never edited after the fact.
    'Remaining quantity' is NEVER stored here; it's always calculated
    from qty minus whatever SaleAllocations have consumed it.
    """

def fetch_usd_thb_rate(rate_date):
    """
    Looks up the USD→THB rate for rate_date via the free, open-source,
    no-key-required Frankfurter API (ECB + central bank data).
    """
```

## Function Design

**Size:**
- Functions are generally focused and lean (typically 10-50 lines)
- Complex functions like `build_dashboard_summary()` are 60+ lines but broken into logical sections
- Private helper functions extract repeated patterns: `_fmt_qty()`, `_money()`, `_lot_table()`

**Parameters:**
- Keyword-only arguments enforced with `*` in function signature: 
  ```python
  def record_sale(*, owner, symbol, sell_date, qty_sold, ...):
  ```
  This forces callers to use explicit keyword arguments for clarity.
- Avoid positional arguments for clarity

**Return Values:**
- Functions return typed values: dictionaries (for reports), model instances, None
- Multiple values returned as dictionaries (not tuples): `{'rows': ..., 'allocation': ..., 'total_cost_thb': ...}`
- Graceful None returns for optional/failed operations: `current_value_thb = None` when price fetch fails

## Module Design

**Exports:**
- Each module has a clear responsibility:
  - `models.py`: ORM models (Symbol, StockLot, Sale, SaleAllocation)
  - `views.py`: HTTP request handlers (class-based views)
  - `services.py`: Business logic (record_sale, fetch rates, build reports)
  - `forms.py`: Form validation and input handling
  - `reports.py`: Report generation (CSV, PDF)
  - `admin.py`: Django admin interface registration

**Barrel Files:**
- No explicit barrel files (index.py exports); imports are direct and specific

**Examples:**
```python
# In views.py, import only what's needed from services
from .services import (
    record_sale, InsufficientLotsError, get_user_lots, get_user_sales,
    build_fifo_report, build_dashboard_summary,
)

# In services.py, import only what's needed
from .models import StockLot, Sale, SaleAllocation, Symbol
```

## Property Usage

**Computed Properties:**
- Models define calculated fields as properties: `qty_remaining`, `qty_allocated`, `cost_thb`, `proceeds_thb`, `capital_gain_thb`
- Properties re-computed on access (no caching) for data consistency
- Used in templates and reports for display

**Example:**
```python
@property
def qty_remaining(self):
    return self.qty - self.qty_allocated

@property
def capital_gain_thb(self):
    return self.proceeds_thb - self.total_cost_basis_thb
```

## Decimal Handling

**Precision Tracking:**
- All monetary values use `Decimal()` for precision, not float
- FX rates stored with 4 decimal places: `max_digits=10, decimal_places=4`
- Prices in USD with 6 decimal places: `max_digits=14, decimal_places=6`
- Share quantities with 8 decimal places: `max_digits=18, decimal_places=8`
- Conversion to Decimal from strings: `Decimal(str(value))` to avoid float precision issues

**Example:**
```python
return Decimal(str(payload['rates']['THB']))  # Convert from JSON string safely
```

## Request Handling

**AJAX Detection:**
```python
def is_ajax(request):
    return request.headers.get('X-Requested-With') == 'XMLHttpRequest'
```

**Response Types:**
- Standard responses: `redirect()`, HTML templates
- AJAX responses: `JsonResponse({'success': True/False, 'html': ...})`
- File downloads: `HttpResponse()` with appropriate content-type and Content-Disposition header

---

*Convention analysis: 2026-07-19*
