from django.contrib import admin
from .models import Symbol, StockLot, Sale, SaleAllocation

@admin.register(Symbol)
class SymbolAdmin(admin.ModelAdmin):
    list_display = ['ticker', 'name']
    search_fields = ['ticker', 'name']


class SaleAllocationInline(admin.TabularInline):
    model = SaleAllocation
    extra = 0
    readonly_fields = ['lot', 'qty_allocated', 'cost_basis_thb']  # allocations shouldn't be hand-edited

@admin.register(StockLot)
class StockLotAdmin(admin.ModelAdmin):
    list_display = ['symbol', 'buy_date', 'qty', 'price_usd', 'qty_remaining', 'owner', 'evidence']
    list_filter = ['symbol', 'owner']
    ordering = ['symbol', 'buy_date']

@admin.register(Sale)
class SaleAdmin(admin.ModelAdmin):
    list_display = ['symbol', 'sell_date', 'qty_sold', 'sale_price_usd', 'owner', 'evidence']
    list_filter = ['symbol', 'owner']
    inlines = [SaleAllocationInline]