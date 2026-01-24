# Generated migration to add ASEEC office location
from django.db import migrations
from decimal import Decimal


def add_aseec_location(apps, schema_editor):
    """Add ASEEC office location to LokasiKantor"""
    LokasiKantor = apps.get_model('absensi', 'LokasiKantor')
    
    # Use get_or_create to avoid duplicates if migration runs multiple times
    lokasi, created = LokasiKantor.objects.get_or_create(
        nama='ASEEC',
        defaults={
            'latitude': Decimal('-7.27072566065834'),
            'longitude': Decimal('112.75979419568775'),
            'radius': 300,
            'is_active': True
        }
    )
    
    if created:
        print(f"✅ Lokasi kantor 'ASEEC' berhasil ditambahkan (ID: {lokasi.id})")
    else:
        # Update existing location if it exists
        lokasi.latitude = Decimal('-7.27072566065834')
        lokasi.longitude = Decimal('112.75979419568775')
        lokasi.radius = 300
        lokasi.is_active = True
        lokasi.save()
        print(f"✅ Lokasi kantor 'ASEEC' berhasil diupdate (ID: {lokasi.id})")


def remove_aseec_location(apps, schema_editor):
    """Remove ASEEC office location (reverse migration)"""
    LokasiKantor = apps.get_model('absensi', 'LokasiKantor')
    LokasiKantor.objects.filter(nama='ASEEC').delete()
    print("✅ Lokasi kantor 'ASEEC' berhasil dihapus")


class Migration(migrations.Migration):

    dependencies = [
        ('absensi', '0021_rename_wfh_to_wfa'),
    ]

    operations = [
        migrations.RunPython(add_aseec_location, remove_aseec_location),
    ]
