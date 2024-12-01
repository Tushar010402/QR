from rest_framework import serializers
from .models import TRF, Barcode
from django.contrib.auth.models import User

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'email']

class BarcodeSerializer(serializers.ModelSerializer):
    is_expired = serializers.BooleanField(read_only=True)
    
    class Meta:
        model = Barcode
        fields = ['id', 'barcode_number', 'barcode_image', 'created_at',
                 'expiry_date', 'notes', 'is_expired', 'trf']
        read_only_fields = ['barcode_image']

class TRFSerializer(serializers.ModelSerializer):
    barcodes = BarcodeSerializer(many=True, read_only=True)
    created_by = UserSerializer(read_only=True)
    is_expired = serializers.BooleanField(read_only=True)
    
    class Meta:
        model = TRF
        fields = ['id', 'trf_number', 'created_by', 'created_at', 'expiry_date',
                 'qr_code', 'notes', 'is_expired', 'barcodes']
        read_only_fields = ['qr_code']

    def create(self, validated_data):
        validated_data['created_by'] = self.context['request'].user
        return super().create(validated_data)