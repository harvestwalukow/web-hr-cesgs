from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from apps.authentication.decorators import role_required
from apps.notifikasi.models import WhatsAppSchedule
from apps.absensi.helpers.whatsapp import (
    DEFAULT_CHECKIN_REMINDER,
    DEFAULT_OVERTIME_ALERT,
)
from django import forms


class WhatsAppScheduleForm(forms.ModelForm):
    class Meta:
        model = WhatsAppSchedule
        fields = ['schedule_type', 'run_time', 'message_template']
        widgets = {
            'schedule_type': forms.HiddenInput(),
            'run_time': forms.TimeInput(attrs={'type': 'time', 'class': 'form-control'}),
            'message_template': forms.Textarea(attrs={'class': 'form-control', 'rows': 8}),
        }


@login_required
@role_required(['HRD'])
def jadwal_whatsapp_view(request):
    daftar_jadwal = WhatsAppSchedule.objects.all().order_by('schedule_type')

    if request.method == 'POST':
        schedule_id = request.POST.get('schedule_id')
        if schedule_id:
            schedule = get_object_or_404(WhatsAppSchedule, pk=schedule_id)
            form = WhatsAppScheduleForm(request.POST, instance=schedule)
            if form.is_valid():
                form.save()
                messages.success(request, 'Jadwal berhasil disimpan.')
            else:
                messages.error(request, 'Ada kesalahan pada form.')
        return redirect('jadwal_whatsapp')

    return render(request, 'hrd/jadwal_whatsapp.html', {
        'daftar_jadwal': daftar_jadwal,
    })


@login_required
@role_required(['HRD'])
def jadwal_whatsapp_detail_ajax(request, schedule_id):
    """Return schedule detail as JSON for edit modal."""
    schedule = get_object_or_404(WhatsAppSchedule, pk=schedule_id)
    message = schedule.message_template
    if not message:
        defaults = {
            'checkin_reminder': DEFAULT_CHECKIN_REMINDER,
            'overtime_alert': DEFAULT_OVERTIME_ALERT,
        }
        message = defaults.get(schedule.schedule_type, '')
    return JsonResponse({
        'id': schedule.id,
        'schedule_type': schedule.schedule_type,
        'schedule_type_display': schedule.get_schedule_type_display(),
        'run_time': schedule.run_time.strftime('%H:%M'),
        'message_template': message,
    })


@login_required
@role_required(['HRD'])
@require_http_methods(['POST'])
def jadwal_whatsapp_toggle_ajax(request):
    try:
        schedule_id = request.POST.get('schedule_id')
        schedule = get_object_or_404(WhatsAppSchedule, pk=schedule_id)
        schedule.is_active = not schedule.is_active
        schedule.save()
        return JsonResponse({
            'success': True,
            'is_active': schedule.is_active,
        })
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)


@login_required
@role_required(['HRD'])
def jadwal_whatsapp_delete(request, schedule_id):
    schedule = get_object_or_404(WhatsAppSchedule, pk=schedule_id)
    schedule.delete()
    messages.success(request, 'Jadwal berhasil dihapus.')
    return redirect('jadwal_whatsapp')
