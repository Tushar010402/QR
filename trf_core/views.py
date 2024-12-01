from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.shortcuts import get_object_or_404, render
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator
from django.views.generic import ListView
from .models import TRF, Barcode
from .serializers import TRFSerializer, BarcodeSerializer
from django.utils import timezone

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

class BarcodeListView(ListView):
    model = Barcode
    template_name = 'trf_core/barcode_list.html'
    context_object_name = 'barcodes'
