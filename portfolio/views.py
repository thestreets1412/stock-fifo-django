from django.shortcuts import render
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import ListView, CreateView, FormView
from django.urls import reverse_lazy
from .models import Symbol, StockLot
from .forms import StockLotForm, SellForm
from .services import record_sale, InsufficientLotsError

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

class StockLotCreateView(LoginRequiredMixin, CreateView):
    model = StockLot
    form_class = StockLotForm
    template_name = 'portfolio/lot_form.html'
    success_url = reverse_lazy('lot_list')

    def form_valid(self, form):
        form.instance.owner = self.request.user
        return super().form_valid(form)
    
class SellView(LoginRequiredMixin, FormView):
    form_class = SellForm
    template_name = 'portfolio/sell_form.html'
    success_url = reverse_lazy('lot_list')

    def form_valid(self, form):
        try:
            record_sale(
                owner=self.request.user,
                symbol=form.cleaned_data['symbol'],
                sell_date=form.cleaned_data['sell_date'],
                qty_sold=form.cleaned_data['qty_sold'],
                sale_price_usd=form.cleaned_data['sale_price_usd'],
                fee_usd=form.cleaned_data['fee_usd'],
                fx_rate_usd_thb=form.cleaned_data['fx_rate_usd_thb'],
            )
        except InsufficientLotsError as e:
            form.add_error(None, str(e))
            return self.form_invalid(form)

        return super().form_valid(form)