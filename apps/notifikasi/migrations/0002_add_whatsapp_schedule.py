# Generated manually - WhatsApp Schedule feature (consolidated)

from django.db import migrations, models
from datetime import time

DEFAULT_CHECKIN = """Reminder Absen Masuk

Halo {nama},

Anda belum melakukan check-in hari ini.

Terima kasih,
HR CESGS"""

DEFAULT_OVERTIME = """Notifikasi Lembur

Halo {nama},

Anda dapat mengajukan klaim lembur untuk hari ini.
Jangan lupa untuk melakukan check-out.

Terima kasih,
HR CESGS"""


def create_default_schedules(apps, schema_editor):
    WhatsAppSchedule = apps.get_model('notifikasi', 'WhatsAppSchedule')
    defaults = [
        ('checkin_reminder', time(9, 0), DEFAULT_CHECKIN),
        ('overtime_alert', time(18, 31), DEFAULT_OVERTIME),
    ]
    for schedule_type, run_time, message_template in defaults:
        WhatsAppSchedule.objects.get_or_create(
            schedule_type=schedule_type,
            defaults={
                'run_time': run_time,
                'message_template': message_template,
                'is_active': False,
            }
        )


def remove_default_schedules(apps, schema_editor):
    WhatsAppSchedule = apps.get_model('notifikasi', 'WhatsAppSchedule')
    WhatsAppSchedule.objects.filter(
        schedule_type__in=['checkin_reminder', 'overtime_alert']
    ).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('notifikasi', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='WhatsAppSchedule',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('schedule_type', models.CharField(
                    choices=[
                        ('checkin_reminder', 'Reminder Check-in'),
                        ('overtime_alert', 'Reminder Klaim Lembur'),
                    ],
                    help_text='Maksimal satu jadwal aktif per tipe',
                    max_length=20,
                    unique=True
                )),
                ('run_time', models.TimeField(help_text='Jam pengiriman (WIB)')),
                ('message_template', models.TextField(
                    blank=True,
                    default='',
                    help_text='Template pesan. Gunakan {nama}, {url_role} sebagai placeholder.',
                )),
                ('is_active', models.BooleanField(default=False)),
                ('last_run_date', models.DateField(blank=True, help_text='Tanggal terakhir dijalankan', null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'verbose_name': 'WhatsApp Schedule',
                'verbose_name_plural': 'WhatsApp Schedules',
                'db_table': 'whatsapp_schedule',
                'ordering': ['schedule_type'],
            },
        ),
        migrations.RunPython(create_default_schedules, remove_default_schedules),
    ]
