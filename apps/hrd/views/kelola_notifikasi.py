"""
Kelola Notifikasi - Reminder check-in dan overtime via Web Push.
Pesan notifikasi hardcoded di cron.
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from apps.authentication.decorators import role_required
from apps.notifikasi.models import ReminderSchedule
from django import forms


class ReminderScheduleForm(forms.ModelForm):
    class Meta:
        model = ReminderSchedule
        fields = ['schedule_type', 'run_time']
        widgets = {
            'schedule_type': forms.HiddenInput(),
            'run_time': forms.TimeInput(attrs={'type': 'time', 'class': 'form-control'}),
        }


@login_required
@role_required(['HRD'])
def kelola_notifikasi_view(request):
    daftar_jadwal = ReminderSchedule.objects.all().order_by('schedule_type')

    if request.method == 'POST':
        schedule_id = request.POST.get('schedule_id')
        if schedule_id:
            schedule = get_object_or_404(ReminderSchedule, pk=schedule_id)
            form = ReminderScheduleForm(request.POST, instance=schedule)
            if form.is_valid():
                obj = form.save(commit=False)
                # Tipe checkout: jam tetap tidak dipakai (cek per menit berdasarkan durasi kerja)
                if schedule.schedule_type == 'checkout_reminder':
                    obj.run_time = schedule.run_time
                obj.save()
                messages.success(request, 'Jadwal berhasil disimpan.')
            else:
                messages.error(request, 'Ada kesalahan pada form.')
        return redirect('kelola_notifikasi')

    return render(request, 'hrd/kelola_notifikasi.html', {
        'daftar_jadwal': daftar_jadwal,
    })


@login_required
@role_required(['HRD'])
def kelola_notifikasi_detail_ajax(request, schedule_id):
    """Return schedule detail as JSON for edit modal."""
    schedule = get_object_or_404(ReminderSchedule, pk=schedule_id)
    return JsonResponse({
        'id': schedule.id,
        'schedule_type': schedule.schedule_type,
        'schedule_type_display': schedule.get_schedule_type_display(),
        'run_time': schedule.run_time.strftime('%H:%M'),
        'needs_run_time': schedule.schedule_type != 'checkout_reminder',
    })


@login_required
@role_required(['HRD'])
@require_http_methods(['POST'])
def kelola_notifikasi_toggle_ajax(request):
    try:
        schedule_id = request.POST.get('schedule_id')
        schedule = get_object_or_404(ReminderSchedule, pk=schedule_id)
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
def kelola_notifikasi_delete(request, schedule_id):
    schedule = get_object_or_404(ReminderSchedule, pk=schedule_id)
    schedule.delete()
    messages.success(request, 'Jadwal berhasil dihapus.')
    return redirect('kelola_notifikasi')
