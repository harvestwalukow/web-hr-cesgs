from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from apps.authentication.decorators import role_required
from apps.hrd.models import Karyawan
from apps.profil.forms import ProfilForm
from apps.absensi.models import AbsensiMagang
from datetime import datetime, time, timedelta
from pytanggalmerah import TanggalMerah
from django.contrib.auth import authenticate, update_session_auth_hash

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

    # Hitung statistik absensi
    total_absensi = AbsensiMagang.objects.filter(id_karyawan=karyawan).count()
    tepat_waktu_count = AbsensiMagang.objects.filter(id_karyawan=karyawan, status='Tepat waktu').count()
    hadir_count = AbsensiMagang.objects.filter(id_karyawan=karyawan, status='Hadir').count()
    terlambat_count = AbsensiMagang.objects.filter(id_karyawan=karyawan, status='Terlambat').count()
    tidak_hadir_count = AbsensiMagang.objects.filter(id_karyawan=karyawan, status='Tidak Hadir').count()

    context = {
        'karyawan': karyawan,
        'daftar_absensi': daftar_absensi,
        'total_absensi': total_absensi,
        'tepat_waktu_count': tepat_waktu_count,
        'hadir_count': hadir_count,
        'terlambat_count': terlambat_count,
        'tidak_hadir_count': tidak_hadir_count,
        'user': user, # Pastikan user juga diteruskan
    }
    return render(request, 'magang/index.html', context)

@login_required
@role_required(['Magang', 'Part Time', 'Freelance', 'Project'])
def calendar_events_magang(request):
    events = []
    user = request.user
    
    try:
        karyawan = Karyawan.objects.get(user=user)
    except Karyawan.DoesNotExist:
        return JsonResponse(events, safe=False)
    
    
    # Tanggal Merah
    today = datetime.now().date()
    end_date = today + timedelta(days=90)  # Tampilkan 3 bulan ke depan
    current_date = today - timedelta(days=30)  # Tampilkan 1 bulan ke belakang
    
    while current_date <= end_date:
        t = TanggalMerah()
        t.set_date(str(current_date.year), f"{current_date.month:02d}", f"{current_date.day:02d}")
        if t.check():
            for event in t.get_event():
                events.append({
                    "title": event,
                    "start": current_date.isoformat(),
                    "color": "#dc3545",
                    "allDay": True
                })
        current_date += timedelta(days=1)
    
    # Add a debug event if no events are found
    if not events:
        events.append({
            "title": "Belum ada data absensi",
            "start": today.isoformat(),
            "color": "#cccccc",
            "allDay": True
        })
    
    return JsonResponse(events, safe=False)

@login_required
@role_required(['Magang', 'Part Time', 'Freelance', 'Project'])
def edit_profil_magang(request):
    user = request.user

    try:
        karyawan = Karyawan.objects.get(user=user)
    except Karyawan.DoesNotExist:
        messages.error(request, "Profil karyawan belum dibuat. Silakan hubungi HRD.")
        return redirect('magang_dashboard')

    if request.method == 'POST':
        form = ProfilForm(request.POST, instance=karyawan, user=user)

        if form.is_valid():
            # Email tidak boleh diubah: abaikan perubahan email dari form
            form.cleaned_data.pop('email', None)

            # Simpan data ke Karyawan
            form.save()

            messages.success(request, 'Profil berhasil diperbarui.')
            return redirect('edit_profil_magang')
        else:
            messages.error(request, 'Terjadi kesalahan saat menyimpan profil.')
    else:
        form = ProfilForm(instance=karyawan, user=user)

    return render(request, 'magang/edit_profil.html', {
        'form': form,
        'karyawan': karyawan,
        'user': user,
    })


@role_required(['Magang', 'Part Time', 'Freelance', 'Project'])
def ubah_password_magang(request):
    """View untuk mengubah password magang"""
    if request.method == 'POST':
        old_password = request.POST.get('old_password')
        new_password1 = request.POST.get('new_password1')
        new_password2 = request.POST.get('new_password2')
        
        # Validasi password lama
        if not authenticate(username=request.user.email, password=old_password):
            messages.error(request, 'Password lama yang Anda masukkan salah.')
            return redirect('edit_profil_magang')
        
        # Validasi password baru
        if new_password1 != new_password2:
            messages.error(request, 'Password baru dan konfirmasi password tidak cocok.')
            return redirect('edit_profil_magang')
        
        if len(new_password1) < 8:
            messages.error(request, 'Password baru harus minimal 8 karakter.')
            return redirect('edit_profil_magang')
        
        # Update password
        user = request.user
        user.set_password(new_password1)
        user.save()
        
        # Update session agar user tidak logout
        update_session_auth_hash(request, user)
        
        messages.success(request, 'Password berhasil diubah.')
        return redirect('edit_profil_magang')
    
    return redirect('edit_profil_magang')
