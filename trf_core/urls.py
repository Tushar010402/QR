from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r'trfs', views.TRFViewSet)
router.register(r'barcodes', views.BarcodeViewSet)

urlpatterns = [
    path('', include(router.urls)),
    path('trf-list/', views.TRFListView.as_view(), name='trf_list'),
    path('barcode-list/', views.BarcodeListView.as_view(), name='barcode_list'),
]