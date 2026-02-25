# Migration for Rules Ramadhan - periode berlakunya rule
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('absensi', '0023_add_lupa_co_fields'),
    ]

    operations = [
        migrations.AddField(
            model_name='rules',
            name='tanggal_mulai',
            field=models.DateField(blank=True, help_text='Berlaku dari (kosong = permanen)', null=True),
        ),
        migrations.AddField(
            model_name='rules',
            name='tanggal_selesai',
            field=models.DateField(blank=True, help_text='Berlaku sampai (kosong = permanen)', null=True),
        ),
    ]
