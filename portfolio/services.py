import json
from decimal import Decimal, InvalidOperation
from urllib.error import URLError, HTTPError
from urllib.request import Request, urlopen

from django.db import transaction
from django.db.models import Q

from .models import StockLot, Sale, SaleAllocation, Symbol


class InsufficientLotsError(Exception):
    """Raised when there isn't enough remaining quantity across all lots to cover a sale."""
    pass


class FxRateFetchError(Exception):
    """Raised when the USD→THB rate can't be auto-fetched for a given date."""
    pass


def fetch_usd_thb_rate(rate_date):
    """
    Looks up the USD→THB rate for rate_date via the free, open-source,
    no-key-required Frankfurter API (ECB + central bank data).
    """
    url = f'https://api.frankfurter.app/{rate_date.isoformat()}?from=USD&to=THB'
    request = Request(url, headers={'User-Agent': 'stock-fifo-web-app/1.0'})
    try:
        with urlopen(request, timeout=5) as response:
            payload = json.load(response)
        return Decimal(str(payload['rates']['THB']))
    except (URLError, HTTPError, KeyError, ValueError, InvalidOperation) as exc:
        raise FxRateFetchError(f'Could not fetch USD/THB rate for {rate_date}: {exc}') from exc


def get_user_lots(owner, symbol_id=None):
    queryset = StockLot.objects.filter(owner=owner).select_related('symbol')
    if symbol_id:
        queryset = queryset.filter(symbol_id=symbol_id)
    return queryset


def get_user_sales(owner, symbol_id=None):
    queryset = (
        Sale.objects
        .filter(owner=owner)
        .select_related('symbol')
        .prefetch_related('allocations__lot')
    )
    if symbol_id:
        queryset = queryset.filter(symbol_id=symbol_id)
    return queryset


def build_fifo_report(owner, symbol_id=None):
    """
    Groups every buy lot and sell allocation by ticker, in FIFO order, so a
    report can show — per symbol — which lots are still open, which are
    exhausted, and exactly which lots fed each sale.
    """
    symbols = (
        Symbol.objects
        .filter(Q(lots__owner=owner) | Q(sales__owner=owner))
        .distinct()
        .order_by('ticker')
    )
    if symbol_id:
        symbols = symbols.filter(pk=symbol_id)

    sections = []
    for symbol in symbols:
        lots = list(get_user_lots(owner, symbol.pk))  # Meta ordering = FIFO order
        sales = sorted(get_user_sales(owner, symbol.pk), key=lambda sale: (sale.sell_date, sale.created_at))
        for sale in sales:
            sale.allocations_sorted = sorted(sale.allocations.all(), key=lambda alloc: alloc.lot.buy_date)

        total_bought_qty = sum((lot.qty for lot in lots), Decimal('0'))
        remaining_qty = sum((lot.qty_remaining for lot in lots), Decimal('0'))
        remaining_cost_thb = sum(
            (lot.qty_remaining * lot.price_usd * lot.fx_rate_usd_thb for lot in lots), Decimal('0')
        )
        total_sold_qty = sum((sale.qty_sold for sale in sales), Decimal('0'))
        realized_gain_thb = sum((sale.capital_gain_thb for sale in sales), Decimal('0'))

        sections.append({
            'symbol': symbol,
            'lots': lots,
            'sales': sales,
            'total_bought_qty': total_bought_qty,
            'total_sold_qty': total_sold_qty,
            'remaining_qty': remaining_qty,
            'remaining_cost_thb': remaining_cost_thb,
            'realized_gain_thb': realized_gain_thb,
        })
    return sections


@transaction.atomic
def record_sale(*, owner, symbol, sell_date, qty_sold, 
                sale_price_usd, fee_usd, fx_rate_usd_thb, 
                evidence=None):
    """
    Creates a Sale and allocates it against StockLots oldest-first (FIFO).
    Returns the created Sale instance.
    """
    qty_sold = Decimal(qty_sold)

    # Lock the candidate lots for this symbol/owner so two simultaneous
    # sales can't both read the same "remaining" qty and double-spend it.
    lots = (
        StockLot.objects
        .select_for_update()
        .filter(owner=owner, symbol=symbol)
        .order_by('buy_date', 'created_at')  # oldest first = FIFO
    )

    # Create the Sale record first — allocations will reference it.
    sale = Sale.objects.create(
        owner=owner,
        symbol=symbol,
        sell_date=sell_date,
        qty_sold=qty_sold,
        sale_price_usd=sale_price_usd,
        fee_usd=fee_usd,
        fx_rate_usd_thb=fx_rate_usd_thb,
        evidence = evidence,
    )

    remaining_to_allocate = qty_sold
    allocations_to_create = []

    for lot in lots:
        if remaining_to_allocate <= 0:
            break

        available = lot.qty_remaining  # computed property: qty - already allocated
        if available <= 0:
            continue  # this lot is already fully consumed, skip it

        take = min(available, remaining_to_allocate)

        allocations_to_create.append(
            SaleAllocation(
                sale=sale,
                lot=lot,
                qty_allocated=take,
                cost_basis_thb=take * lot.price_usd * lot.fx_rate_usd_thb,
            )
        )
        remaining_to_allocate -= take

    if remaining_to_allocate > 0:
        # Not enough total remaining quantity across all lots to cover this sale.
        # Raising here triggers Django's @transaction.atomic to roll back
        # everything above — the Sale we just created gets undone too.
        raise InsufficientLotsError(
            f"Tried to sell {qty_sold} of {symbol}, but only "
            f"{qty_sold - remaining_to_allocate} is available across all lots."
        )

    SaleAllocation.objects.bulk_create(allocations_to_create)
    return sale