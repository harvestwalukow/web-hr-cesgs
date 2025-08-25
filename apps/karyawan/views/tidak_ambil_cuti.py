from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.contrib import messages
from django.utils import timezone
from apps.hrd.models import TidakAmbilCuti, Karyawan, CutiBersama
from apps.karyawan.forms import TidakAmbilCutiForm
from datetime import datetime
from django.db.models import Q
from notifications.signals import notify
from apps.authentication.models import User

@login_required
def tidak_ambil_cuti_view(request):
    karyawan = get_object_or_404(Karyawan, user=request.user)

    # Ambil tahun saat ini
    tahun_sekarang = datetime.now().year

    # Ambil semua tanggal cuti bersama untuk tahun ini
    semua_cuti_bersama = CutiBersama.objects.filter(tanggal__year=tahun_sekarang)

    # Ambil tanggal yang sudah diajukan dan disetujui
    pengajuan_disetujui = TidakAmbilCuti.objects.filter(
        id_karyawan=karyawan,
        status='disetujui'
    ).values_list('tanggal__id', flat=True)

    # Filter daftar tanggal cuti bersama yang belum diajukan
    sisa_tanggal = semua_cuti_bersama.exclude(id__in=pengajuan_disetujui)
    
    # paginasi tabel pengajuan
    paginator = Paginator(sisa_tanggal, 10)  # 10 items per page
    page_number = request.GET.get('page')
    riwayat = paginator.get_page(page_number) 
    
    # Form khusus untuk pilihan tanggal
    if request.method == 'POST':
        form = TidakAmbilCutiForm(request.POST, request.FILES)
        form.fields['tanggal'].queryset = sisa_tanggal  # inject pilihan yang belum diajukan
        if form.is_valid():
            tidak_ambil = form.save(commit=False)
            tidak_ambil.id_karyawan = karyawan
            tidak_ambil.save()
            form.save_m2m()
            
            # Kirim notifikasi ke HRD
            hr_users = User.objects.filter(role='HRD')
            notify.send(
                sender=request.user,
                recipient=hr_users,
                verb="mengajukan tidak ambil cuti",
                description=f"{karyawan.nama} mengajukan tidak ambil cuti bersama",
                target=tidak_ambil,
                data={"url": "/hrd/approval-cuti/"}
            )
            
            messages.success(request, "Pengajuan berhasil dikirim.")
            return redirect('tidak_ambil_cuti')
    else:
        form = TidakAmbilCutiForm()
        form.fields['tanggal'].queryset = sisa_tanggal

    riwayat = TidakAmbilCuti.objects.filter(id_karyawan=karyawan).order_by('-tanggal_pengajuan')
    return render(request, 'karyawan/tidak_ambil_cuti.html', {
        'form': form,
        'riwayat': riwayat,
        'tahun_sekarang': tahun_sekarang,
    })

@login_required
def hapus_tidak_ambil_cuti_view(request, id):
    karyawan = get_object_or_404(Karyawan, user=request.user)
    pengajuan = get_object_or_404(TidakAmbilCuti, id=id, id_karyawan=karyawan)

    if pengajuan.status == 'menunggu':
        pengajuan.delete()
        messages.success(request, "Pengajuan berhasil dihapus.")
    else:
        messages.warning(request, "Pengajuan yang sudah diproses tidak dapat dihapus.")

    return redirect('tidak_ambil_cuti')
