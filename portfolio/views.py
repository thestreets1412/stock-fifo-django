from django.shortcuts import render
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import ListView, CreateView, FormView, DetailView, View
from django.urls import reverse_lazy
from django.http import JsonResponse, HttpResponseBadRequest
from django.template.loader import render_to_string
from .models import Symbol, StockLot, Sale
from .forms import StockLotForm, SellForm
from .services import (
    record_sale, InsufficientLotsError, get_user_lots, get_user_sales,
    build_fifo_report, build_dashboard_summary, parse_date_param,
)
from . import reports


def is_ajax(request):
    return request.headers.get('X-Requested-With') == 'XMLHttpRequest'

# Create your views here.
class LotEvidenceView(LoginRequiredMixin, DetailView):
    model = StockLot
    template_name = 'portfolio/lot_evidence.html'
    context_object_name = 'lot'

    def get_queryset(self):
        return StockLot.objects.filter(owner = self.request.user)
    
class SaleEvidenceView(LoginRequiredMixin, DetailView):
    model = Sale
    template_name = 'portfolio/sale_evidence.html'
    context_object_name = 'sale'

    def get_queryset(self):
        return Sale.objects.filter(owner = self.request.user)

class HomePortfolioListView(LoginRequiredMixin, ListView):
    model = StockLot
    template_name = 'portfolio/home.html'
    context_object_name = 'lots'

    def get_queryset(self):
        return get_user_lots(
            self.request.user,
            self.request.GET.get('symbol'),
            parse_date_param(self.request.GET.get('date_from')),
            parse_date_param(self.request.GET.get('date_to')),
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['dashboard'] = build_dashboard_summary(self.request.user)
        return context

class LotListView(LoginRequiredMixin, ListView):
    model = StockLot
    template_name = 'portfolio/lot_list.html'
    context_object_name = 'lots'

    def get_queryset(self):
        return get_user_lots(
            self.request.user,
            self.request.GET.get('symbol'),
            parse_date_param(self.request.GET.get('date_from')),
            parse_date_param(self.request.GET.get('date_to')),
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        date_from = parse_date_param(self.request.GET.get('date_from'))
        date_to = parse_date_param(self.request.GET.get('date_to'))
        context['symbols'] = Symbol.objects.all()
        context['selected_symbol_id'] = self.request.GET.get('symbol', '')
        context['selected_date_from'] = self.request.GET.get('date_from', '')
        context['selected_date_to'] = self.request.GET.get('date_to', '')
        context['form'] = StockLotForm()
        context['dashboard'] = build_dashboard_summary(self.request.user, date_from, date_to)
        return context

class StockLotCreateView(LoginRequiredMixin, CreateView):
    model = StockLot
    form_class = StockLotForm
    template_name = 'portfolio/lot_form.html'
    success_url = reverse_lazy('lot_list')

    def form_valid(self, form):
        form.instance.owner = self.request.user
        response = super().form_valid(form)
        if is_ajax(self.request):
            return JsonResponse({'success': True, 'redirect_url': str(self.get_success_url())})
        return response

    def form_invalid(self, form):
        if is_ajax(self.request):
            html = render_to_string(
                'portfolio/partials/lot_form.html',
                {'form': form, 'ajax': True},
                request=self.request,
            )
            return JsonResponse({'success': False, 'html': html}, status=400)
        return super().form_invalid(form)

class SellView(LoginRequiredMixin, FormView):
    form_class = SellForm
    template_name = 'portfolio/sell_form.html'
    success_url = reverse_lazy('sale_list')

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
                evidence=form.cleaned_data['evidence'],
            )
        except InsufficientLotsError as e:
            form.add_error(None, str(e))
            return self.form_invalid(form)

        response = super().form_valid(form)
        if is_ajax(self.request):
            return JsonResponse({'success': True, 'redirect_url': str(self.get_success_url())})
        return response

    def form_invalid(self, form):
        if is_ajax(self.request):
            html = render_to_string(
                'portfolio/partials/sell_form.html',
                {'form': form, 'ajax': True},
                request=self.request,
            )
            return JsonResponse({'success': False, 'html': html}, status=400)
        return super().form_invalid(form)
    
class SaleListView(LoginRequiredMixin, ListView):
    model = Sale
    template_name = 'portfolio/sale_list.html'
    context_object_name = 'sales'

    def get_queryset(self):
        return get_user_sales(
            self.request.user,
            self.request.GET.get('symbol'),
            parse_date_param(self.request.GET.get('date_from')),
            parse_date_param(self.request.GET.get('date_to')),
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['symbols'] = Symbol.objects.all()
        context['selected_symbol_id'] = self.request.GET.get('symbol', '')
        context['selected_date_from'] = self.request.GET.get('date_from', '')
        context['selected_date_to'] = self.request.GET.get('date_to', '')
        context['form'] = SellForm()
        return context

class PortfolioReportView(LoginRequiredMixin, View):
    def get(self, request):
        fmt = request.GET.get('format', 'csv')
        symbol_id = request.GET.get('symbol')
        sections = build_fifo_report(request.user, symbol_id)

        if fmt == 'pdf':
            owner_name = request.user.get_full_name() or request.user.username
            symbol_filter_note = None
            if symbol_id:
                symbol = Symbol.objects.filter(pk=symbol_id).first()
                if symbol:
                    symbol_filter_note = symbol.ticker
            return reports.fifo_report_pdf_response(
                'fifo_portfolio_report.pdf', sections,
                owner_name=owner_name, symbol_filter_note=symbol_filter_note,
            )
        if fmt == 'csv':
            return reports.fifo_report_csv_response('fifo_portfolio_report.csv', sections)
        return HttpResponseBadRequest('Unknown report format.')
    