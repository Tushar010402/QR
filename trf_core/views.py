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
from .models import TRF, Barcode
from .serializers import TRFSerializer, BarcodeSerializer
from django.utils import timezone
from datetime import datetime

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
