from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from apps.authentication.decorators import role_required
from apps.hrd.models import Karyawan, CutiBersama, Izin
from apps.absensi.models import AbsensiMagang
from django.contrib import messages
from django.http import JsonResponse
from datetime import datetime, timedelta, date
from pytanggalmerah import TanggalMerah
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.forms import PasswordChangeForm
from apps.profil.forms import ProfilForm
from apps.karyawan.forms import IzinForm
from apps.authentication.models import User
from notifications.signals import notify
from django.core.paginator import Paginator

@login_required
@role_required(['Magang', 'Part Time', 'Freelance', 'Project'])
def magang_dashboard(request):
    user = request.user
    try:
        karyawan = Karyawan.objects.get(user=user)
    except Karyawan.DoesNotExist:
        messages.error(request, "Data karyawan tidak ditemukan.")
        return redirect('home') # Atau halaman lain yang sesuai

    # Ambil data absensi terbaru (misal 5 data terakhir)
    daftar_absensi = AbsensiMagang.objects.filter(id_karyawan=karyawan).order_by('-tanggal', '-jam_masuk')[:5]

    # Hitung statistik absensi (8 jam fleksibel - hanya total hadir)
    total_absensi = AbsensiMagang.objects.filter(id_karyawan=karyawan).count()

    # --- Libur Nasional Terdekat (30 hari ke depan) - Konsisten dengan Dashboard Karyawan ---
    today = datetime.today()
    libur_terdekat = []
    tanggal_mulai = today.date()
    tanggal_sampai = tanggal_mulai + timedelta(days=30)

    for hari in range((tanggal_sampai - tanggal_mulai).days):
        tanggal = tanggal_mulai + timedelta(days=hari)
        
        if tanggal.weekday() == 6:
            continue  # Lewati hari Minggu

        t = TanggalMerah()
        t.set_date(str(tanggal.year), f"{tanggal.month:02d}", f"{tanggal.day:02d}")
        if t.check():
            for event in t.get_event():
                libur_terdekat.append({
                    "summary": event,
                    "date": tanggal
                })

    context = {
        'karyawan': karyawan,
        'daftar_absensi': daftar_absensi,
        'total_absensi': total_absensi,
        'libur_terdekat': libur_terdekat,
        'user': user,
    }
    return render(request, 'magang/index.html', context)

@login_required
@role_required(['Magang', 'Part Time', 'Freelance', 'Project'])
def edit_profile_magang(request):
    """View untuk edit profil magang"""
    user = request.user
    
    try:
        karyawan = Karyawan.objects.get(user=user)
    except Karyawan.DoesNotExist:
        messages.error(request, "Data karyawan tidak ditemukan.")
        return redirect('magang_dashboard')
    
    if request.method == 'POST':
        form = ProfilForm(request.POST, request.FILES, instance=karyawan)
        if form.is_valid():
            # Update data karyawan
            karyawan = form.save(commit=False)
            
            # Update email di User model jika ada perubahan
            if 'email' in form.cleaned_data:
                user.email = form.cleaned_data['email']
                user.save()
            
            karyawan.save()
            messages.success(request, 'Profil berhasil diperbarui!')
            return redirect('edit_profile_magang')
        else:
            messages.error(request, 'Terjadi kesalahan saat memperbarui profil.')
    else:
        # Pre-populate form dengan data yang ada
        initial_data = {
            'email': user.email,
        }
        form = ProfilForm(instance=karyawan, initial=initial_data)
    
    context = {
        'form': form,
        'karyawan': karyawan,
        'user': user,
        'title': 'Edit Profil Magang'
    }
    
    # Gunakan template yang sudah ada
    return render(request, 'magang/edit_profil.html', context)

@login_required
@role_required(['Magang', 'Part Time', 'Freelance', 'Project'])
def ubah_password_magang(request):
    """View untuk ubah password magang"""
    user = request.user
    
    try:
        karyawan = Karyawan.objects.get(user=user)
    except Karyawan.DoesNotExist:
        messages.error(request, "Data karyawan tidak ditemukan.")
        return redirect('magang_dashboard')
    
    if request.method == 'POST':
        form = PasswordChangeForm(user, request.POST)
        if form.is_valid():
            user = form.save()
            # Update session agar user tidak logout setelah ganti password
            update_session_auth_hash(request, user)
            messages.success(request, 'Password berhasil diubah!')
            return redirect('edit_profile_magang')  # Redirect ke halaman edit profil
        else:
            messages.error(request, 'Terjadi kesalahan saat mengubah password.')
            # Tampilkan form profil juga
            profil_form = ProfilForm(instance=karyawan, initial={'email': user.email})
            context = {
                'form': profil_form,
                'password_form': form,
                'karyawan': karyawan,
                'user': user,
                'title': 'Edit Profil Magang'
            }
            return render(request, 'magang/edit_profil.html', context)
    
    # Jika GET request, redirect ke edit profile
    return redirect('edit_profile_magang')

@login_required
@role_required(['Magang', 'Part Time', 'Freelance', 'Project'])
def calendar_events_magang(request):
    from datetime import date
    WFA_CUTOFF_DATE = date(2026, 1, 30)  # WFA labels only visible from this date onwards (30 Jan)
    
    events = []
    user = request.user
    
    try:
        karyawan = Karyawan.objects.get(user=user)
    except Karyawan.DoesNotExist:
        return JsonResponse(events, safe=False)
    
    today = datetime.now().date()
    start_date = today - timedelta(days=365)  # 1 tahun ke belakang
    end_date = today + timedelta(days=365)    # 1 tahun ke depan
    
    # Tanggal Merah dengan range yang konsisten
    current_date = start_date
    
    while current_date <= end_date:
        t = TanggalMerah()
        t.set_date(str(current_date.year), f"{current_date.month:02d}", f"{current_date.day:02d}")
        if t.check():
            for event in t.get_event():
                events.append({
                    "title": event,
                    "start": current_date.isoformat(),
                    "color": "#dc3545",
                    "allDay": True,
                    "description": f"Libur Nasional: {event}"
                })
        current_date += timedelta(days=1)
    
    # Tambahkan Cuti Bersama
    for cb in CutiBersama.objects.all():
        if cb.jenis == 'WFA':
            # Skip WFA labels before cutoff date
            if cb.tanggal < WFA_CUTOFF_DATE:
                continue
            title = f"WFA: {cb.keterangan}" if cb.keterangan else "WFA"
            color = "#36b9cc"  # Cyan for WFA
        else:
            title = f"Cuti Bersama: {cb.keterangan}" if cb.keterangan else "Cuti Bersama"
            color = "#6f42c1"

        events.append({
            "title": title,
            "start": cb.tanggal.isoformat(),
            "color": color,
            "allDay": True,
            "description": f"{cb.jenis} - {cb.keterangan or ''}"
        })
    
    # Add a debug event if no events are found
    if not events:
        events.append({
            "title": "Test Event - Hari Ini",
            "start": today.isoformat(),
            "color": "#28a745",
            "allDay": True,
            "description": "Event test untuk memastikan kalender berfungsi"
        })
    
    return JsonResponse(events, safe=False)


@login_required
@role_required(['Magang', 'Part Time', 'Freelance', 'Project'])
def izin_magang_view(request):
    """View untuk pengajuan dan riwayat izin magang"""
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
            return redirect('pengajuan_izin_magang')
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
    
    # Count izin pulang awal for current month
    izin_pulang_awal_count = Izin.objects.filter(
        id_karyawan=karyawan,
        jenis_izin='pulang_awal',
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
        'izin_sakit_remaining': max(0, 3 - izin_sakit_count),
        'izin_pulang_awal_count': izin_pulang_awal_count,
        'izin_pulang_awal_remaining': max(0, 3 - izin_pulang_awal_count)
    }
    
    return render(request, 'magang/pengajuan_izin.html', context)


@login_required
@role_required(['Magang', 'Part Time', 'Freelance', 'Project'])
def hapus_izin_magang_view(request, id):
    """Hapus pengajuan izin magang"""
    karyawan = get_object_or_404(Karyawan, user=request.user)
    izin = get_object_or_404(Izin, id=id, id_karyawan=karyawan)

    if izin.status == 'menunggu':
        izin.delete()
        messages.success(request, "Pengajuan izin berhasil dihapus.")
    else:
        messages.warning(request, "Pengajuan yang sudah diproses tidak dapat dihapus.")

    return redirect('pengajuan_izin_magang')

