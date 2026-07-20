from django.urls import path
from . import views

urlpatterns = [
    path('', views.HomePortfolioListView.as_view(), name = 'home'),
    path('buy/', views.StockLotCreateView.as_view(), name = 'lot_create'),
    path('sell/', views.SellView.as_view(), name = 'sell_create'),
    path('sales/', views.SaleListView.as_view(), name = 'sale_list'),
    path('lots/<int:pk>/evidence/', views.LotEvidenceView.as_view(), name = 'lot_evidence'),
    path('sales/<int:pk>/evidence/', views.SaleEvidenceView.as_view(), name = 'sale_evidence'),
    path('reports/fifo/', views.PortfolioReportView.as_view(), name = 'fifo_report'),
    # path('home/', views.HomePortfolioListView.as_view(), name = 'home'),
    path('lots/', views.LotListView.as_view(), name = 'lot_list'),
]