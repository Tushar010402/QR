from django.contrib import admin
from .models import TRF, Barcode

@admin.register(TRF)
class TRFAdmin(admin.ModelAdmin):
    list_display = ('trf_number', 'created_by', 'created_at', 'expiry_date', 'is_expired')
    list_filter = ('created_at', 'expiry_date')
    search_fields = ('trf_number', 'notes')
    readonly_fields = ('created_at', 'qr_code')

@admin.register(Barcode)
class BarcodeAdmin(admin.ModelAdmin):
    list_display = ('barcode_number', 'trf', 'created_at', 'expiry_date', 'is_expired')
    list_filter = ('created_at', 'expiry_date')
    search_fields = ('barcode_number', 'notes', 'trf__trf_number')
    readonly_fields = ('created_at', 'barcode_image')
