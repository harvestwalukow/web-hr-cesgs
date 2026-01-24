# Generated migration to update Izin choices and overtime amount
from django.db import migrations, models


def update_izin_choices_forward(apps, schema_editor):
    """Update existing izin records: change wfa/wfh to sakit if needed"""
    Izin = apps.get_model('hrd', 'Izin')
    # Keep existing data as is - we're just adding 'sakit' as a new option
    # Legacy wfa/wfh records will remain for backward compatibility
    pass


def update_izin_choices_reverse(apps, schema_editor):
    """Reverse migration - no data changes needed"""
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('hrd', '0033_remove_wfa_from_cutibersama'),
    ]

    operations = [
        migrations.AlterField(
            model_name='izin',
            name='jenis_izin',
            field=models.CharField(
                choices=[
                    ('telat', 'Izin Telat'),
                    ('sakit', 'Izin Sakit'),
                    ('wfa', 'Izin WFA'),  # Legacy support
                    ('wfh', 'Izin WFH'),  # Legacy support
                    ('klaim_lembur', 'Izin Lembur'),
                    ('business_trip', 'Izin Business Trip'),
                ],
                max_length=50
            ),
        ),
        migrations.AlterField(
            model_name='izin',
            name='kompensasi_lembur',
            field=models.CharField(
                blank=True,
                choices=[
                    ('makan', 'Uang Makan (Max 49 rb)'),
                    ('masuk_siang', 'Masuk Siang (Esok Hari)'),
                ],
                help_text='Kompensasi untuk pengajuan Izin Lembur',
                max_length=20,
                null=True
            ),
        ),
    ]
