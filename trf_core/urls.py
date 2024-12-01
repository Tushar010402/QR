from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r'trfs', views.TRFViewSet)
router.register(r'barcodes', views.BarcodeViewSet)

urlpatterns = [
    path('api/', include(router.urls)),
    path('', views.home, name='home'),
    path('trfs/', views.trf_list, name='trf_list'),
    path('barcodes/', views.barcode_list, name='barcode_list'),
    path('trf/<int:pk>/', views.trf_detail, name='trf_detail'),
    path('barcode/<int:pk>/', views.barcode_detail, name='barcode_detail'),
    path('trf/create/', views.trf_create, name='trf_create'),
    path('barcode/create/<int:trf_id>/', views.barcode_create, name='barcode_create'),
]