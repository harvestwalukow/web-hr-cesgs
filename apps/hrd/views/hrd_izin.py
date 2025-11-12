from django.shortcuts import render, redirect, get_object_or_404
from django.core.paginator import Paginator
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponse
from apps.hrd.models import Izin
from apps.authentication.models import User
from notifications.signals import notify
import openpyxl

@login_required
def approval_izin_view(request):
    if request.user.role != 'HRD':
        messages.error(request, "Anda tidak memiliki akses ke halaman ini.")
        return redirect('karyawan_dashboard')

    # Tabel pengajuan yang masih menunggu
    daftar_izin = Izin.objects.filter(status='menunggu').order_by('-tanggal_pengajuan')
    
    # paginasi tabel pengajuan
    paginator = Paginator(daftar_izin, 10)  # 10 items per page
    page_number = request.GET.get('page')
    daftar_izin = paginator.get_page(page_number)  # Get the current page's items

    # Filter untuk riwayat
    riwayat_izin = Izin.objects.exclude(status='menunggu')
    keyword = request.GET.get('nama')
    tahun = request.GET.get('tahun')

    if keyword:
        riwayat_izin = riwayat_izin.filter(id_karyawan__nama__icontains=keyword)
    if tahun:
        riwayat_izin = riwayat_izin.filter(tanggal_izin__year=tahun)

    riwayat_izin = riwayat_izin.order_by('-tanggal_pengajuan')
    
    # paginasi tabel riwayat
    paginator = Paginator(riwayat_izin, 10)  # 10 items per page
    page_number = request.GET.get('page')
    riwayat_izin = paginator.get_page(page_number)  # Get the current page's items

    # 📝 Form approval
    if request.method == 'POST':
        izin_id = request.POST.get('izin_id')
        aksi = request.POST.get('aksi')
        izin = get_object_or_404(Izin, id=izin_id)

        # Di dalam fungsi approval_izin_view, saat memproses POST request:
        
        if aksi in ['disetujui', 'ditolak']:
            izin.status = aksi
            izin.approval = request.user
        
            # Kirim notifikasi ke karyawan
            notify.send(
                sender=request.user,
                recipient=izin.id_karyawan.user,
                verb=f"izin {aksi}",
                description=f"Pengajuan {izin.get_jenis_izin_display()} Anda untuk tanggal {izin.tanggal_izin} telah {aksi}",
                target=izin,
                data={"url": "/karyawan/pengajuan-izin/"}
            )
            file_persetujuan = request.FILES.get('file_persetujuan')
            if file_persetujuan:
                izin.file_persetujuan = file_persetujuan
            izin.save()
            messages.success(request, f"Izin berhasil {aksi}.")

        elif aksi == 'ditolak':
            alasan = request.POST.get('feedback_hr', '').strip()
            izin.status = 'ditolak'
            izin.approval = request.user
            izin.feedback_hr = alasan or "Tidak ada alasan diberikan."
            izin.save()
            messages.success(request, "Izin berhasil ditolak.")

        return redirect('approval_izin')

    return render(request, 'hrd/approval_izin.html', {
        'daftar_izin': daftar_izin,
        'riwayat_izin': riwayat_izin,
    })

@login_required
def export_riwayat_izin_excel(request):
    if request.user.role != 'HRD':
        return HttpResponse("Forbidden", status=403)

    riwayat = Izin.objects.exclude(status='menunggu')
    keyword = request.GET.get('nama')
    tahun = request.GET.get('tahun')

    if keyword:
        riwayat = riwayat.filter(id_karyawan__nama__icontains=keyword)
    if tahun:
        riwayat = riwayat.filter(tanggal_izin__year=tahun)

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Riwayat Izin"

    ws.append(["Nama", "Jenis Izin", "Tanggal", "Alasan", "Status", "Disetujui Oleh"])

    for i in riwayat:
        ws.append([
            i.id_karyawan.nama,
            i.get_jenis_izin_display(),
            i.tanggal_izin.strftime('%Y-%m-%d'),
            i.alasan,
            i.status,
            i.approval.get_full_name() if i.approval else '-'
        ])

    response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = 'attachment; filename=riwayat_izin.xlsx'
    wb.save(response)
    return response
