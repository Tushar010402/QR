from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r'trfs', views.TRFViewSet)
router.register(r'barcodes', views.BarcodeViewSet)

urlpatterns = [
    path('api/', include(router.urls)),
    path('', views.home, name='home'),
    path('lookup/', views.public_portal, name='public_portal'),
    
    # TRF URLs
    path('trfs/', views.trf_list, name='trf_list'),
    path('trf/create/', views.trf_create, name='trf_create'),
    path('trf/<int:pk>/', views.trf_detail, name='trf_detail'),
    
    # Barcode URLs
    path('barcodes/', views.barcode_list, name='barcode_list'),
    path('barcode/<int:pk>/', views.barcode_detail, name='barcode_detail'),
    path('barcode/create/<int:trf_id>/', views.barcode_create, name='barcode_create'),
    
    # Pre-printed Barcode Management
    path('barcode-inventory/', views.barcode_inventory_list, name='barcode_inventory_list'),
    path('barcode-inventory/create/', views.barcode_inventory_create, name='barcode_inventory_create'),
    path('available-barcodes/', views.available_barcodes, name='available_barcodes'),
    path('assign-barcode/<int:barcode_id>/', views.assign_barcode, name='assign_barcode'),
    path('delete-batch/<int:batch_id>/', views.delete_barcode_batch, name='delete_barcode_batch'),
    path('print-batch/<int:batch_id>/', views.print_barcode_batch, name='print_barcode_batch'),
    path('print-barcode/<int:barcode_id>/', views.print_single_barcode, name='print_single_barcode'),
    
    # Barcode Scanner
    path('scanner/', views.barcode_scanner, name='barcode_scanner'),
    path('api/process-scan/', views.process_scanned_barcode, name='process_scanned_barcode'),
]