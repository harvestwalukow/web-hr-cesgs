# Generated migration to rename WFH to WFA
from django.db import migrations, models
import apps.absensi.validators


def update_wfh_to_wfa_data(apps, schema_editor):
    """Update all WFH references to WFA in database"""
    AbsensiMagang = apps.get_model('absensi', 'AbsensiMagang')
    
    # Update keterangan field
    AbsensiMagang.objects.filter(keterangan='WFH').update(keterangan='WFA')


def reverse_update(apps, schema_editor):
    """Reverse: Update WFA back to WFH"""
    AbsensiMagang = apps.get_model('absensi', 'AbsensiMagang')
    AbsensiMagang.objects.filter(keterangan='WFA').update(keterangan='WFH')


class Migration(migrations.Migration):

    dependencies = [
        ('absensi', '0020_advanced_attendance_rules'),
    ]

    operations = [
        # Rename field aktivitas_wfh to aktivitas_wfa
        migrations.RenameField(
            model_name='absensimagang',
            old_name='aktivitas_wfh',
            new_name='aktivitas_wfa',
        ),
        # Update dokumen_persetujuan field: change upload_to and validators
        migrations.AlterField(
            model_name='absensimagang',
            name='dokumen_persetujuan',
            field=models.FileField(
                blank=True,
                help_text='Dokumen persetujuan atasan untuk WFA (.png, .jpg, .pdf, max 5MB)',
                null=True,
                upload_to='absensi/wfa_approval/%Y/%m/%d/',
                validators=[apps.absensi.validators.validate_file_size_wfa, apps.absensi.validators.validate_wfa_document_extension]
            ),
        ),
        # Update keterangan choices
        migrations.AlterField(
            model_name='absensimagang',
            name='keterangan',
            field=models.CharField(
                blank=False,
                choices=[
                    ('WFO', 'WFO'),
                    ('WFA', 'WFA'),
                    ('Izin Telat', 'Izin Telat'),
                    ('Izin Sakit', 'Izin Sakit')
                ],
                max_length=25,
                null=True
            ),
        ),
        # Update data: WFH -> WFA
        migrations.RunPython(update_wfh_to_wfa_data, reverse_update),
    ]
