from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
import uuid
import qrcode
from barcode import Code128
from barcode.writer import ImageWriter
from io import BytesIO
from django.core.files import File
from PIL import Image
from django.core.exceptions import ValidationError

class TRF(models.Model):
    trf_number = models.CharField(max_length=50, unique=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    expiry_date = models.DateField()
    qr_code = models.ImageField(upload_to='qr_codes/', blank=True)
    notes = models.TextField(blank=True)

    def save(self, *args, **kwargs):
        if not self.qr_code:
            qr = qrcode.QRCode(
                version=1,
                error_correction=qrcode.constants.ERROR_CORRECT_L,
                box_size=10,
                border=4,
            )
            qr.add_data(f'TRF: {self.trf_number}\nExpiry: {self.expiry_date}')
            qr.make(fit=True)
            qr_image = qr.make_image(fill_color="black", back_color="white")
            
            buffer = BytesIO()
            qr_image.save(buffer, format='PNG')
            self.qr_code.save(f'qr_{self.trf_number}.png', 
                            File(buffer), save=False)
        
        super().save(*args, **kwargs)

    def __str__(self):
        return f'TRF: {self.trf_number}'

    @property
    def is_expired(self):
        return self.expiry_date < timezone.now().date()

class BarcodeInventory(models.Model):
    """Model for managing pre-printed barcode inventory"""
    batch_number = models.CharField(max_length=50)
    prefix = models.CharField(max_length=10, blank=True)
    start_number = models.IntegerField()
    end_number = models.IntegerField()
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    notes = models.TextField(blank=True)

    def clean(self):
        if self.start_number >= self.end_number:
            raise ValidationError("Start number must be less than end number")
        
    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)
        # Create individual barcodes if they don't exist
        self.create_barcodes()
    
    def create_barcodes(self):
        from .models import Barcode  # Import here to avoid circular import
        for number in range(self.start_number, self.end_number + 1):
            barcode_number = f"{self.prefix}{number:08d}"
            Barcode.objects.get_or_create(
                barcode_number=barcode_number,
                defaults={
                    'barcode_type': 'pre_printed',
                    'batch_number': self.batch_number,
                    'is_available': True
                }
            )

    def __str__(self):
        return f"Batch {self.batch_number} ({self.start_number}-{self.end_number})"

class Barcode(models.Model):
    """Model for individual barcodes (both pre-printed and generated)"""
    BARCODE_TYPE_CHOICES = [
        ('generated', 'Generated'),
        ('pre_printed', 'Pre-printed')
    ]
    
    trf = models.ForeignKey(TRF, related_name='barcodes', on_delete=models.CASCADE, null=True, blank=True)
    barcode_number = models.CharField(max_length=50, unique=True)
    barcode_image = models.ImageField(upload_to='barcodes/', blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    expiry_date = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True)
    barcode_type = models.CharField(max_length=20, choices=BARCODE_TYPE_CHOICES, default='generated')
    batch_number = models.CharField(max_length=50, blank=True)
    is_available = models.BooleanField(default=True)  # For tracking if barcode is available for use
    assigned_at = models.DateTimeField(null=True, blank=True)  # When the barcode was assigned to a TRF
    assigned_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='assigned_barcodes')
    tube_data = models.JSONField(null=True, blank=True)  # For storing additional tube information

    def save(self, *args, **kwargs):
        if not self.barcode_image:
            code128 = Code128(self.barcode_number, writer=ImageWriter())
            buffer = BytesIO()
            code128.write(buffer)
            self.barcode_image.save(f'barcode_{self.barcode_number}.png',
                                  File(buffer), save=False)
        
        if not self.expiry_date:
            self.expiry_date = self.trf.expiry_date
            
        super().save(*args, **kwargs)

    def __str__(self):
        return f'Barcode: {self.barcode_number}'

    @property
    def is_expired(self):
        return self.expiry_date < timezone.now().date()
