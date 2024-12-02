from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.shortcuts import get_object_or_404, render, redirect
from django.http import HttpResponse
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter, A4, landscape
from reportlab.lib.units import mm, inch
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Image, Paragraph, Spacer, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER
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
from django.views.decorators.http import require_http_methods
from django.core.serializers import serialize
from django.conf import settings
import base64
from io import BytesIO
from PIL import Image as PILImage
import barcode
from barcode.writer import ImageWriter

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

            # Validate barcode is not empty
            if not barcode_number or not barcode_number.strip():
                return JsonResponse({
                    'success': False,
                    'message': 'Barcode number cannot be empty'
                })
            
            # Check if barcode exists anywhere in the system
            existing_barcode = Barcode.objects.filter(barcode_number=barcode_number).first()
            if existing_barcode:
                if existing_barcode.trf:
                    return JsonResponse({
                        'success': False,
                        'message': f'This barcode is already assigned to TRF: {existing_barcode.trf.trf_number}'
                    })
                if not existing_barcode.is_available:
                    return JsonResponse({
                        'success': False,
                        'message': 'This barcode is already in use'
                    })
                barcode = existing_barcode
            else:
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
                
                # Additional validation for expiry date
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
    batch = get_object_or_404(BarcodeInventory, id=batch_id)
    
    try:
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
    batch = get_object_or_404(BarcodeInventory, id=batch_id)
    barcodes = Barcode.objects.filter(batch_number=batch.batch_number)
    
    # Create a response with appropriate headers for printing
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="batch_{batch.batch_number}_barcodes.pdf"'
    
    # Create PDF document optimized for label printing
    # Using A4 landscape for better label layout
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
        
        for idx, barcode_obj in enumerate(batch_barcodes):
            # Generate barcode image
            code128 = barcode.get_barcode_class('code128')
            barcode_instance = code128(barcode_obj.barcode_number, writer=ImageWriter())
            
            # Save barcode to BytesIO
            img_temp = BytesIO()
            barcode_instance.write(img_temp)
            img_temp.seek(0)
            
            # Create a cell with barcode image and text
            cell_contents = [
                Image(img_temp, width=45*mm, height=15*mm),
                Paragraph(barcode_obj.barcode_number, barcode_style)
            ]
            row.append(cell_contents)
            
            if len(row) == cols:
                data.append(row)
                row = []
        
        # Add any remaining items in the last row
        if row:
            while len(row) < cols:
                row.append(['', ''])  # Empty cells for padding
            data.append(row)
        
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
        if i + cols * rows < len(barcodes):  # Only add page break if not last page
            elements.append(PageBreak())
    
    try:
        doc.build(elements)
    except Exception as e:
        messages.error(request, f'Error generating PDF: {str(e)}')
        return redirect('barcode_inventory_list')
        
    return response

def public_scanner(request):
    """Public view for scanning barcodes"""
    return render(request, 'trf_core/public_scanner.html')

@require_http_methods(["GET"])
def public_barcode_info(request, barcode_number):
    """Public API endpoint for retrieving barcode information"""
    try:
        # Find the barcode
        barcode_obj = get_object_or_404(Barcode, barcode_number=barcode_number)
        
        # Get TRF information
        trf = barcode_obj.trf
        if not trf:
            return JsonResponse({
                'error': 'This barcode is not assigned to any TRF'
            })
        
        # Get associated barcodes (excluding the current one)
        associated_barcodes = [b.barcode_number for b in trf.barcodes.all() 
                             if b.barcode_number != barcode_number]
        
        # Generate barcode image
        code128 = barcode.get_barcode_class('code128')
        barcode_instance = code128(barcode_obj.barcode_number, writer=ImageWriter())
        
        # Save barcode to BytesIO
        img_temp = BytesIO()
        barcode_instance.write(img_temp)
        img_temp.seek(0)
        
        # Convert image to base64
        image_data = base64.b64encode(img_temp.getvalue()).decode()
        
        # Prepare the response data
        response_data = {
            'barcode_number': barcode_obj.barcode_number,
            'barcode_image': f'data:image/png;base64,{image_data}',
            'trf_number': trf.trf_number,
            'expiry_date': trf.expiry_date.strftime('%Y-%m-%d'),
            'is_expired': trf.is_expired,
            'associated_barcodes': associated_barcodes
        }
        
        return JsonResponse(response_data)
        
    except Exception as e:
        return JsonResponse({
            'error': str(e)
        }, status=400)

@login_required
def print_single_barcode(request, barcode_id):
    """View for printing a single barcode"""
    barcode_obj = get_object_or_404(Barcode, id=barcode_id)
    
    # Create a response with appropriate headers for printing
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="barcode_{barcode_obj.barcode_number}.pdf"'
    
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
    
    # Generate barcode image
    code128 = barcode.get_barcode_class('code128')
    barcode_instance = code128(barcode_obj.barcode_number, writer=ImageWriter())
    
    # Save barcode to BytesIO
    img_temp = BytesIO()
    barcode_instance.write(img_temp)
    img_temp.seek(0)
    
    # Create elements list
    elements = []
    
    # Add barcode image and text
    elements.append(Image(img_temp, width=60*mm, height=20*mm))
    elements.append(Paragraph(barcode_obj.barcode_number, barcode_style))
    
    try:
        doc.build(elements)
    except Exception as e:
        messages.error(request, f'Error generating PDF: {str(e)}')
        return redirect('barcode_detail', pk=barcode_id)
    
    return response
