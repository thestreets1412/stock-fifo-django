# Testing Patterns

**Analysis Date:** 2026-07-19

## Test Framework

**Runner:**
- Django's built-in test framework (based on Python's unittest)
- Run command: `python manage.py test`
- Run specific test: `python manage.py test portfolio.tests.BuildDashboardSummaryTests`
- Verbosity: `python manage.py test -v 2`

**Assertion Library:**
- Python's built-in `unittest` assertions: `assertEqual()`, `assertIsNone()`, `assertTrue()`, etc.
- No external testing library (pytest, nose) configured

**Run Commands:**
```bash
# Run all tests
python manage.py test

# Run specific app tests
python manage.py test portfolio

# Run specific test class
python manage.py test portfolio.tests.BuildDashboardSummaryTests

# Run with verbosity
python manage.py test -v 2

# Run with coverage (requires coverage package)
# coverage run --source='.' manage.py test
# coverage report
```

## Test File Organization

**Location:**
- Co-located with app source: `portfolio/tests.py`
- Not in separate `tests/` directory; follows Django app convention

**Naming:**
- Test file: `tests.py` (not `test_*.py` or `*_test.py`)
- Test classes: `PascalCase` ending with "Tests" (e.g., `BuildDashboardSummaryTests`)
- Test methods: `test_*` prefix using snake_case and descriptive names

**Structure:**
```
portfolio/
├── models.py
├── views.py
├── services.py
├── forms.py
├── tests.py          # All tests here
└── ...
```

## Test Structure

**Suite Organization:**
- One test class per major function/feature being tested
- Within test class, multiple test methods for different scenarios

**Example:**
```python
class BuildDashboardSummaryTests(TestCase):
    def setUp(self):
        # Shared test data
        self.owner = User.objects.create_user(username='trader', password='pw')
        self.aapl = Symbol.objects.create(ticker='AAPL')
        self.tsla = Symbol.objects.create(ticker='TSLA')
    
    def test_no_lots_returns_zeroed_summary(self):
        # Test case 1
        ...
    
    def test_computes_live_value_and_unrealized_gain(self):
        # Test case 2
        ...
```

**Patterns:**

1. **Setup pattern:**
   - Override `setUp()` method to create test fixtures
   - Called before each test method runs
   - Create necessary database objects (users, symbols, stock lots)

2. **Teardown pattern:**
   - Django's TestCase automatically rolls back database after each test
   - No explicit `tearDown()` method needed for database cleanup
   - Inheriting from `TestCase` (not `SimpleTestCase`) ensures transaction rollback

3. **Assertion pattern:**
   - Explicit assertions: `self.assertEqual(actual, expected)`
   - None checks: `self.assertIsNone(value)`
   - Type/existence checks: `self.assertIn()`, `self.assertTrue()`

## Mocking

**Framework:** `unittest.mock` (Python standard library)

**Patterns:**
- Use `@patch()` decorator to mock external dependencies
- Mock external API calls to avoid network dependency in tests

**Example:**
```python
@patch('portfolio.services.fetch_current_price')
@patch('portfolio.services.fetch_usd_thb_rate')
def test_computes_live_value_and_unrealized_gain(self, mock_fx, mock_price):
    mock_fx.return_value = Decimal('35')
    mock_price.return_value = Decimal('150')
    
    # Test code using mocked functions
    summary = build_dashboard_summary(self.owner)
    self.assertEqual(summary['total_value_thb'], Decimal('52500'))
```

**What to Mock:**
- External API calls: `fetch_usd_thb_rate()` (Frankfurter API)
- Third-party library calls: `fetch_current_price()` (yfinance)
- Network operations that could be slow or flaky

**What NOT to Mock:**
- Database models and queries (use in-memory SQLite test database instead)
- Internal service functions (test them directly)
- View and form logic (test with real ORM objects)

**Side Effects:**
- Set `.side_effect` to raise exceptions for error testing:
  ```python
  mock_price.side_effect = PriceFetchError('boom')
  ```
- Test graceful degradation when external services fail

## Fixtures and Factories

**Test Data:**
- Create test data directly in `setUp()` using model constructors
- No factory library (factory_boy) detected

**Example:**
```python
def setUp(self):
    self.owner = User.objects.create_user(username='trader', password='pw')
    self.aapl = Symbol.objects.create(ticker='AAPL')
    
    StockLot.objects.create(
        owner=self.owner, symbol=self.aapl, buy_date='2026-01-01',
        price_usd=Decimal('100'), qty=Decimal('10'), fx_rate_usd_thb=Decimal('33'),
    )
```

**Location:**
- Test data creation inside `setUp()` method within test class
- No separate fixtures directory or fixture files
- Data scoped to single test class

## Coverage

**Requirements:** None enforced (no coverage configuration detected)

**View Coverage:**
```bash
# Install coverage tool
pip install coverage

# Run tests with coverage
coverage run --source='.' manage.py test

# View report
coverage report
coverage html
```

## Test Types

**Unit Tests:**
- Scope: Individual functions/methods in isolation
- Approach: Mock external dependencies, test logic directly
- Example: `test_computes_live_value_and_unrealized_gain` tests `build_dashboard_summary()` with mocked price/FX data
- Located in: `portfolio/tests.py`

**Integration Tests:**
- Scope: Multiple components working together with real database
- Approach: Use Django's TestCase (which wraps database in transactions)
- Example: `test_no_lots_returns_zeroed_summary` exercises the full dashboard build process
- Database: Uses SQLite in-memory test database by default

**E2E Tests:**
- Framework: Not implemented (no Selenium, Playwright, or similar detected)
- Testing user flows end-to-end through the UI would require additional setup

## Common Patterns

**Async Testing:**
- Not used (synchronous Django views, no async/await)

**Error Testing:**
```python
@patch('portfolio.services.fetch_current_price')
@patch('portfolio.services.fetch_usd_thb_rate')
def test_price_fetch_failure_degrades_gracefully(self, mock_fx, mock_price):
    mock_fx.return_value = Decimal('35')
    mock_price.side_effect = PriceFetchError('boom')  # Simulate failure
    
    # Test that dashboard still works, just missing live price data
    summary = build_dashboard_summary(self.owner)
    row = summary['rows'][0]
    self.assertIsNone(row['current_value_thb'])
    self.assertIsNone(row['unrealized_gain_thb'])
```

**Database Queries:**
- Tests run with SQLite in-memory database
- Models use standard Django ORM queries
- `select_related()` and `prefetch_related()` patterns tested in queries for performance
- Database state isolated per test (transaction rollback after each test)

**Decimal Precision:**
- Test calculations use `Decimal()` for exact comparison
- Example: `self.assertEqual(row['cost_thb'], Decimal('33000'))`

## Database Testing

**Test Database:**
- SQLite in-memory database (created fresh for each test run)
- Configured via `DATABASES['default']` in `config/settings.py`
- Full Django schema applied (migrations run automatically)

**Transaction Behavior:**
- Each test runs in a transaction that's rolled back afterward
- Inheritance from `TestCase` ensures database isolation
- No need for explicit cleanup in `tearDown()`

**Example Test Flow:**
1. `setUp()` creates test user and symbols
2. Test method runs with clean database state
3. After test completes, transaction rolls back
4. Next test starts with fresh state

## Best Practices Observed

1. **Descriptive test names:** `test_price_fetch_failure_degrades_gracefully` clearly states what's being tested
2. **Focused tests:** Each test method tests one scenario/behavior
3. **Mock external APIs:** Network calls mocked to keep tests fast and deterministic
4. **Test real business logic:** Internal service functions tested with real (in-memory) database
5. **Graceful degradation testing:** Tests verify system behaves well when external services fail

---

*Testing analysis: 2026-07-19*
