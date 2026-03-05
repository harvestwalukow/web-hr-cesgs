"""
Models untuk modul Notifikasi

Menyimpan log semua notifikasi WhatsApp yang dikirim ke karyawan.
"""

from django.db import models
from apps.hrd.models import Karyawan


class WhatsAppLog(models.Model):
    """
    Log semua notifikasi WhatsApp yang dikirim via Fonnte API.
    Berguna untuk tracking dan debugging.
    """
    NOTIFICATION_TYPE_CHOICES = [
        ('overtime_alert', 'Alert Lembur 10 Jam'),
        ('reminder', 'Reminder'),
        ('approval', 'Approval Status'),
        ('general', 'General Notification'),
    ]
    
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('sent', 'Sent'),
        ('failed', 'Failed'),
    ]
    
    karyawan = models.ForeignKey(
        Karyawan, 
        on_delete=models.CASCADE,
        related_name='whatsapp_logs'
    )
    notification_type = models.CharField(
        max_length=20, 
        choices=NOTIFICATION_TYPE_CHOICES,
        default='general'
    )
    phone_number = models.CharField(max_length=20)
    message = models.TextField()
    status = models.CharField(
        max_length=10, 
        choices=STATUS_CHOICES, 
        default='pending'
    )
    fonnte_response = models.JSONField(
        null=True, 
        blank=True,
        help_text="Raw response dari Fonnte API"
    )
    sent_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'whatsapp_log'
        ordering = ['-sent_at']
        verbose_name = 'WhatsApp Log'
        verbose_name_plural = 'WhatsApp Logs'
    
    def __str__(self):
        return f"{self.karyawan.nama} - {self.notification_type} ({self.status})"


class WhatsAppSchedule(models.Model):
    """
    Jadwal pengiriman WhatsApp yang dikelola HR.
    Menggantikan cron otomatis CheckinReminder dan OvertimeAlert.
    """
    SCHEDULE_TYPE_CHOICES = [
        ('checkin_reminder', 'Reminder Check-in'),
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
        default=True
    )
    last_run_date = models.DateField(
        null=True,
        blank=True,
        help_text='Tanggal terakhir dijalankan'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'whatsapp_schedule'
        verbose_name = 'WhatsApp Schedule'
        verbose_name_plural = 'WhatsApp Schedules'
        ordering = ['schedule_type']

    def __str__(self):
        return f"{self.get_schedule_type_display()} - {self.run_time.strftime('%H:%M')} ({'Aktif' if self.is_active else 'Nonaktif'})"
