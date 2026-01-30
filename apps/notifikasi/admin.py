from django.contrib import admin
from .models import WhatsAppLog


@admin.register(WhatsAppLog)
class WhatsAppLogAdmin(admin.ModelAdmin):
    """Admin interface untuk WhatsApp Log"""
    list_display = [
        'karyawan', 
        'notification_type', 
        'phone_number', 
        'status', 
        'sent_at'
    ]
    list_filter = ['notification_type', 'status', 'sent_at']
    search_fields = ['karyawan__nama', 'phone_number', 'message']
    readonly_fields = ['sent_at', 'fonnte_response']
    date_hierarchy = 'sent_at'
    
    fieldsets = (
        ('Informasi Penerima', {
            'fields': ('karyawan', 'phone_number')
        }),
        ('Detail Notifikasi', {
            'fields': ('notification_type', 'message', 'status')
        }),
        ('Response API', {
            'fields': ('fonnte_response', 'sent_at'),
            'classes': ('collapse',)
        }),
    )
