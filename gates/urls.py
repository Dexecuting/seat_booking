from django.urls import path

from .views import GateEntryListView, ScanView

urlpatterns = [
    path('scan/', ScanView.as_view(), name='gate-scan'),
    path('entries/', GateEntryListView.as_view(), name='gate-entries'),
]
