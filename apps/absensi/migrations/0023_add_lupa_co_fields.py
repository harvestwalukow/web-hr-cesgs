# Generated migration for lupa CO (forgot checkout) feature
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('absensi', '0022_add_aseec_location'),
    ]

    operations = [
        migrations.AddField(
            model_name='absensimagang',
            name='co_auto_generated',
            field=models.BooleanField(default=False, help_text='True jika jam_pulang diisi otomatis karena lupa CO'),
        ),
        migrations.AddField(
            model_name='absensimagang',
            name='alasan_lupa_co',
            field=models.TextField(blank=True, help_text='Alasan lupa check-out (diisi saat CI berikutnya)', null=True),
        ),
        migrations.AddField(
            model_name='absensimagang',
            name='jam_pulang_kira',
            field=models.TimeField(blank=True, help_text='Perkiraan jam pulang (diisi saat CI berikutnya)', null=True),
        ),
    ]
