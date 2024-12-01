from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.shortcuts import get_object_or_404, render, redirect
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

            barcode = get_object_or_404(Barcode, barcode_number=barcode_number)
            trf = get_object_or_404(TRF, id=trf_id)

            if not barcode.is_available:
                return JsonResponse({
                    'success': False,
                    'message': 'This barcode is already in use'
                })

            # Assign barcode to TRF
            barcode.trf = trf
            barcode.is_available = False
            barcode.assigned_at = timezone.now()
            barcode.assigned_by = request.user
            
            # Handle expiry date
            expiry_date = data.get('expiry_date')
            if expiry_date:
                try:
                    barcode.expiry_date = datetime.strptime(expiry_date, '%Y-%m-%d').date()
                except ValueError:
                    return JsonResponse({
                        'success': False,
                        'message': 'Invalid expiry date format'
                    })
            else:
                barcode.expiry_date = trf.expiry_date
            
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
