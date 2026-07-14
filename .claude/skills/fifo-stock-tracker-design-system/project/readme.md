# FIFO Stock Tracker — Design System

## Sources

This design system is derived entirely from one codebase:

- **GitHub:** [thestreets1412/stock-fifo-django](https://github.com/thestreets1412/stock-fifo-django)

Explore that repository further for the full picture — models (`portfolio/models.py`), FIFO allocation logic (`portfolio/services.py`), PDF/CSV report generation (`portfolio/reports.py`), and the Django templates (`portfolio/templates/portfolio/`) that this system's tokens and components were read from.

No Figma file, slide deck, or additional brand asset was provided. If you have one, attach it and this system can be extended.

## Product context

**Stock FIFO Tracker** is a personal-use Django web app for tracking stock trades with First-In-First-Out (FIFO) cost-basis accounting, in dual-currency (USD/THB). It has one surface: a small internal tool, not a public-facing product.

- **Users record buys** as immutable "lots" (ticker, date, USD price, quantity, USD→THB FX rate, optional evidence photo).
- **Users record sells**, and the app automatically walks open lots oldest-first, allocating the sale across as many lots as needed, computing realized capital gain in THB.
- **Two list views** — Stock Lots (open positions) and Sell History (realized sales, with per-sale FIFO lot breakdown).
- **A FIFO Portfolio Report** exports as PDF (formal, one page per ticker, ReportLab) or CSV (flat ledger).
- Built on **Django 6 + Bootstrap 5** (via CDN) — no design tooling, no custom component library, no logo.

There is exactly one product/surface here (no separate marketing site, mobile app, etc.), so this system contains one UI kit.

## Components

Core: `Button`, `Card` / `CardBody` / `CardTitle`, `Table` / `TableRow` / `TableCell`.
Forms: `FormField`, `TextInput`, `Select`, `FileInput`.
Feedback: `Alert`, `GainLossBadge`.
Navigation: `Navbar`, `Modal`, `Dropdown`.

These are not an invented "standard component set" — they are exactly the Bootstrap-based primitives the source templates use (navbar, striped/hover tables, bordered cards, Bootstrap modals, dropdown menus, dismissible alerts, standard form controls) plus one custom piece: `GainLossBadge`, which formalizes the green/red capital-gain text pattern from `sale_list.html` and the PDF report's `GAIN_COLOR`/`LOSS_COLOR`.

### Intentional additions
- **`GainLossBadge`** — the source repeats "green if ≥0, red if negative" inline in two places (template + PDF generator) without a named component; promoted here so it's used consistently everywhere a capital gain/loss number appears.

No Checkbox/Radio/Switch/Tabs/Toast/Tooltip/Badge exist — the source app never uses them, so they were not invented.

## Index

- `styles.css` — root stylesheet, imports all tokens.
- `tokens/` — `colors.css`, `typography.css`, `spacing.css`.
- `components/core/` — Button, Card, Table.
- `components/forms/` — FormField, TextInput, Select, FileInput.
- `components/feedback/` — Alert, GainLossBadge.
- `components/navigation/` — Navbar, Modal, Dropdown.
- `guidelines/` — foundation specimen cards (colors, type, spacing, brand/iconography).
- `ui_kits/fifo-tracker/` — `App.jsx` + `index.html`, an interactive recreation of the Lots / Sell History screens with working Record Buy / Record Sell modals and live FIFO allocation.
- `SKILL.md` — Claude Code–compatible skill file for using this system outside this environment.

## Content fundamentals

The app has almost no marketing copy — it's a utility tool, and its "voice" is entirely in labels, button text, and error messages.

- **Voice:** imperative and terse. Buttons say what they do: "Record Buy", "Record Sell", "Sell (FIFO)", "Save", "View", "Download CSV", "Download PDF". No "Get Started", no marketing verbs.
- **Address:** second person only in the navbar greeting — "Hi, {{ user.username }}" — otherwise content is impersonal (field labels, table headers). No first-person ("I"/"we") anywhere.
- **Casing:** Title Case for headings and button labels ("Stock Lots", "Sell History", "Record a Buy"); sentence case for form labels and help text; ALL CAPS never used except CSV section markers (`=== TICKER: NVDA ===`) which are a machine-readable convention, not a voice choice.
- **Errors are literal, not soft:** the one hand-written user-facing error string is *"Cannot sell more shares than you hold"* (paraphrased from `InsufficientLotsError`) — direct cause-and-effect, no apology, no hedging.
- **Numbers over prose:** the report and tables prefer a number with a precise unit ("Cost (THB)", "FX Rate", "Qty Remaining") over descriptive text. Financial precision (THB monetary values quantized to 2dp, share quantities to 8dp) matters more than tone.
- **No emoji, no exclamation points, no humor.** This is a ledger, and it reads like one.

## Visual foundations

- **Colors:** Bootstrap 5 defaults, unmodified — blue `#0d6efd` for the one primary action per screen, dark `#212529` navbar, gray-scale borders/text. The only bespoke color decision in the whole app is the gain/loss pair (`#1e7e34` green / `#c0392b` red) and a slate report-header color (`#2c3e50`), both defined once in `reports.py` and otherwise absent from the UI. Read as: **functional, not expressive** — color exists to mark state (success/danger/gain/loss), never for decoration.
- **Type:** system sans-serif only, one weight change (600 for the navbar wordmark), one size scale (Bootstrap's default h1–h6 + body + small). No display face, no serif, no letter-spacing tricks.
- **Spacing:** Bootstrap's 0.25rem-step spacer scale used directly via utility classes (`mb-3`, `mb-4`, `py-3`, `gap-2`) — nothing custom.
- **Backgrounds:** flat white page background throughout. No images, no gradients, no illustrations, no patterns/textures — none exist anywhere in the source.
- **Animation:** none beyond Bootstrap's built-in modal fade and alert `fade show` transitions (CSS opacity fade, default Bootstrap timing ~150ms). No custom easing, no bounce, no page transitions.
- **Hover / press states:** entirely Bootstrap defaults — buttons darken ~1 shade on hover, table rows get a faint darker tint (`table-hover`), links have no underline until hover. No custom press/active treatment (no scale/shrink).
- **Borders & shadows:** 1px solid gray borders on cards, inputs, tables. Cards carry **no shadow** — flat and bordered only. The only elevation in the whole app is the default Bootstrap modal drop-shadow and dropdown-menu shadow.
- **Corner radii:** Bootstrap default — 0.375rem on buttons/inputs/dropdowns, 0.5rem on cards/modals. Nothing sharp, nothing very round; no pill shapes appear in the actual UI (badges/pills aren't used).
- **Transparency / blur:** only the semi-transparent modal backdrop (Bootstrap default `rgba(0,0,0,.5)`, no blur).
- **Imagery:** none native to the app's chrome. User-uploaded "evidence" images (buy/sell receipts) are the only imagery, shown plainly in a bordered card with `img-fluid` — no filters, no treatment.
- **Layout:** conventional top navbar + centered `container` (Bootstrap's max-width breakpoints) + footer. No fixed/sticky elements, no sidebars, no off-canvas nav.
- **Density:** table-first, data-dense — this is a ledger app, and rows/columns are the primary UI, not cards or lists.

## Iconography

- The source app itself defines **no icon system** — the only `<svg class="bi">` markup in `base.html` (`#bootstrap`, `#instagram`, `#facebook` sprite refs) is leftover boilerplate from Bootstrap's own starter template footer, not real, wired-up icons (no `<symbol>` defs exist anywhere in the repo, so those `<use>` tags render blank in practice).
- No emoji, no unicode glyphs used as icons, no PNG icon assets exist in the codebase.
- **Substitution:** this system links **Bootstrap Icons** from CDN (`bootstrap-icons@1.11.3`) as the closest-fitting set — same design language as the Bootstrap 5 CSS the app already depends on, same stroke/fill weight. See the "Iconography" card in the Brand group for the substitute glyphs mapped to this app's concepts (cash/lot, gain graph, receipt/evidence, PDF/CSV export, logout).
- If real product icons exist outside this repo, replace the CDN link with real assets and update this section.

## Caveats

- No logo or brand mark exists anywhere in the source — wordmark is rendered as plain semibold text, matching `.navbar-brand`. Do not invent a logo for this brand.
- No custom webfont exists — the source declares only `font-family: sans-serif`. This system uses the OS system-font stack as the faithful equivalent; no Google Fonts substitution was needed or made.
- Iconography is a substitution — see ICONOGRAPHY below.
