from django.urls import path
from . import views

urlpatterns = [
    path('', views.LotListView.as_view(), name = 'lot_list'),
    path('buy/', views.StockLotCreateView.as_view(), name = 'lot_create'),
    path('sell/', views.SellView.as_view(), name = 'sell_create'),
    path('sales/', views.SaleListView.as_view(), name = 'sale_list'),
]