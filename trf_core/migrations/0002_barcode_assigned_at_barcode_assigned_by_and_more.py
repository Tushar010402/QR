# Generated by Django 5.1.3 on 2024-12-01 12:11

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('trf_core', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name='barcode',
            name='assigned_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='barcode',
            name='assigned_by',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='assigned_barcodes', to=settings.AUTH_USER_MODEL),
        ),
        migrations.AddField(
            model_name='barcode',
            name='barcode_type',
            field=models.CharField(choices=[('generated', 'Generated'), ('pre_printed', 'Pre-printed')], default='generated', max_length=20),
        ),
        migrations.AddField(
            model_name='barcode',
            name='batch_number',
            field=models.CharField(blank=True, max_length=50),
        ),
        migrations.AddField(
            model_name='barcode',
            name='is_available',
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name='barcode',
            name='tube_data',
            field=models.JSONField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name='barcode',
            name='trf',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='barcodes', to='trf_core.trf'),
        ),
        migrations.CreateModel(
            name='BarcodeInventory',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('batch_number', models.CharField(max_length=50)),
                ('prefix', models.CharField(blank=True, max_length=10)),
                ('start_number', models.IntegerField()),
                ('end_number', models.IntegerField()),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('notes', models.TextField(blank=True)),
                ('created_by', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
            ],
        ),
    ]
