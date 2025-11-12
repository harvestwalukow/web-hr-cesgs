from django.shortcuts import render, redirect, get_object_or_404
from django.core.paginator import Paginator
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.shortcuts import render, get_object_or_404, redirect
from apps.hrd.models import Cuti, Karyawan, JatahCuti, DetailJatahCuti
from apps.karyawan.forms import CutiForm
from datetime import datetime
import calendar
from notifications.signals import notify
from apps.authentication.models import User

@login_required
def cuti_view(request):
    karyawan = get_object_or_404(Karyawan, user=request.user)

    #  Batasi hanya untuk HRD & Karyawan Tetap
    if karyawan.user.role not in ['HRD', 'Karyawan Tetap']:
        messages.error(request, "Anda tidak memiliki akses ke fitur pengajuan cuti.")
        return redirect('karyawan_dashboard')

    # Handle form
    if request.method == 'POST':
        form = CutiForm(request.POST, request.FILES, karyawan=karyawan)
        if form.is_valid():
            cuti = form.save(commit=False)
            cuti.id_karyawan = karyawan
            cuti.save()

            # Kirim notifikasi ke HRD
            notify.send(
                sender=request.user,
                recipient=User.objects.filter(role='HRD'),  # Semua user dengan role HRD
                verb=f"Pengajuan cuti baru",
                description=f"Pengajuan cuti baru dari {karyawan.nama} untuk tanggal {cuti.tanggal_mulai} sampai {cuti.tanggal_selesai}",
                target=cuti,
                data={"url": "/hrd/approval-cuti/"}
            )

            messages.success(request, "Pengajuan cuti berhasil dikirim.")
            return redirect('pengajuan_cuti')
    else:
        form = CutiForm(karyawan=karyawan)

    # Data riwayat
    riwayat = Cuti.objects.filter(id_karyawan=karyawan).order_by('-created_at')

    #  Ambil tahun sekarang dan tahun yang dipilih dari parameter URL
    tahun_sekarang = timezone.now().year
    selected_year = int(request.GET.get('tahun', tahun_sekarang))
    bulan_sekarang = timezone.now().month
    
    # Ambil semua tahun yang tersedia untuk dropdown filter
    available_years = list(range(tahun_sekarang - 5, tahun_sekarang + 1))
    available_years.reverse()  # Urutkan dari tahun terbaru
    
    # Cek jatah cuti yang akan expired bulan ini (dari tahun lalu)
    tahun_lalu = tahun_sekarang - 1
    cuti_akan_expired = []
    
    # Cek jatah cuti tahun lalu yang belum dipakai dan bulannya = bulan sekarang
    jatah_tahun_lalu = JatahCuti.objects.filter(karyawan=karyawan, tahun=tahun_lalu).first()
    if jatah_tahun_lalu:
        detail_akan_expired = DetailJatahCuti.objects.filter(
            jatah_cuti=jatah_tahun_lalu,
            tahun=tahun_lalu,
            bulan=bulan_sekarang,
            dipakai=False
        )
        
        for detail in detail_akan_expired:
            cuti_akan_expired.append({
                'bulan': calendar.month_name[detail.bulan],
                'tahun': tahun_lalu
            })

    #  Ambil jatah cuti tahunan berdasarkan tahun yang dipilih
    jatah = JatahCuti.objects.filter(karyawan=karyawan, tahun=selected_year).first()
    
    # paginasi
    paginator = Paginator(riwayat, 10)  # Show 10 rules per page
    page_number = request.GET.get('page')
    riwayat = paginator.get_page(page_number)  # Get the current page's rules

    if jatah:
        total_jatah_cuti = jatah.total_cuti
        sisa_cuti = jatah.sisa_cuti
        cuti_terpakai = total_jatah_cuti - sisa_cuti
        persentase_penggunaan = round((cuti_terpakai / total_jatah_cuti) * 100) if total_jatah_cuti else 0
    else:
        total_jatah_cuti = 0
        sisa_cuti = 0
        cuti_terpakai = 0
        persentase_penggunaan = 0

    return render(request, 'karyawan/pengajuan_cuti.html', {
        'form': form,
        'riwayat': riwayat,
        'tahun_sekarang': tahun_sekarang,
        'selected_year': selected_year,
        'available_years': available_years,
        'total_jatah_cuti': total_jatah_cuti,
        'sisa_cuti': sisa_cuti,
        'cuti_terpakai': cuti_terpakai,
        'persentase_penggunaan': persentase_penggunaan,
        'cuti_akan_expired': cuti_akan_expired,  # Tambahkan data cuti yang akan expired
    })


@login_required
def hapus_cuti_view(request, id):
    karyawan = get_object_or_404(Karyawan, user=request.user)

    #  Batasi hanya role yang diizinkan menghapus
    if karyawan.user.role not in ['HRD', 'Karyawan Tetap']:
        messages.error(request, "Anda tidak memiliki akses untuk menghapus pengajuan cuti.")
        return redirect('pengajuan_cuti')

    cuti = get_object_or_404(Cuti, id=id, id_karyawan=karyawan)

    if cuti.status == 'menunggu':
        cuti.delete()
        messages.success(request, "Pengajuan cuti berhasil dihapus.")
    else:
        messages.warning(request, "Pengajuan yang sudah diproses tidak dapat dihapus.")

    return redirect('pengajuan_cuti')
