from django import forms
from django.contrib.auth.forms import AuthenticationForm
from .models import StockLot, Symbol


class BootstrapAuthenticationForm(AuthenticationForm):
    username = forms.CharField(widget=forms.TextInput(attrs={'class': 'form-control', 'autofocus': True}))
    password = forms.CharField(widget=forms.PasswordInput(attrs={'class': 'form-control'}))


class StockLotForm(forms.ModelForm):
    class Meta:
        model = StockLot
        fields = ['symbol', 'buy_date', 'price_usd', 'qty', 'fx_rate_usd_thb', 'evidence']
        widgets = {
            'symbol': forms.Select(attrs={'class': 'form-select'}),
            'buy_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'price_usd': forms.NumberInput(attrs={'class': 'form-control'}),
            'qty': forms.NumberInput(attrs={'class': 'form-control'}),
            'fx_rate_usd_thb': forms.NumberInput(attrs={'class': 'form-control'}),
            'evidence': forms.ClearableFileInput(attrs={'class': 'form-control'}),
        }


class SellForm(forms.Form):
    """
    NOT a ModelForm — there's no single model that maps directly to
    'a sale request'. This form just collects input; record_sale()
    does the actual work of creating Sale + SaleAllocation rows.
    """
    symbol = forms.ModelChoiceField(
        queryset=Symbol.objects.all(),
        widget=forms.Select(attrs={'class': 'form-select'}),
    )
    sell_date = forms.DateField(
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
    )
    qty_sold = forms.DecimalField(max_digits=18,
                                  decimal_places=8,
                                  min_value=0.00000001,
                                  widget=forms.NumberInput(attrs={'class': 'form-control'}))
    sale_price_usd = forms.DecimalField(max_digits=14,
                                        decimal_places=6,
                                        min_value=0,
                                        widget=forms.NumberInput(attrs={'class': 'form-control'}))
    fee_usd = forms.DecimalField(max_digits=10,
                                 decimal_places=4,
                                 min_value=0, initial=0,
                                 widget=forms.NumberInput(attrs={'class': 'form-control'}))
    fx_rate_usd_thb = forms.DecimalField(max_digits=10,
                                         decimal_places=4, min_value=0,
                                         widget=forms.NumberInput(attrs={'class': 'form-control'}))
    evidence = forms.ImageField(
        required=False,
        widget=forms.ClearableFileInput(attrs={'class': 'form-control'}),
    )
