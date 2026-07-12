from django import forms
from .models import StockLot, Symbol


class StockLotForm(forms.ModelForm):
    class Meta:
        model = StockLot
        fields = ['symbol', 'buy_date', 'price_usd', 'qty', 'fx_rate_usd_thb', 'evidence']
        widgets = {
            'buy_date': forms.DateInput(attrs={'type': 'date'}),
        }


class SellForm(forms.Form):
    """
    NOT a ModelForm — there's no single model that maps directly to
    'a sale request'. This form just collects input; record_sale()
    does the actual work of creating Sale + SaleAllocation rows.
    """
    symbol = forms.ModelChoiceField(queryset=Symbol.objects.all())
    sell_date = forms.DateField(widget=forms.DateInput(attrs={'type': 'date'}))
    qty_sold = forms.DecimalField(max_digits=18, 
                                  decimal_places=8, 
                                  min_value=0.00000001)
    sale_price_usd = forms.DecimalField(max_digits=14, 
                                        decimal_places=6, 
                                        min_value=0)
    fee_usd = forms.DecimalField(max_digits=10, 
                                 decimal_places=4, 
                                 min_value=0, initial=0)
    fx_rate_usd_thb = forms.DecimalField(max_digits=10, 
                                         decimal_places=4, min_value=0)
    evidence = forms.ImageField(required=False)