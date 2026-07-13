# Stock FIFO Tracker

A Django web app for tracking personal stock trades using **First-In-First-Out (FIFO)** cost-basis accounting, with dual-currency (USD/THB) support. Every buy is recorded as an immutable lot; every sell is automatically matched against the oldest remaining lots first, so cost basis and realized capital gain are always calculated the way tax authorities expect — no manual spreadsheet matching required.

## Features

- **FIFO-accurate sell matching** — recording a sell atomically walks your open lots oldest-first and allocates quantity across as many lots as needed, raising a clear error if you try to sell more than you actually hold.
- **Dual-currency accounting** — every buy and sell carries its own USD price and USD→THB FX rate, so cost basis, proceeds, and capital gain are all computed in THB at the rate that applied on that specific transaction date.
- **Lot & sale history views** — browse current holdings (with per-lot remaining quantity) and full sell history (with per-sale capital gain), filterable by ticker.
- **Record Buy / Record Sell modals** — buy and sell forms open in a Bootstrap modal directly from the list pages and submit via AJAX; validation errors reappear inside the modal instead of bouncing you to a new page.
- **Evidence uploads** — attach a screenshot/receipt image to any buy or sell as a paper trail.
- **FIFO Portfolio Report export** — a formal, per-ticker report available as:
  - **PDF** — one page per ticker (open lots, sales with their FIFO lot allocations shown as sub-rows, ticker totals), plus a portfolio summary page. Gains are shown in green, losses in red.
  - **CSV** — a flat, Excel-friendly ledger (`BUY LOT` / `SALE` / `-> ALLOCATION` rows, full Decimal precision) for further analysis.
- **Per-user data isolation** — every lot and sale is scoped to its owner; nothing is visible across accounts.

## How FIFO allocation works

A **Sale** is never linked to a single lot — it can draw from several. When you record a sell:

1. Your `StockLot`s for that ticker are locked and read oldest-first (`buy_date`, then `created_at`).
2. The requested quantity is taken from the oldest lot with quantity remaining, then the next, and so on, until the full sale quantity is covered.
3. A `SaleAllocation` row is created for each lot touched, recording exactly how many shares and how much THB cost basis came from that lot.
4. If total remaining quantity across all lots can't cover the sale, the whole transaction rolls back and you get an error instead of a partial/incorrect sale.

This means a lot's `qty_remaining` is never stored directly — it's always `qty - sum(allocations)`, so it can't drift out of sync with reality.

## Data model

```
Symbol          — a ticker (e.g. NVDA), shared across users
StockLot        — one BUY: symbol, buy_date, price_usd, qty, fx_rate_usd_thb, evidence
Sale            — one SELL: symbol, sell_date, qty_sold, sale_price_usd, fee_usd, fx_rate_usd_thb, evidence
SaleAllocation  — the FIFO link: which Sale drew how much qty (and cost basis) from which StockLot
```

`StockLot` and `Sale` are immutable once created — corrections are made by recording offsetting transactions, not by editing history, which keeps the FIFO ledger trustworthy.

## Tech stack

- **Backend:** Django 6, SQLite
- **Frontend:** Django templates + Bootstrap 5 (CDN), vanilla JS for AJAX modal forms
- **Reports:** [ReportLab](https://www.reportlab.com/) for PDF generation, stdlib `csv` for CSV export
- **Auth:** Django's built-in authentication (login required on every view)

## Getting started

```bash
# 1. Clone and enter the project
git clone https://github.com/thestreets1412/stock-fifo-django.git
cd stock-fifo-django

# 2. Create and activate a virtual environment
python -m venv .venv
.venv\Scripts\activate        # Windows
source .venv/bin/activate     # macOS/Linux

# 3. Install dependencies
pip install -r requirments.txt

# 4. Configure environment variables
# Create a .env file in the project root:
#   SECRET_KEY=your-secret-key
#   DEBUG=True

# 5. Set up the database and an account
python manage.py migrate
python manage.py createsuperuser

# 6. Run the dev server
python manage.py runserver
```

Then sign in and start recording buys and sells from the **Lots** and **Sell History** pages.

## Project structure

```
config/                    Django project settings, root URLs
portfolio/
  models.py                 Symbol, StockLot, Sale, SaleAllocation
  services.py                FIFO allocation logic (record_sale) and query helpers
  reports.py                  CSV / PDF FIFO report generation
  forms.py                     Buy/sell/login forms
  views.py                      List, create, evidence, and report views
  templates/portfolio/          Lot list, sale list, buy/sell forms, evidence pages
  static/portfolio/             Bootstrap overrides, AJAX modal-form JS
```
