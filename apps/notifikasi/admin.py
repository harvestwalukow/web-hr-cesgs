from django.contrib import admin
from .models import ReminderSchedule


@admin.register(ReminderSchedule)
class ReminderScheduleAdmin(admin.ModelAdmin):
    list_display = ['schedule_type', 'run_time', 'is_active', 'last_run_date', 'updated_at']
    list_editable = ['is_active']
    list_filter = ['is_active', 'schedule_type']
