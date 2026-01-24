from django.shortcuts import render, redirect, get_object_or_404
from django.core.paginator import Paginator
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from apps.hrd.models import Izin, Karyawan
from apps.karyawan.forms import IzinForm
from apps.authentication.models import User
from notifications.signals import notify
from datetime import date, timedelta

@login_required
def izin_view(request):
    karyawan = get_object_or_404(Karyawan, user=request.user)
    
    if request.method == 'POST':
        form = IzinForm(request.POST, request.FILES, karyawan=karyawan)
        if form.is_valid():
            izin = form.save(commit=False)
            izin.id_karyawan = karyawan
            izin.save()

            # Kirim notifikasi ke HRD
            hr_users = User.objects.filter(role='HRD')
            notify.send(
                sender=request.user,
                recipient=hr_users,
                verb="mengajukan izin",
                description=f"{karyawan.nama} mengajukan {izin.get_jenis_izin_display()} untuk tanggal {izin.tanggal_izin}",
                target=izin,
                data={"url": "/hrd/approval-izin/"}
            )

            messages.success(request, "Pengajuan izin berhasil dikirim.")
            return redirect('pengajuan_izin')
    else:
        form = IzinForm(karyawan=karyawan)
    
    # Calculate izin sakit count for current month
    today = date.today()
    first_day = today.replace(day=1)
    if today.month == 12:
        last_day = today.replace(year=today.year + 1, month=1, day=1) - timedelta(days=1)
    else:
        last_day = today.replace(month=today.month + 1, day=1) - timedelta(days=1)
    
    izin_sakit_count = Izin.objects.filter(
        id_karyawan=karyawan,
        jenis_izin='sakit',
        tanggal_izin__gte=first_day,
        tanggal_izin__lte=last_day
    ).count()
    
    riwayat = Izin.objects.filter(id_karyawan=karyawan).order_by('-created_at')
    
    # paginasi
    paginator = Paginator(riwayat, 10)
    page_number = request.GET.get('page')
    riwayat = paginator.get_page(page_number)
    
    context = {
        'form': form,
        'riwayat': riwayat,
        'izin_sakit_count': izin_sakit_count,
        'izin_sakit_remaining': max(0, 3 - izin_sakit_count)
    }
    
    return render(request, 'karyawan/pengajuan_izin.html', context)

@login_required
def hapus_izin_view(request, id):
    karyawan = get_object_or_404(Karyawan, user=request.user)
    izin = get_object_or_404(Izin, id=id, id_karyawan=karyawan)

    if izin.status == 'menunggu':
        izin.delete()
        messages.success(request, "Pengajuan izin berhasil dihapus.")
    else:
        messages.warning(request, "Pengajuan yang sudah diproses tidak dapat dihapus.")

    return redirect('pengajuan_izin')
