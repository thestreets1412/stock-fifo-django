from decimal import Decimal
from django.db import transaction

from .models import StockLot, Sale, SaleAllocation


class InsufficientLotsError(Exception):
    """Raised when there isn't enough remaining quantity across all lots to cover a sale."""
    pass


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