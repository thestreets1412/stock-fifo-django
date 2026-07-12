from django.urls import path
from . import views

urlpatterns = [
    path('', views.LotListView.as_view(), name = 'lot_list'),
]