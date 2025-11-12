import pandas as pd
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator
from django.http import HttpResponse
from django.db.models import Count, Q
from apps.authentication.decorators import role_required
from apps.absensi.models import AbsensiMagang
from apps.hrd.models import Karyawan
from datetime import datetime
import openpyxl

@login_required
@role_required(['HRD'])
def riwayat_absensi_magang_hr(request):
    """Menampilkan riwayat absensi magang untuk HR"""
    # Filter berdasarkan parameter
    nama = request.GET.get('nama', '')
    bulan = request.GET.get('bulan')
    tahun = request.GET.get('tahun')
    status = request.GET.get('status')
    tanggal_mulai = request.GET.get('tanggal_mulai')
    tanggal_selesai = request.GET.get('tanggal_selesai')
    
    # Buat query dasar
    absensi_query = AbsensiMagang.objects.all().select_related('id_karyawan')
    
    # Terapkan filter
    if nama:
        absensi_query = absensi_query.filter(id_karyawan__nama__icontains=nama)
    
    if bulan and bulan.isdigit():
        absensi_query = absensi_query.filter(tanggal__month=int(bulan))
    
    if tahun and tahun.isdigit():
        absensi_query = absensi_query.filter(tanggal__year=int(tahun))
    
    if status:
        absensi_query = absensi_query.filter(status=status)
    
    if tanggal_mulai:
        try:
            tanggal_mulai = datetime.strptime(tanggal_mulai, '%Y-%m-%d').date()
            absensi_query = absensi_query.filter(tanggal__gte=tanggal_mulai)
        except ValueError:
            messages.error(request, 'Format tanggal mulai tidak valid')
    
    if tanggal_selesai:
        try:
            tanggal_selesai = datetime.strptime(tanggal_selesai, '%Y-%m-%d').date()
            absensi_query = absensi_query.filter(tanggal__lte=tanggal_selesai)
        except ValueError:
            messages.error(request, 'Format tanggal selesai tidak valid')
    
    # Sorting
    sort_by = request.GET.get('sort_by', '-tanggal')
    absensi_query = absensi_query.order_by(sort_by)
    
    # Pagination
    paginator = Paginator(absensi_query, 10)  # 10 items per halaman
    page = request.GET.get('page')
    absensi_list = paginator.get_page(page)
    
    # Pilihan bulan dan tahun untuk filter
    months = [
        (1, 'Januari'), (2, 'Februari'), (3, 'Maret'), (4, 'April'),
        (5, 'Mei'), (6, 'Juni'), (7, 'Juli'), (8, 'Agustus'),
        (9, 'September'), (10, 'Oktober'), (11, 'November'), (12, 'Desember')
    ]
    
    # Tahun dari 3 tahun lalu sampai tahun depan
    current_year = datetime.now().year
    years = range(current_year - 3, current_year + 2)
    
    # Status choices dari model
    status_choices = [
        ('Tepat Waktu', 'Tepat Waktu'),
        ('Terlambat', 'Terlambat')
    ]
    
    # Hitung statistik untuk pivot
    if bulan and bulan.isdigit() and tahun and tahun.isdigit():
        # Menggunakan pandas untuk membuat pivot table
        if absensi_query.exists():
            # Ambil data untuk pivot
            pivot_data = list(absensi_query.values('id_karyawan__nama', 'status'))
            df = pd.DataFrame(pivot_data)
            
            # Buat pivot table
            if not df.empty and 'id_karyawan__nama' in df.columns and 'status' in df.columns:
                # Pastikan semua status yang mungkin ada dalam kolom
                all_status = ['Tepat Waktu', 'Terlambat']
                
                pivot_table = pd.pivot_table(
                    df,
                    index='id_karyawan__nama',
                    columns='status',
                    aggfunc='size',
                    fill_value=0
                ).reset_index()
                
                # Tambahkan kolom status yang tidak ada dengan nilai 0
                for status in all_status:
                    if status not in pivot_table.columns:
                        pivot_table[status] = 0
                
                # Tambahkan kolom total
                # Menghitung total dengan menjumlahkan semua kolom kecuali kolom nama
                numeric_columns = [col for col in pivot_table.columns if col != 'id_karyawan__nama']
                pivot_table['Total'] = pivot_table[numeric_columns].sum(axis=1)
                
                # Urutkan kolom sesuai urutan yang diinginkan
                column_order = ['id_karyawan__nama'] + all_status + ['Total']
                pivot_table = pivot_table.reindex(columns=column_order, fill_value=0)
                
                # Konversi ke list untuk template
                pivot_headers = ['Nama Karyawan'] + all_status + ['Total']
                pivot_rows = []
                
                for _, row in pivot_table.iterrows():
                    pivot_rows.append(list(row))
            else:
                pivot_headers = ['Nama Karyawan', 'Tepat Waktu', 'Terlambat', 'Hadir', 'Izin', 'Sakit', 'Total']
                pivot_rows = []
        else:
            pivot_headers = ['Nama Karyawan', 'Tepat Waktu', 'Terlambat', 'Hadir', 'Izin', 'Sakit', 'Total']
            pivot_rows = []
    else:
        pivot_headers = ['Nama Karyawan', 'Tepat Waktu', 'Terlambat', 'Hadir', 'Izin', 'Sakit', 'Total']
        pivot_rows = []
    
    context = {
        'absensi_list': absensi_list,
        'nama_filter': nama,
        'selected_month': int(bulan) if bulan and bulan.isdigit() else '',
        'selected_year': int(tahun) if tahun and tahun.isdigit() else '',
        'selected_status': status if status else '',
        'tanggal_mulai': tanggal_mulai,
        'tanggal_selesai': tanggal_selesai,
        'months': months,
        'years': years,
        'status_choices': status_choices,
        'sort_by': sort_by,
        'pivot_headers': pivot_headers,
        'pivot_rows': pivot_rows,
        'title': 'Riwayat Absensi Magang'
    }
    
    return render(request, 'absensi/riwayat_absensi_magang_hr.html', context)

@login_required
@role_required(['HRD'])
def export_absensi_magang_excel(request):
    """Ekspor data absensi magang ke Excel"""
    nama = request.GET.get('nama', '')
    bulan = request.GET.get('bulan')
    tahun = request.GET.get('tahun')
    status = request.GET.get('status')
    tanggal_mulai = request.GET.get('tanggal_mulai')
    tanggal_selesai = request.GET.get('tanggal_selesai')
    
    # Buat query dasar
    absensi_query = AbsensiMagang.objects.all().select_related('id_karyawan')
    
    # Terapkan filter
    if nama:
        absensi_query = absensi_query.filter(id_karyawan__nama__icontains=nama)
    
    if bulan and bulan.isdigit():
        absensi_query = absensi_query.filter(tanggal__month=int(bulan))
    
    if tahun and tahun.isdigit():
        absensi_query = absensi_query.filter(tanggal__year=int(tahun))
    
    if status:
        absensi_query = absensi_query.filter(status=status)
    
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
    
    # Sorting
    sort_by = request.GET.get('sort_by', '-tanggal')
    if sort_by.startswith('-'):
        sort_field = sort_by[1:]
        reverse = True
    else:
        sort_field = sort_by
        reverse = False
    
    # Buat workbook Excel
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Riwayat Absensi Magang"
    
    # Header
    headers = [
        "Nama Karyawan", "Tanggal", "Jam Masuk", "Jam Pulang", 
        "Status", "Lokasi Masuk", "Lokasi Pulang"
    ]
    ws.append(headers)
    
    # Data
    for absensi in absensi_query:
        ws.append([
            absensi.id_karyawan.nama,
            absensi.tanggal.strftime("%Y-%m-%d"),
            absensi.jam_masuk.strftime("%H:%M:%S") if absensi.jam_masuk else "-",
            absensi.jam_pulang.strftime("%H:%M:%S") if absensi.jam_pulang else "-",
            absensi.status,
            absensi.alamat_masuk or "-",
            absensi.alamat_pulang or "-"
        ])
    
    # Buat respons download
    response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    filename = f"riwayat_absensi_magang_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    wb.save(response)
    
    return response

@login_required
@role_required(['HRD'])
def export_rekap_absensi_magang_excel(request):
    """Ekspor rekap pivot absensi magang ke Excel"""
    bulan = request.GET.get('bulan')
    tahun = request.GET.get('tahun')
    nama = request.GET.get('nama', '')
    
    if not bulan or not tahun:
        messages.error(request, "Bulan dan tahun harus dipilih untuk ekspor rekap.")
        return redirect("riwayat_absensi_magang_hr")
    
    # Buat query dasar
    absensi_query = AbsensiMagang.objects.filter(
        tanggal__month=int(bulan),
        tanggal__year=int(tahun)
    ).select_related('id_karyawan')
    
    if nama:
        absensi_query = absensi_query.filter(id_karyawan__nama__icontains=nama)
    
    # Menggunakan pandas untuk membuat pivot table
    if absensi_query.exists():
        # Ambil data untuk pivot
        pivot_data = list(absensi_query.values('id_karyawan__nama', 'status'))
        df = pd.DataFrame(pivot_data)
        
        # Buat pivot table
        if not df.empty and 'id_karyawan__nama' in df.columns and 'status' in df.columns:
            pivot_table = pd.pivot_table(
                df,
                index='id_karyawan__nama',
                columns='status',
                aggfunc='size',
                fill_value=0
            ).reset_index()
            
            # Tambahkan kolom total
            # Hitung total dengan menjumlahkan semua kolom kecuali kolom nama
            numeric_columns = pivot_table.columns.drop('id_karyawan__nama')
            pivot_table['Total'] = pivot_table[numeric_columns].sum(axis=1)
            
            # Buat workbook Excel
            wb = openpyxl.Workbook()
            ws = wb.active
            ws.title = "Rekap Absensi Magang"
            
            # Header
            headers = ['Nama Karyawan'] + list(pivot_table.columns[1:])
            ws.append(headers)
            
            # Data
            for _, row in pivot_table.iterrows():
                ws.append(list(row))
        else:
            # Buat workbook kosong dengan header default
            wb = openpyxl.Workbook()
            ws = wb.active
            ws.title = "Rekap Absensi Magang"
            ws.append(['Nama Karyawan', 'Tepat Waktu', 'Terlambat', 'Total'])
            pivot_headers = ['Nama Karyawan', 'Tepat Waktu', 'Terlambat', 'Total']
            pivot_rows = []
    else:
        pivot_headers = ['Nama Karyawan', 'Tepat Waktu', 'Terlambat', 'Total']
        pivot_rows = []
    
    # Buat respons download
    response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    bulan_nama = dict([
        (1, 'Januari'), (2, 'Februari'), (3, 'Maret'), (4, 'April'),
        (5, 'Mei'), (6, 'Juni'), (7, 'Juli'), (8, 'Agustus'),
        (9, 'September'), (10, 'Oktober'), (11, 'November'), (12, 'Desember')
    ]).get(int(bulan), str(bulan))
    filename = f"rekap_absensi_magang_{bulan_nama}_{str(tahun)}.xlsx"
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    wb.save(response)
    
    return response