from django.shortcuts import render
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import ListView
from .models import Symbol, StockLot

# Create your views here.
class LotListView(LoginRequiredMixin, ListView):
    model = StockLot
    template_name = 'portfolio/lot_list.html'
    context_object_name = 'lots'

    def get_queryset(self):
        queryset = StockLot.objects.filter(owner = self.request.user).select_related('symbol')
        symbol_id = self.request.GET.get('symbol')
        if symbol_id:
            queryset = queryset.filter(symbol_id = symbol_id)
        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['symbols'] = Symbol.objects.all()
        context['selected_symbol_id'] = self.request.GET.get('symbol', '')
        return context
