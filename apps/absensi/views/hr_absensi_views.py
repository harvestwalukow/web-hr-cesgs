import pandas as pd
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator
from django.http import HttpResponse
from django.db.models import Count, Q, F
from apps.authentication.decorators import role_required
from apps.absensi.models import AbsensiMagang
from apps.hrd.models import Karyawan
from apps.authentication.models import User
from datetime import datetime, timedelta
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side


def calculate_work_duration(jam_masuk, jam_pulang):
    """Menghitung durasi kerja dalam jam dari jam masuk dan pulang"""
    if not jam_masuk or not jam_pulang:
        return None
    
    # Combine with a dummy date for calculation
    today = datetime.today().date()
    start = datetime.combine(today, jam_masuk)
    end = datetime.combine(today, jam_pulang)
    
    # Handle cases where end time is before start (shouldn't happen but just in case)
    if end < start:
        return None
    
    duration = (end - start).total_seconds() / 3600
    return round(duration, 1)


@login_required
@role_required(['HRD'])
def riwayat_absensi_magang_hr(request):
    """Dashboard Riwayat Absensi untuk HR - Control Center Kehadiran"""
    
    # Get today's date for dashboard stats
    today = datetime.now().date()
    
    # ============================================
    # DASHBOARD STATISTICS
    # ============================================
    
    # Total karyawan aktif
    total_karyawan_aktif = Karyawan.objects.filter(status_keaktifan='Aktif').count()
    
    # Absensi hari ini
    absensi_hari_ini = AbsensiMagang.objects.filter(tanggal=today).select_related('id_karyawan', 'id_karyawan__user')
    
    sudah_absen_hari_ini = absensi_hari_ini.count()
    wfo_hari_ini = absensi_hari_ini.filter(keterangan='WFO').count()
    wfh_hari_ini = absensi_hari_ini.filter(keterangan='WFH').count()
    
    # Karyawan yang belum absen pulang (sudah masuk tapi belum pulang)
    belum_pulang = absensi_hari_ini.filter(jam_masuk__isnull=False, jam_pulang__isnull=True)
    belum_pulang_count = belum_pulang.count()
    belum_pulang_list = list(belum_pulang.values_list('id_karyawan__nama', flat=True)[:5])
    
    # Karyawan aktif yang belum absen masuk sama sekali hari ini
    karyawan_sudah_absen_ids = absensi_hari_ini.values_list('id_karyawan_id', flat=True)
    belum_masuk = Karyawan.objects.filter(
        status_keaktifan='Aktif'
    ).exclude(id__in=karyawan_sudah_absen_ids)
    belum_masuk_count = belum_masuk.count()
    belum_masuk_list = list(belum_masuk.values_list('nama', flat=True)[:5])
    
    # ============================================
    # WORK DURATION INSIGHTS
    # ============================================
    
    # Query absensi yang sudah pulang hari ini (untuk hitung durasi)
    absensi_selesai = absensi_hari_ini.filter(jam_masuk__isnull=False, jam_pulang__isnull=False)
    
    # Hitung rata-rata durasi kerja
    total_durasi = 0
    durasi_list = []
    durasi_kurang_8_jam = []
    potensi_lembur = []
    
    for absensi in absensi_selesai:
        durasi = calculate_work_duration(absensi.jam_masuk, absensi.jam_pulang)
        if durasi:
            durasi_list.append(durasi)
            total_durasi += durasi
            
            if durasi < 8:
                durasi_kurang_8_jam.append({
                    'nama': absensi.id_karyawan.nama,
                    'durasi': durasi
                })
            elif durasi >= 10:
                potensi_lembur.append({
                    'nama': absensi.id_karyawan.nama,
                    'durasi': durasi
                })
    
    # Check for employees still working (belum pulang) with 10+ hours
    for absensi in belum_pulang:
        if absensi.jam_masuk:
            jam_masuk_dt = datetime.combine(today, absensi.jam_masuk)
            sekarang = datetime.now()
            durasi = (sekarang - jam_masuk_dt).total_seconds() / 3600
            if durasi >= 10:
                potensi_lembur.append({
                    'nama': absensi.id_karyawan.nama,
                    'durasi': round(durasi, 1),
                    'masih_kerja': True
                })
    
    rata_rata_durasi = round(total_durasi / len(durasi_list), 1) if durasi_list else 0
    
    # ============================================
    # FILTERS
    # ============================================
    
    nama = request.GET.get('nama', '')
    bulan = request.GET.get('bulan')
    tahun = request.GET.get('tahun')
    role = request.GET.get('role', '')
    keterangan = request.GET.get('keterangan', '')
    tanggal = request.GET.get('tanggal', '')
    tanggal_mulai = request.GET.get('tanggal_mulai')
    tanggal_selesai = request.GET.get('tanggal_selesai')
    
    # Buat query dasar dengan join ke User untuk mendapat role
    absensi_query = AbsensiMagang.objects.all().select_related('id_karyawan', 'id_karyawan__user')
    
    # Terapkan filter
    if nama:
        absensi_query = absensi_query.filter(id_karyawan__nama__icontains=nama)
    
    if bulan and bulan.isdigit():
        absensi_query = absensi_query.filter(tanggal__month=int(bulan))
    
    if tahun and tahun.isdigit():
        absensi_query = absensi_query.filter(tanggal__year=int(tahun))
    
    if role:
        absensi_query = absensi_query.filter(id_karyawan__user__role=role)
    
    if keterangan:
        absensi_query = absensi_query.filter(keterangan=keterangan)
    
    if tanggal:
        try:
            tanggal_parsed = datetime.strptime(tanggal, '%Y-%m-%d').date()
            absensi_query = absensi_query.filter(tanggal=tanggal_parsed)
        except ValueError:
            messages.error(request, 'Format tanggal tidak valid')
    
    if tanggal_mulai:
        try:
            tanggal_mulai_parsed = datetime.strptime(tanggal_mulai, '%Y-%m-%d').date()
            absensi_query = absensi_query.filter(tanggal__gte=tanggal_mulai_parsed)
        except ValueError:
            messages.error(request, 'Format tanggal mulai tidak valid')
    
    if tanggal_selesai:
        try:
            tanggal_selesai_parsed = datetime.strptime(tanggal_selesai, '%Y-%m-%d').date()
            absensi_query = absensi_query.filter(tanggal__lte=tanggal_selesai_parsed)
        except ValueError:
            messages.error(request, 'Format tanggal selesai tidak valid')
    
    # Sorting
    sort_by = request.GET.get('sort_by', '-tanggal')
    absensi_query = absensi_query.order_by(sort_by)
    
    # Calculate duration for each attendance record
    absensi_with_duration = []
    for absensi in absensi_query:
        durasi = calculate_work_duration(absensi.jam_masuk, absensi.jam_pulang)
        absensi.durasi_kerja = durasi
        absensi_with_duration.append(absensi)
    
    # Pagination
    paginator = Paginator(absensi_with_duration, 15)  # 15 items per halaman
    page = request.GET.get('page')
    absensi_list = paginator.get_page(page)
    
    # ============================================
    # FILTER OPTIONS
    # ============================================
    
    months = [
        (1, 'Januari'), (2, 'Februari'), (3, 'Maret'), (4, 'April'),
        (5, 'Mei'), (6, 'Juni'), (7, 'Juli'), (8, 'Agustus'),
        (9, 'September'), (10, 'Oktober'), (11, 'November'), (12, 'Desember')
    ]
    
    current_year = datetime.now().year
    years = range(current_year - 3, current_year + 2)
    
    # Role choices dari model User
    role_choices = User.ROLE_CHOICES
    
    # Keterangan choices
    keterangan_choices = [
        ('WFO', 'WFO'),
        ('WFH', 'WFH'),
        ('Izin Telat', 'Izin Telat'),
        ('Izin Sakit', 'Izin Sakit')
    ]
    
    # ============================================
    # PIVOT TABLE (untuk rekap bulanan)
    # ============================================
    
    pivot_headers = []
    pivot_rows = []
    
    if bulan and bulan.isdigit() and tahun and tahun.isdigit():
        if absensi_query.exists():
            pivot_data = list(absensi_query.values('id_karyawan__nama', 'keterangan'))
            df = pd.DataFrame(pivot_data)
            
            if not df.empty and 'id_karyawan__nama' in df.columns and 'keterangan' in df.columns:
                pivot_table = pd.pivot_table(
                    df,
                    index='id_karyawan__nama',
                    columns='keterangan',
                    aggfunc='size',
                    fill_value=0
                ).reset_index()
                
                all_keterangan = ['WFO', 'WFH']
                for ket in all_keterangan:
                    if ket not in pivot_table.columns:
                        pivot_table[ket] = 0
                
                numeric_columns = [col for col in pivot_table.columns if col != 'id_karyawan__nama']
                pivot_table['Total'] = pivot_table[numeric_columns].sum(axis=1)
                
                column_order = ['id_karyawan__nama'] + all_keterangan + ['Total']
                pivot_table = pivot_table.reindex(columns=column_order, fill_value=0)
                
                pivot_headers = ['Nama Karyawan'] + all_keterangan + ['Total']
                pivot_rows = [list(row) for _, row in pivot_table.iterrows()]
    
    # ============================================
    # CONTEXT
    # ============================================
    
    context = {
        # Dashboard stats
        'today': today,
        'total_karyawan_aktif': total_karyawan_aktif,
        'sudah_absen_hari_ini': sudah_absen_hari_ini,
        'wfo_hari_ini': wfo_hari_ini,
        'wfh_hari_ini': wfh_hari_ini,
        'belum_masuk_count': belum_masuk_count,
        'belum_masuk_list': belum_masuk_list,
        'belum_pulang_count': belum_pulang_count,
        'belum_pulang_list': belum_pulang_list,
        'rata_rata_durasi': rata_rata_durasi,
        'durasi_kurang_8_jam': durasi_kurang_8_jam,
        'potensi_lembur': potensi_lembur,
        
        # Table data
        'absensi_list': absensi_list,
        
        # Filter values
        'nama_filter': nama,
        'selected_month': int(bulan) if bulan and bulan.isdigit() else '',
        'selected_year': int(tahun) if tahun and tahun.isdigit() else '',
        'selected_role': role,
        'selected_keterangan': keterangan,
        'tanggal_filter': tanggal,
        'tanggal_mulai': tanggal_mulai,
        'tanggal_selesai': tanggal_selesai,
        'sort_by': sort_by,
        
        # Filter options
        'months': months,
        'years': years,
        'role_choices': role_choices,
        'keterangan_choices': keterangan_choices,
        
        # Pivot table
        'pivot_headers': pivot_headers,
        'pivot_rows': pivot_rows,
        
        # Page title
        'title': 'Riwayat Absensi'
    }
    
    return render(request, 'absensi/riwayat_absensi_magang_hr.html', context)


@login_required
@role_required(['HRD'])
def export_absensi_magang_excel(request):
    """Ekspor data absensi ke Excel dengan Role dan Durasi"""
    nama = request.GET.get('nama', '')
    bulan = request.GET.get('bulan')
    tahun = request.GET.get('tahun')
    role = request.GET.get('role', '')
    keterangan = request.GET.get('keterangan', '')
    tanggal_mulai = request.GET.get('tanggal_mulai')
    tanggal_selesai = request.GET.get('tanggal_selesai')
    
    # Buat query dasar
    absensi_query = AbsensiMagang.objects.all().select_related('id_karyawan', 'id_karyawan__user')
    
    # Terapkan filter
    if nama:
        absensi_query = absensi_query.filter(id_karyawan__nama__icontains=nama)
    
    if bulan and bulan.isdigit():
        absensi_query = absensi_query.filter(tanggal__month=int(bulan))
    
    if tahun and tahun.isdigit():
        absensi_query = absensi_query.filter(tanggal__year=int(tahun))
    
    if role:
        absensi_query = absensi_query.filter(id_karyawan__user__role=role)
    
    if keterangan:
        absensi_query = absensi_query.filter(keterangan=keterangan)
    
    if tanggal_mulai:
        try:
            tanggal_mulai = datetime.strptime(tanggal_mulai, '%Y-%m-%d').date()
            absensi_query = absensi_query.filter(tanggal__gte=tanggal_mulai)
        except ValueError:
            pass
    
    if tanggal_selesai:
        try:
            tanggal_selesai = datetime.strptime(tanggal_selesai, '%Y-%m-%d').date()
            absensi_query = absensi_query.filter(tanggal__lte=tanggal_selesai)
        except ValueError:
            pass
    
    absensi_query = absensi_query.order_by('-tanggal')
    
    # Buat workbook Excel
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Riwayat Absensi"
    
    # Style untuk header
    header_font = Font(bold=True, color="FFFFFF")
    header_fill = PatternFill(start_color="4472C4", end_color="4472C4", fill_type="solid")
    header_alignment = Alignment(horizontal="center", vertical="center")
    thin_border = Border(
        left=Side(style='thin'),
        right=Side(style='thin'),
        top=Side(style='thin'),
        bottom=Side(style='thin')
    )
    
    # Header
    headers = [
        "Nama Karyawan", "Role", "Tanggal", "Jam Masuk", "Jam Pulang", 
        "Durasi (Jam)", "Keterangan", "Lokasi Masuk", "Lokasi Pulang"
    ]
    
    for col, header in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col, value=header)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = header_alignment
        cell.border = thin_border
    
    # Data
    for row_num, absensi in enumerate(absensi_query, 2):
        durasi = calculate_work_duration(absensi.jam_masuk, absensi.jam_pulang)
        role_name = absensi.id_karyawan.user.role if absensi.id_karyawan.user else "-"
        
        row_data = [
            absensi.id_karyawan.nama,
            role_name,
            absensi.tanggal.strftime("%Y-%m-%d"),
            absensi.jam_masuk.strftime("%H:%M:%S") if absensi.jam_masuk else "-",
            absensi.jam_pulang.strftime("%H:%M:%S") if absensi.jam_pulang else "-",
            durasi if durasi else "-",
            absensi.keterangan or "-",
            absensi.alamat_masuk or "-",
            absensi.alamat_pulang or "-"
        ]
        
        for col, value in enumerate(row_data, 1):
            cell = ws.cell(row=row_num, column=col, value=value)
            cell.border = thin_border
            if col in [3, 4, 5, 6, 7]:  # Center align date, time, duration, keterangan
                cell.alignment = Alignment(horizontal="center")
    
    # Auto-adjust column widths
    for column in ws.columns:
        max_length = 0
        column_letter = column[0].column_letter
        for cell in column:
            try:
                if len(str(cell.value)) > max_length:
                    max_length = len(str(cell.value))
            except:
                pass
        adjusted_width = min(max_length + 2, 50)
        ws.column_dimensions[column_letter].width = adjusted_width
    
    # Buat respons download
    response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    filename = f"riwayat_absensi_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    wb.save(response)
    
    return response


@login_required
@role_required(['HRD'])
def export_rekap_absensi_magang_excel(request):
    """Ekspor rekap pivot absensi ke Excel"""
    bulan = request.GET.get('bulan')
    tahun = request.GET.get('tahun')
    nama = request.GET.get('nama', '')
    role = request.GET.get('role', '')
    
    if not bulan or not tahun:
        messages.error(request, "Bulan dan tahun harus dipilih untuk ekspor rekap.")
        return redirect("riwayat_absensi_magang_hr")
    
    # Buat query dasar
    absensi_query = AbsensiMagang.objects.filter(
        tanggal__month=int(bulan),
        tanggal__year=int(tahun)
    ).select_related('id_karyawan', 'id_karyawan__user')
    
    if nama:
        absensi_query = absensi_query.filter(id_karyawan__nama__icontains=nama)
    
    if role:
        absensi_query = absensi_query.filter(id_karyawan__user__role=role)
    
    # Buat workbook Excel
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Rekap Absensi"
    
    # Style
    header_font = Font(bold=True, color="FFFFFF")
    header_fill = PatternFill(start_color="4472C4", end_color="4472C4", fill_type="solid")
    
    if absensi_query.exists():
        pivot_data = list(absensi_query.values('id_karyawan__nama', 'id_karyawan__user__role', 'keterangan'))
        df = pd.DataFrame(pivot_data)
        
        if not df.empty:
            pivot_table = pd.pivot_table(
                df,
                index=['id_karyawan__nama', 'id_karyawan__user__role'],
                columns='keterangan',
                aggfunc='size',
                fill_value=0
            ).reset_index()
            
            # Ensure WFO and WFH columns exist
            for ket in ['WFO', 'WFH']:
                if ket not in pivot_table.columns:
                    pivot_table[ket] = 0
            
            numeric_columns = [col for col in pivot_table.columns if col not in ['id_karyawan__nama', 'id_karyawan__user__role']]
            pivot_table['Total'] = pivot_table[numeric_columns].sum(axis=1)
            
            # Rename columns for clarity
            pivot_table = pivot_table.rename(columns={
                'id_karyawan__nama': 'Nama Karyawan',
                'id_karyawan__user__role': 'Role'
            })
            
            # Header
            headers = list(pivot_table.columns)
            for col, header in enumerate(headers, 1):
                cell = ws.cell(row=1, column=col, value=header)
                cell.font = header_font
                cell.fill = header_fill
            
            # Data
            for row_num, (_, row) in enumerate(pivot_table.iterrows(), 2):
                for col, value in enumerate(row, 1):
                    ws.cell(row=row_num, column=col, value=value)
    else:
        headers = ['Nama Karyawan', 'Role', 'WFO', 'WFH', 'Total']
        for col, header in enumerate(headers, 1):
            cell = ws.cell(row=1, column=col, value=header)
            cell.font = header_font
            cell.fill = header_fill
    
    # Auto-adjust column widths
    for column in ws.columns:
        max_length = 0
        column_letter = column[0].column_letter
        for cell in column:
            try:
                if len(str(cell.value)) > max_length:
                    max_length = len(str(cell.value))
            except:
                pass
        adjusted_width = min(max_length + 2, 50)
        ws.column_dimensions[column_letter].width = adjusted_width
    
    # Buat respons download
    response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    bulan_nama = dict([
        (1, 'Januari'), (2, 'Februari'), (3, 'Maret'), (4, 'April'),
        (5, 'Mei'), (6, 'Juni'), (7, 'Juli'), (8, 'Agustus'),
        (9, 'September'), (10, 'Oktober'), (11, 'November'), (12, 'Desember')
    ]).get(int(bulan), str(bulan))
    filename = f"rekap_absensi_{bulan_nama}_{str(tahun)}.xlsx"
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    wb.save(response)
    
    return response