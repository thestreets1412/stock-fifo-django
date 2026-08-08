# Stock FIFO Tracker

A Django web app for tracking personal stock trades using **First-In-First-Out (FIFO)** cost-basis accounting, with dual-currency (USD/THB) support. Every buy is recorded as an immutable lot; every sell is automatically matched against the oldest remaining lots first, so cost basis and realized capital gain are always calculated the way tax authorities expect — no manual spreadsheet matching required.

## Features

- **Portfolio dashboard home page** — stat cards (total value, cost basis, unrealized/realized gain-loss), a per-symbol holdings table, and a Chart.js allocation pie, backed by live market prices (via `yfinance`) layered on top of your FIFO cost basis. Price lookups are bounded to a 5s timeout in a worker thread and degrade gracefully per-symbol (shows "—") instead of hanging or erroring if a ticker can't be priced. The existing buy-lot table, ticker filter, and Record Buy modal stay embedded below, unchanged.
- **FIFO-accurate sell matching** — recording a sell atomically walks your open lots oldest-first and allocates quantity across as many lots as needed, raising a clear error if you try to sell more than you actually hold.
- **Dual-currency accounting** — every buy and sell carries its own USD price and USD→THB FX rate, so cost basis, proceeds, and capital gain are all computed in THB at the rate that applied on that specific transaction date.
- **Lot & sale history views** — browse current holdings (with per-lot remaining quantity) and full sell history (with per-sale capital gain), filterable by ticker and by an optional buy/sell date range (`From` / `To`). When a date range is set, remaining quantity, cost basis, and capital gain all recompute from only the allocations inside that window — including on the dashboard cards — so the numbers on screen stay internally consistent with whatever's visible.
- **Record Buy / Record Sell modals** — buy and sell forms open in a Bootstrap modal directly from the list pages and submit via AJAX; validation errors reappear inside the modal instead of bouncing you to a new page.
- **Evidence uploads** — attach a screenshot/receipt image to any buy or sell as a paper trail.
- **FIFO Portfolio Report export** — a formal, per-ticker report available as:
  - **PDF** — brokerage/bank-statement styled: a cover page (owner name, generation date, ticker filter note, portfolio totals), then one page per ticker (open lots, sales with their FIFO lot allocations shown as sub-rows, ticker totals) with horizontal-rule-only tables and `THB`-prefixed values, plus a portfolio summary page. Gains are shown in green, losses in red.
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
- **Frontend:** Django templates + Bootstrap 5 (CDN), Chart.js (CDN) for the allocation pie, vanilla JS for AJAX modal forms
- **Live pricing:** [`yfinance`](https://pypi.org/project/yfinance/) for current market prices on the dashboard
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
pip install -r requirements.txt

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

Then sign in — you'll land on the portfolio dashboard, with the buy-lot table (filterable by ticker, plus the Record Buy modal) below it and **Sell History** in the nav.

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
scripts/
  backup.sh                   Nightly snapshot + USB mirror, runs on the Pi
  pull-pi-backup.ps1          Pulls those snapshots to the laptop
```

## Backups

The ledger is a single SQLite file, so it is kept in three places. `scripts/backup.sh`
on the Pi is the only thing that creates backups; every other copy is a mirror of what
it produced.

| Copy | Location | Created by | Kept |
|---|---|---|---|
| 1 | `/home/minotaur/backups` (Pi SD card) | `stock-fifo-backup.timer`, nightly 20:00 | 14 days |
| 2 | `/mnt/backup/stock-fifo` (USB drive on the Pi) | same script, same run | 60 days |
| 3 | `D:\Backups\stock-fifo` (laptop) | Task Scheduler `StockFifo-BackupPull`, daily 20:00 | 60 days |

Filenames are `db_YYYY-MM-DD_HHMMSS.sqlite3` and `media_YYYY-MM-DD_HHMMSS.tar.gz`.

**Snapshots use `sqlite3 ".backup"`, never `cp`.** A plain copy of a database with an
active writer produces a silently corrupt file. Every snapshot is checked with
`PRAGMA integrity_check` and discarded if it fails.

The USB mirror is guarded by `mountpoint -q`. If the drive is absent the script logs a
warning and skips it rather than writing to `/mnt/backup` on the SD card — which would
fill the very disk the backups exist to survive. `/etc/fstab` uses `nofail` so a
missing or failed drive cannot stop the Pi from booting.

The laptop pull tries two SSH aliases in order (`pi-stockfifo` via mDNS, then
`pi-stockfifo-ip`). Neither route is reliable alone: mDNS breaks on mobile hotspots
that limit multicast, and the raw IP breaks on DHCP lease changes. If both fail the
script exits 0 — a laptop away from home is normal, not a failure.

### Checking that it still works

```bash
systemctl list-timers stock-fifo-backup.timer          # on the Pi
journalctl -u stock-fifo-backup.service -n 20          # on the Pi
```

```powershell
Get-Content D:\Backups\stock-fifo-pull.log -Tail 5     # on the laptop
```

### Restore procedure

```powershell
$newest = Get-ChildItem D:\Backups\stock-fifo -Filter "db_*.sqlite3" |
          Sort-Object LastWriteTime -Descending | Select-Object -First 1
New-Item -ItemType Directory -Force -Path D:\restore-test | Out-Null
Copy-Item $newest.FullName D:\restore-test\db.sqlite3
```

Verify before trusting it, then compare the counts against the live database:

```powershell
.venv\Scripts\python.exe -c "import sqlite3; c=sqlite3.connect(r'D:\restore-test\db.sqlite3'); print(c.execute('PRAGMA integrity_check').fetchone()[0]); print([c.execute(f'SELECT COUNT(*) FROM {t}').fetchone()[0] for t in ('portfolio_stocklot','portfolio_sale','portfolio_saleallocation')])"
```

```bash
sqlite3 ~/stock-fifo-django/db.sqlite3 "SELECT COUNT(*) FROM portfolio_stocklot; SELECT COUNT(*) FROM portfolio_sale; SELECT COUNT(*) FROM portfolio_saleallocation;"
```

Evidence images restore by extracting the matching archive over the project root:

```bash
tar -xzf media_YYYY-MM-DD_HHMMSS.tar.gz -C ~/stock-fifo-django
```

**Drill last passed: 2026-07-26** — restored the laptop copy of
`db_2026-07-25_233128.sqlite3`, integrity `ok`, counts 28 lots / 21 sales /
38 allocations matching the live database exactly, media archive holding 8 evidence
images. An untested backup is an assumption; rerun this drill after any change to the
backup scripts.

### Known gaps

- **No off-site copy.** Copies 1 and 2 sit in the same room and copy 3 travels with the
  laptop. A fire while the laptop is home destroys all three. Closing this needs an
  encrypted cloud upload.
- **No failure alert.** A broken backup announces itself only in `journalctl` and the
  pull log. Check them occasionally.
- **Backups are unencrypted.** Fine while every copy is on hardware you physically
  control; not fine the moment one goes to a cloud provider.

## Public access

The app is reachable from anywhere at **https://fifo-by-minotaur.uk**, through a
Cloudflare Tunnel. No router port is forwarded and the home IP is never in DNS —
`cloudflared` on the Pi dials out to Cloudflare's edge and traffic returns down
that connection.

- **Identity gate:** Cloudflare Access sits in front of the whole hostname. An
  unauthenticated request never reaches Django; it gets a one-time PIN prompt.
  Only the owner's email address is on the allow policy. Session lasts 24 hours.
- **Origin:** Gunicorn binds `127.0.0.1:8000` only. `cloudflared` is its sole
  possible client, which is what makes trusting the `X-Forwarded-Proto` header
  safe — Django learns the request was HTTPS from a header only a local process
  can set.
- **Ingress config:** `deploy/cloudflared/config.yml.example`, copied to
  `/etc/cloudflared/config.yml` on the Pi. Version-controlled for the same
  reason the Samba share is — the device is never the source of truth.
- **The NAS share is not exposed.** Ingress has exactly one hostname rule and a
  catch-all 404. SMB stays on the LAN.

### LAN access no longer works

`SESSION_COOKIE_SECURE`, `CSRF_COOKIE_SECURE` and `SECURE_SSL_REDIRECT` are all
active whenever `DEBUG=False`, so `http://<pi-ip>:8000` redirects to HTTPS and
the browser refuses to send session cookies over plain HTTP. This is deliberate.
Use the domain — it works on the home WiFi exactly as it does anywhere else.

### Known gaps

- **`/media/` has no authentication check of its own.** Cloudflare Access is
  what protects the evidence photos, not Django. See
  `.planning/todos/pending/unauthenticated-media-endpoint.md`.
- **The tunnel is a single point of failure.** If Cloudflare Access or the free
  tunnel tier has an outage, there is no LAN fallback by design.

## Home NAS share

The USB drive attached to the Pi doubles as a LAN file share for moving documents
between the household laptops, so files no longer travel by flash drive.

- **Address:** `\\stockfifo.local\nas` (falls back to `\\<pi-ip>\nas` if mDNS doesn't
  resolve on a given machine — see Known gaps below), mapped to `Z:` on both laptops
- **Account:** `nasuser` — a Samba-only account, unrelated to the Pi's Linux login
- **On disk:** `/mnt/backup/nas`, a sibling of the backup folder `/mnt/backup/stock-fifo`
  on the same exFAT drive
- **Config:** `deploy/samba/nas-share.conf`, pulled to the Pi by `git pull` and wired in
  by an `include =` line in `/etc/samba/smb.conf`, so the share definition is
  version-controlled instead of hand-edited on the Pi

### What the share deliberately does not expose

The drive is exFAT, which stores no Unix permissions, so Samba's `path =` directive is
the only thing separating the share from the FIFO ledger backups on the same filesystem.
A few rules keep that wall intact:

- No share ever points at `/mnt/backup` — only at `/mnt/backup/nas`. Verified: browsing
  `\\stockfifo.local\stock-fifo` and `\\stockfifo.local\minotaur` both fail with "network
  name cannot be found," and the server root lists only `nas`.
- `[homes]` is disabled. The Debian package shipped it enabled by default on this
  install — it would have exposed the live `db.sqlite3` and the 14-day snapshot folder
  under `/home/minotaur` (read-only, but reachable by any authenticated user). Disabled
  by replacing the whole `smb.conf` global section rather than trying to comment out one
  block.
- `smbd` binds only to `127.0.0.1` and the Pi's LAN address, listed as explicit IPs
  rather than the interface name `wlan0`. Naming the interface also bound Samba to its
  IPv6 global address, which on a network where the ISP hands out routable IPv6 (no
  NAT, unlike IPv4) would have put port 445 within reach of the open internet — a known
  ransomware vector. `hosts allow` is scoped to the home subnet regardless.
- The share is never routed through the Cloudflare Tunnel. LAN only.

### Recycle bin

Deletions over SMB are diverted into `.recycle` inside the share instead of being
destroyed outright — Explorer offers no undo over a network share.
`/etc/tmpfiles.d/nas-recycle.conf` empties anything older than 30 days via the default
`systemd-tmpfiles-clean.timer`.

### If the drive is unplugged

Verified by physically removing the drive: Samba refuses the share because its path no
longer exists, and the nightly backup logs `WARN: /mnt/backup is not mounted, USB mirror
skipped`. Neither writes to the SD card — `/mnt/backup` reverts to an empty directory
owned by `root`, and free space on the SD card is unchanged. The web app keeps running
because the fstab entry carries `nofail`.

### Known gaps

- **mDNS (`.local`) resolution is unreliable across clients.** It worked from one
  Windows 10 laptop and failed on a Windows 11 laptop with `DNS name does not exist`,
  while the plain IP address worked on both. Likely cause: Windows suppresses multicast
  discovery when a network connection is categorized `Public` instead of `Private`.
  Unresolved — using the IP address is a reliable fallback in the meantime.
