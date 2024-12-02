from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.shortcuts import get_object_or_404, render, redirect
from django.http import HttpResponse
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter, A4, landscape
from reportlab.lib.units import mm, inch
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER
from io import BytesIO
from PIL import Image as PILImage
from reportlab.platypus import Image as RLImage
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator
from django.views.generic import ListView
from django.contrib import messages
from django.http import JsonResponse
from django.urls import reverse
from .models import TRF, Barcode, BarcodeInventory
from .serializers import TRFSerializer, BarcodeSerializer
from django.utils import timezone
from datetime import datetime
import json
from django.views.decorators.csrf import csrf_exempt
from django.core.exceptions import ValidationError

class IsAuthenticatedOrReadOnly(permissions.BasePermission):
    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return True
        return request.user and request.user.is_authenticated

class TRFViewSet(viewsets.ModelViewSet):
    queryset = TRF.objects.all()
    serializer_class = TRFSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]

    def get_queryset(self):
        queryset = TRF.objects.all()
        trf_number = self.request.query_params.get('trf_number', None)
        if trf_number:
            queryset = queryset.filter(trf_number=trf_number)
        return queryset

    @action(detail=True, methods=['post'])
    def add_barcode(self, request, pk=None):
        trf = self.get_object()
        serializer = BarcodeSerializer(data=request.data)
        
        if serializer.is_valid():
            serializer.save(trf=trf)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class BarcodeViewSet(viewsets.ModelViewSet):
    queryset = Barcode.objects.all()
    serializer_class = BarcodeSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]

    def get_queryset(self):
        queryset = Barcode.objects.all()
        barcode_number = self.request.query_params.get('barcode_number', None)
        if barcode_number:
            queryset = queryset.filter(barcode_number=barcode_number)
        return queryset

    @action(detail=True, methods=['get'])
    def check_expiry(self, request, pk=None):
        barcode = self.get_object()
        is_expired = barcode.expiry_date < timezone.now().date()
        return Response({
            'barcode_number': barcode.barcode_number,
            'is_expired': is_expired,
            'expiry_date': barcode.expiry_date
        })

class TRFListView(ListView):
    model = TRF
    template_name = 'trf_core/trf_list.html'
    context_object_name = 'trfs'

def home(request):
    return render(request, 'trf_core/home.html')

def public_portal(request):
    """Public portal for barcode lookup without authentication"""
    search_query = request.GET.get('search', '').strip()
    search_performed = bool(search_query)
    barcode = None
    
    if search_query:
        try:
            barcode = Barcode.objects.select_related('trf').get(barcode_number=search_query)
        except Barcode.DoesNotExist:
            pass
    
    return render(request, 'trf_core/public_portal.html', {
        'barcode': barcode,
        'search_performed': search_performed
    })

def trf_list(request):
    trfs = TRF.objects.all().order_by('-created_at')
    return render(request, 'trf_core/trf_list.html', {'trfs': trfs})

def barcode_list(request):
    barcodes = Barcode.objects.all().order_by('-created_at')
    return render(request, 'trf_core/barcode_list.html', {'barcodes': barcodes})

@login_required
def trf_create(request):
    if request.method == 'POST':
        trf_number = request.POST.get('trf_number')
        expiry_date = request.POST.get('expiry_date')
        notes = request.POST.get('notes')

        try:
            expiry_date = datetime.strptime(expiry_date, '%Y-%m-%d').date()
            trf = TRF.objects.create(
                trf_number=trf_number,
                expiry_date=expiry_date,
                notes=notes,
                created_by=request.user
            )
            messages.success(request, 'TRF created successfully.')
            return redirect('trf_detail', pk=trf.pk)
        except Exception as e:
            messages.error(request, f'Error creating TRF: {str(e)}')
            return redirect('trf_list')

    return render(request, 'trf_core/trf_form.html')

@login_required
def barcode_create(request, trf_id):
    trf = get_object_or_404(TRF, id=trf_id)
    
    if request.method == 'POST':
        barcode_number = request.POST.get('barcode_number')
        expiry_date = request.POST.get('expiry_date')
        notes = request.POST.get('notes')

        try:
            expiry_date = datetime.strptime(expiry_date, '%Y-%m-%d').date() if expiry_date else trf.expiry_date
            barcode = Barcode.objects.create(
                trf=trf,
                barcode_number=barcode_number,
                expiry_date=expiry_date,
                notes=notes
            )
            messages.success(request, 'Barcode created successfully.')
            return redirect('barcode_detail', pk=barcode.pk)
        except Exception as e:
            messages.error(request, f'Error creating barcode: {str(e)}')
            return redirect('trf_detail', pk=trf_id)

    return render(request, 'trf_core/barcode_form.html', {'trf': trf})

def trf_detail(request, pk):
    trf = get_object_or_404(TRF, pk=pk)
    return render(request, 'trf_core/trf_detail.html', {'trf': trf})

def barcode_detail(request, pk):
    barcode = get_object_or_404(Barcode, pk=pk)
    return render(request, 'trf_core/barcode_detail.html', {'barcode': barcode})

@login_required
def barcode_inventory_list(request):
    inventories = BarcodeInventory.objects.all().order_by('-created_at')
    for inventory in inventories:
        inventory.available_count = Barcode.objects.filter(
            batch_number=inventory.batch_number,
            is_available=True
        ).count()
    return render(request, 'trf_core/barcode_inventory_list.html', {'inventories': inventories})

@login_required
def barcode_inventory_create(request):
    if request.method == 'POST':
        try:
            batch_number = request.POST.get('batch_number')
            prefix = request.POST.get('prefix', '')
            start_number = int(request.POST.get('start_number'))
            end_number = int(request.POST.get('end_number'))
            notes = request.POST.get('notes', '')

            inventory = BarcodeInventory.objects.create(
                batch_number=batch_number,
                prefix=prefix,
                start_number=start_number,
                end_number=end_number,
                notes=notes,
                created_by=request.user
            )
            messages.success(request, f'Successfully created {end_number - start_number + 1} barcodes')
            return redirect('barcode_inventory_list')
        except ValidationError as e:
            messages.error(request, str(e))
        except Exception as e:
            messages.error(request, f'Error creating barcodes: {str(e)}')
    
    return render(request, 'trf_core/barcode_inventory_form.html')

@login_required
def barcode_scanner(request):
    """View for scanning barcodes and assigning them to TRFs"""
    return render(request, 'trf_core/barcode_scanner.html')

@csrf_exempt
@login_required
def process_scanned_barcode(request):
    """API endpoint for processing scanned barcodes"""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            barcode_number = data.get('barcode_number')
            trf_id = data.get('trf_id')
            tube_data = data.get('tube_data', {})

            # Check if barcode exists
            try:
                barcode = Barcode.objects.get(barcode_number=barcode_number)
                if not barcode.is_available:
                    return JsonResponse({
                        'success': False,
                        'message': 'This barcode is already in use'
                    })
            except Barcode.DoesNotExist:
                # Create new external barcode
                trf = get_object_or_404(TRF, id=trf_id)
                custom_expiry = data.get('expiry_date')
                
                try:
                    expiry_date = datetime.strptime(custom_expiry, '%Y-%m-%d').date() if custom_expiry else trf.expiry_date
                except ValueError:
                    return JsonResponse({
                        'success': False,
                        'message': 'Invalid expiry date format. Use YYYY-MM-DD'
                    })
                
                if expiry_date < timezone.now().date():
                    return JsonResponse({
                        'success': False,
                        'message': 'Expiry date cannot be in the past'
                    })
                
                barcode = Barcode.objects.create(
                    barcode_number=barcode_number,
                    barcode_type='external',
                    is_available=True,
                    expiry_date=expiry_date
                )

            trf = get_object_or_404(TRF, id=trf_id)

            # Assign barcode to TRF
            barcode.trf = trf
            barcode.is_available = False
            barcode.assigned_at = timezone.now()
            barcode.assigned_by = request.user
            barcode.tube_data = tube_data
            barcode.save()

            return JsonResponse({
                'success': True,
                'message': 'Barcode successfully assigned to TRF',
                'barcode_id': barcode.id
            })

        except Exception as e:
            return JsonResponse({
                'success': False,
                'message': str(e)
            })

    return JsonResponse({'success': False, 'message': 'Invalid request method'})

@login_required
def available_barcodes(request):
    """View for listing available pre-printed barcodes"""
    barcodes = Barcode.objects.filter(
        barcode_type='pre_printed',
        is_available=True
    )
    
    # Filter by batch if specified
    batch = request.GET.get('batch')
    if batch:
        barcodes = barcodes.filter(batch_number=batch)
    
    barcodes = barcodes.order_by('batch_number', 'barcode_number')
    
    return render(request, 'trf_core/available_barcodes.html', {
        'barcodes': barcodes,
        'selected_batch': batch
    })

@login_required
def delete_barcode_batch(request, batch_id):
    """View for deleting a barcode batch and its associated barcodes"""
    try:
        batch = get_object_or_404(BarcodeInventory, id=batch_id)
        barcodes = Barcode.objects.filter(batch_number=batch.batch_number)
        
        if not barcodes.exists():
            messages.error(request, 'No barcodes found in this batch')
            return redirect('barcode_inventory_list')
        
        # Delete associated barcodes that are still available (not assigned to any TRF)
        Barcode.objects.filter(batch_number=batch.batch_number, is_available=True).delete()
        
        # Check if there are any assigned barcodes
        assigned_barcodes = Barcode.objects.filter(batch_number=batch.batch_number, is_available=False).exists()
        if assigned_barcodes:
            messages.warning(request, 'Some barcodes from this batch are in use and were not deleted')
        
        # Delete the batch
        batch.delete()
        messages.success(request, 'Barcode batch deleted successfully')
    except Exception as e:
        messages.error(request, f'Error deleting batch: {str(e)}')
    
    return redirect('barcode_inventory_list')

@login_required
def print_barcode_batch(request, batch_id):
    """View for printing all barcodes in a batch"""
    try:
        batch = get_object_or_404(BarcodeInventory, id=batch_id)
        barcodes = Barcode.objects.filter(batch_number=batch.batch_number)
        
        if not barcodes.exists():
            messages.error(request, 'No barcodes found in this batch')
            return redirect('barcode_inventory_list')
        
        # Create a response with appropriate headers for printing
        response = HttpResponse(content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="batch_{batch.batch_number}_barcodes.pdf"'
        
        # Create PDF document optimized for label printing
        doc = SimpleDocTemplate(
            response,
            pagesize=landscape(A4),
            rightMargin=10*mm,
            leftMargin=10*mm,
            topMargin=10*mm,
            bottomMargin=10*mm
        )
        
        # Define styles
        styles = getSampleStyleSheet()
        barcode_style = ParagraphStyle(
            'BarcodeStyle',
            parent=styles['Normal'],
            alignment=TA_CENTER,
            fontSize=8,
            leading=10
        )
        
        elements = []
        
        # Calculate optimal layout
        page_width = landscape(A4)[0] - 20*mm
        page_height = landscape(A4)[1] - 20*mm
        label_width = 50*mm
        label_height = 25*mm
        cols = int(page_width // label_width)
        rows = int(page_height // label_height)
        
        # Process barcodes in groups for table layout
        for i in range(0, len(barcodes), cols * rows):
            batch_barcodes = barcodes[i:i + cols * rows]
            data = []
            row = []
            
            for barcode in batch_barcodes:
                try:
                    # Get the barcode image
                    img_temp = BytesIO()
                    img = PILImage.open(barcode.barcode_image.path)
                    img.save(img_temp, format='PNG')
                    img_temp.seek(0)
                    
                    # Create a cell with barcode image and text
                    barcode_image = RLImage(img_temp, width=45*mm, height=15*mm)
                    barcode_text = Paragraph(barcode.barcode_number, barcode_style)
                    
                    cell_contents = [
                        barcode_image,
                        barcode_text
                    ]
                    row.append(cell_contents)
                    
                    if len(row) == cols:
                        data.append(row)
                        row = []
                except Exception as e:
                    messages.error(request, f'Error processing barcode {barcode.barcode_number}: {str(e)}')
                    continue
            
            # Add any remaining items in the last row
            if row:
                while len(row) < cols:
                    row.append(['', ''])  # Empty cells for padding
                data.append(row)
            
            if data:  # Only create table if we have data
                # Create table for this group
                col_widths = [label_width] * cols
                table = Table(data, colWidths=col_widths, rowHeights=[label_height] * len(data))
                
                table.setStyle(TableStyle([
                    ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                    ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                    ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
                    ('BOX', (0, 0), (-1, -1), 0.5, colors.grey),
                    ('LEFTPADDING', (0, 0), (-1, -1), 2*mm),
                    ('RIGHTPADDING', (0, 0), (-1, -1), 2*mm),
                    ('TOPPADDING', (0, 0), (-1, -1), 1*mm),
                    ('BOTTOMPADDING', (0, 0), (-1, -1), 1*mm),
                ]))
                
                elements.append(table)
                elements.append(PageBreak())
        
        if not elements:
            messages.error(request, 'No valid barcodes to print')
            return redirect('barcode_inventory_list')
        
        doc.build(elements)
        return response
        
    except Exception as e:
        messages.error(request, f'Error generating PDF: {str(e)}')
        return redirect('barcode_inventory_list')

@login_required
def print_single_barcode(request, barcode_id):
    """View for printing a single barcode"""
    try:
        barcode = get_object_or_404(Barcode, id=barcode_id)
        
        # Create a response with appropriate headers for printing
        response = HttpResponse(content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="barcode_{barcode.barcode_number}.pdf"'
        
        # Create PDF document optimized for label printing
        doc = SimpleDocTemplate(
            response,
            pagesize=(62*mm, 29*mm),  # Standard label size
            rightMargin=1*mm,
            leftMargin=1*mm,
            topMargin=1*mm,
            bottomMargin=1*mm
        )
        
        # Define styles
        styles = getSampleStyleSheet()
        barcode_style = ParagraphStyle(
            'BarcodeStyle',
            parent=styles['Normal'],
            alignment=TA_CENTER,
            fontSize=8,
            leading=10
        )
        
        elements = []
        
        try:
            # Get the barcode image
            img_temp = BytesIO()
            img = PILImage.open(barcode.barcode_image.path)
            img.save(img_temp, format='PNG')
            img_temp.seek(0)
            
            # Add barcode image sized for label
            barcode_image = RLImage(img_temp, width=58*mm, height=20*mm)
            elements.append(barcode_image)
            elements.append(Spacer(1, 1*mm))
            
            # Add barcode number in small text
            elements.append(Paragraph(barcode.barcode_number, barcode_style))
            
            # Build the PDF with a frame
            def add_border(canvas, doc):
                canvas.setStrokeColorRGB(0.8, 0.8, 0.8)  # Light grey
                canvas.setLineWidth(0.5)
                canvas.rect(
                    doc.leftMargin,
                    doc.bottomMargin,
                    doc.width,
                    doc.height
                )
            
            doc.build(elements, onFirstPage=add_border, onLaterPages=add_border)
            return response
            
        except Exception as e:
            messages.error(request, f'Error processing barcode image: {str(e)}')
            return redirect('barcode_detail', pk=barcode_id)
            
    except Exception as e:
        messages.error(request, f'Error generating PDF: {str(e)}')
        return redirect('barcode_list')

def assign_barcode(request, barcode_id):
    """View for assigning a pre-printed barcode to a TRF"""
    barcode = get_object_or_404(Barcode, id=barcode_id)
    
    if request.method == 'POST':
        trf_id = request.POST.get('trf_id')
        tube_data = {
            'sample_type': request.POST.get('sample_type'),
            'volume': request.POST.get('volume'),
            'collection_date': request.POST.get('collection_date'),
            'notes': request.POST.get('notes')
        }
        
        try:
            trf = get_object_or_404(TRF, id=trf_id)
            
            if not barcode.is_available:
                messages.error(request, 'This barcode is already in use')
                return redirect('available_barcodes')
            
            barcode.trf = trf
            barcode.is_available = False
            barcode.assigned_at = timezone.now()
            barcode.assigned_by = request.user
            barcode.tube_data = tube_data
            barcode.save()
            
            messages.success(request, 'Barcode successfully assigned to TRF')
            return redirect('trf_detail', pk=trf.id)
            
        except Exception as e:
            messages.error(request, f'Error assigning barcode: {str(e)}')
            return redirect('available_barcodes')
    
    trfs = TRF.objects.filter(created_by=request.user).order_by('-created_at')
    return render(request, 'trf_core/assign_barcode.html', {
        'barcode': barcode,
        'trfs': trfs
    })
