# Generated manually for CatatanPengambilanGalon

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('hrd', '0035_add_izin_pulang_awal'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='CatatanPengambilanGalon',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('tanggal', models.DateField()),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('id_karyawan', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='catatan_pengambilan_galon', to='hrd.karyawan')),
                ('dicatat_oleh', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='catatan_galon_dicatat', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Catatan Pengambilan Galon',
                'verbose_name_plural': 'Catatan Pengambilan Galon',
                'db_table': 'catatan_pengambilan_galon',
                'ordering': ['-tanggal', '-created_at'],
                'unique_together': {('id_karyawan', 'tanggal')},
            },
        ),
    ]
