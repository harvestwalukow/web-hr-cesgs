from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.http import HttpResponse
from django.db.models import Q
from apps.hrd.models import Cuti, Karyawan, JatahCuti, DetailJatahCuti, CutiBersama
from apps.hrd.utils.jatah_cuti import proses_cuti_hangus  # Tambahkan import ini
import calendar
from datetime import datetime, date
import xlwt
from io import BytesIO

@login_required
def riwayat_cuti_detail_view(request):
    """View untuk menampilkan detail riwayat cuti karyawan per tahun."""
    karyawan = get_object_or_404(Karyawan, user=request.user)

    # Batasi hanya untuk HRD & Karyawan Tetap
    if karyawan.user.role not in ['HRD', 'Karyawan Tetap']:
        messages.error(request, "Anda tidak memiliki akses ke halaman ini.")
        return redirect('karyawan_dashboard')

    # Ambil tahun dari parameter GET, default tahun sekarang
    tahun_dipilih = request.GET.get('tahun', timezone.now().year)
    try:
        tahun_dipilih = int(tahun_dipilih)
    except (ValueError, TypeError):
        tahun_dipilih = timezone.now().year

    # TAMBAHKAN: Proses cuti hangus sebelum menampilkan data
    proses_cuti_hangus(karyawan, timezone.now().year)
    
    # Ambil data jatah cuti untuk tahun yang dipilih
    jatah_cuti = JatahCuti.objects.filter(karyawan=karyawan, tahun=tahun_dipilih).first()
    
    # Ambil detail jatah cuti per bulan
    detail_jatah_cuti = []
    if jatah_cuti:
        for bulan in range(1, 13):
            detail = DetailJatahCuti.objects.filter(
                jatah_cuti=jatah_cuti,
                tahun=tahun_dipilih,
                bulan=bulan
            ).first()
            
            # Cek apakah ada cuti bersama di bulan ini
            cuti_bersama_bulan = CutiBersama.objects.filter(
                tanggal__year=tahun_dipilih,
                tanggal__month=bulan
            )
            
            detail_jatah_cuti.append({
                'bulan': bulan,
                'nama_bulan': calendar.month_name[bulan],
                'jatah_tersedia': 1 if not detail or not detail.dipakai else 0,
                'cuti_diambil': 1 if detail and detail.dipakai else 0,
                'sisa': 0 if detail and detail.dipakai else 1,
                'keterangan': detail.keterangan if detail else '',
                'is_cuti_bersama': any('cuti bersama' in detail.keterangan.lower() if detail and detail.keterangan else False for _ in [1]),
                'cuti_bersama_dates': list(cuti_bersama_bulan.values_list('tanggal', 'keterangan'))
            })

    # Ambil riwayat cuti yang disetujui untuk tahun ini
    riwayat_cuti = Cuti.objects.filter(
        id_karyawan=karyawan,
        status='disetujui',
        tanggal_mulai__year=tahun_dipilih
    ).order_by('tanggal_mulai')

    # Hitung statistik
    total_jatah = jatah_cuti.total_cuti if jatah_cuti else 12
    total_digunakan = sum(1 for detail in detail_jatah_cuti if detail['cuti_diambil'])
    total_sisa = total_jatah - total_digunakan
    
    # Cek cuti yang akan hangus (dari tahun sebelumnya)
    tahun_sebelumnya = tahun_dipilih - 1
    cuti_akan_hangus = []
    if tahun_dipilih == timezone.now().year:  # Hanya tampilkan untuk tahun sekarang
        jatah_tahun_lalu = JatahCuti.objects.filter(karyawan=karyawan, tahun=tahun_sebelumnya).first()
        if jatah_tahun_lalu:
            detail_akan_hangus = DetailJatahCuti.objects.filter(
                jatah_cuti=jatah_tahun_lalu,
                tahun=tahun_sebelumnya,
                bulan__lte=timezone.now().month,
                dipakai=False
            )
            
            for detail in detail_akan_hangus:
                cuti_akan_hangus.append({
                    'bulan': calendar.month_name[detail.bulan],
                    'tahun': tahun_sebelumnya
                })

    # Ambil daftar tahun yang tersedia untuk filter
    tahun_tersedia = JatahCuti.objects.filter(karyawan=karyawan).values_list('tahun', flat=True).distinct().order_by('-tahun')
    
    # Jika tidak ada data, tambahkan tahun sekarang
    if not tahun_tersedia:
        tahun_tersedia = [timezone.now().year]

    context = {
        'karyawan': karyawan,
        'tahun_dipilih': tahun_dipilih,
        'tahun_tersedia': tahun_tersedia,
        'jatah_cuti': jatah_cuti,
        'detail_jatah_cuti': detail_jatah_cuti,
        'riwayat_cuti': riwayat_cuti,
        'total_jatah': total_jatah,
        'total_digunakan': total_digunakan,
        'total_sisa': total_sisa,
        'persentase_penggunaan': round((total_digunakan / total_jatah) * 100) if total_jatah else 0,
        'cuti_akan_hangus': cuti_akan_hangus,
    }

    return render(request, 'karyawan/riwayat_cuti_detail.html', context)

@login_required
def export_riwayat_cuti_excel(request):
    """Export riwayat cuti ke Excel."""
    karyawan = get_object_or_404(Karyawan, user=request.user)

    # Batasi hanya untuk HRD & Karyawan Tetap
    if karyawan.user.role not in ['HRD', 'Karyawan Tetap']:
        messages.error(request, "Anda tidak memiliki akses ke fitur ini.")
        return redirect('karyawan_dashboard')

    # Ambil tahun dari parameter GET
    tahun_dipilih = request.GET.get('tahun', timezone.now().year)
    try:
        tahun_dipilih = int(tahun_dipilih)
    except (ValueError, TypeError):
        tahun_dipilih = timezone.now().year

    # Buat workbook Excel
    response = HttpResponse(content_type='application/ms-excel')
    response['Content-Disposition'] = f'attachment; filename="Riwayat_Cuti_{karyawan.nama}_{tahun_dipilih}.xls"'

    wb = xlwt.Workbook(encoding='utf-8')
    ws = wb.add_sheet(f'Riwayat Cuti {tahun_dipilih}')

    # Style untuk header
    header_style = xlwt.XFStyle()
    header_font = xlwt.Font()
    header_font.bold = True
    header_style.font = header_font

    # Header informasi
    ws.write(0, 0, 'RIWAYAT CUTI TAHUNAN', header_style)
    ws.write(1, 0, f'Nama: {karyawan.nama}')
    ws.write(2, 0, f'Tahun: {tahun_dipilih}')
    ws.write(3, 0, f'Tanggal Export: {timezone.now().strftime("%d/%m/%Y %H:%M")}')

    # Header tabel detail per bulan
    row_num = 6
    ws.write(row_num, 0, 'DETAIL PENGGUNAAN CUTI PER BULAN', header_style)
    row_num += 2

    columns = ['Bulan', 'Jatah Tersedia', 'Cuti Diambil', 'Sisa', 'Keterangan']
    for col_num, column_title in enumerate(columns):
        ws.write(row_num, col_num, column_title, header_style)

    # Data detail per bulan
    jatah_cuti = JatahCuti.objects.filter(karyawan=karyawan, tahun=tahun_dipilih).first()
    if jatah_cuti:
        for bulan in range(1, 13):
            row_num += 1
            detail = DetailJatahCuti.objects.filter(
                jatah_cuti=jatah_cuti,
                tahun=tahun_dipilih,
                bulan=bulan
            ).first()
            
            ws.write(row_num, 0, calendar.month_name[bulan])
            ws.write(row_num, 1, 1 if not detail or not detail.dipakai else 0)
            ws.write(row_num, 2, 1 if detail and detail.dipakai else 0)
            ws.write(row_num, 3, 0 if detail and detail.dipakai else 1)
            ws.write(row_num, 4, detail.keterangan if detail else '')

    # Header tabel riwayat cuti
    row_num += 3
    ws.write(row_num, 0, 'RIWAYAT PENGAJUAN CUTI', header_style)
    row_num += 2

    cuti_columns = ['Tanggal Pengajuan', 'Jenis Cuti', 'Tanggal Mulai', 'Tanggal Selesai', 'Status', 'Keterangan HR']
    for col_num, column_title in enumerate(cuti_columns):
        ws.write(row_num, col_num, column_title, header_style)

    # Data riwayat cuti
    riwayat_cuti = Cuti.objects.filter(
        id_karyawan=karyawan,
        tanggal_mulai__year=tahun_dipilih
    ).order_by('tanggal_mulai')

    for cuti in riwayat_cuti:
        row_num += 1
        ws.write(row_num, 0, cuti.tanggal_pengajuan.strftime('%d/%m/%Y'))
        ws.write(row_num, 1, cuti.get_jenis_cuti_display())
        ws.write(row_num, 2, cuti.tanggal_mulai.strftime('%d/%m/%Y'))
        ws.write(row_num, 3, cuti.tanggal_selesai.strftime('%d/%m/%Y'))
        ws.write(row_num, 4, cuti.get_status_display())
        ws.write(row_num, 5, cuti.feedback_hr or '')

    wb.save(response)
    return response