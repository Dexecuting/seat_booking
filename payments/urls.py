from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import MpesaCallbackView, PaymentViewSet

router = DefaultRouter()
router.register('', PaymentViewSet, basename='payment')

urlpatterns = [
    path('mpesa/callback/<str:token>/', MpesaCallbackView.as_view(), name='mpesa-callback'),
] + router.urls
