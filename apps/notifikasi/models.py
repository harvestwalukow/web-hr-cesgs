"""
Models untuk modul Notifikasi

ReminderSchedule: Jadwal pengiriman reminder check-in/overtime via Web Push.
"""

from django.db import models


class ReminderSchedule(models.Model):
    """
    Jadwal pengiriman reminder yang dikelola HR.
    Kirim via Web Push (notifikasi sistem browser).
    """
    SCHEDULE_TYPE_CHOICES = [
        ('checkin_reminder', 'Reminder Absen Masuk'),
        ('overtime_alert', 'Reminder Klaim Lembur'),
    ]

    schedule_type = models.CharField(
        max_length=20,
        choices=SCHEDULE_TYPE_CHOICES,
        unique=True,
        help_text='Maksimal satu jadwal aktif per tipe'
    )
    run_time = models.TimeField(
        help_text='Jam pengiriman (WIB)'
    )
    message_template = models.TextField(
        blank=True,
        default='',
        help_text='Template pesan. Gunakan {nama}, {url_role} sebagai placeholder.'
    )
    is_active = models.BooleanField(
        default=False
    )
    last_run_date = models.DateField(
        null=True,
        blank=True,
        help_text='Tanggal terakhir dijalankan'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'reminder_schedule'
        verbose_name = 'Reminder Schedule'
        verbose_name_plural = 'Reminder Schedules'
        ordering = ['schedule_type']

    def __str__(self):
        return f"{self.get_schedule_type_display()} - {self.run_time.strftime('%H:%M')} ({'Aktif' if self.is_active else 'Nonaktif'})"
