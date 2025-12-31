from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.db.models import Count, Sum, Value
from django.db.models.functions import Coalesce
from datetime import datetime, timedelta
from collections import defaultdict
from calendar import month_name
from pytanggalmerah import TanggalMerah
from django.db.models import Max

from apps.absensi.models import Absensi
from apps.hrd.models import Cuti, Izin, JatahCuti, CutiBersama, Karyawan


@login_required
def karyawan_dashboard(request):
    user = request.user
    karyawan = user.karyawan  
    
    # Check for birthday employees today
    today = datetime.now().date()
    birthday_employees = Karyawan.objects.filter(
        tanggal_lahir__month=today.month,
        tanggal_lahir__day=today.day,
        status_keaktifan='Aktif'
    ).select_related('user')
    
    has_birthday_today = birthday_employees.exists()

    # Mengambil bulan dan tahun terakhir dari data absensi
    latest_data = Absensi.objects.aggregate(
        latest_bulan=Max('bulan'),
        latest_tahun=Max('tahun')
    )
    bulan = latest_data['latest_bulan'] or datetime.now().month
    tahun = latest_data['latest_tahun'] or datetime.now().year
    
    # --- Perhitungan Sisa Cuti: Jumlahkan sisa_cuti dari semua tahun sejak join ---
    tanggal_join = karyawan.mulai_kontrak
    if tanggal_join:
        # Ambil total sisa cuti dari semua tahun sejak join
        sisa_cuti = JatahCuti.objects.filter(
            karyawan=karyawan,
            tahun__gte=tanggal_join.year
        ).aggregate(
            total_sisa=Coalesce(Sum('sisa_cuti'), Value(0))
        )['total_sisa']
        
        # Pastikan tidak negatif
        sisa_cuti = max(0, sisa_cuti)
    else:
        sisa_cuti = 0
    
    # --- Statistik Pribadi ---
    total_pengajuan_cuti = Cuti.objects.filter(id_karyawan=karyawan, status__iexact='disetujui').count()
    total_pengajuan_izin = Izin.objects.filter(id_karyawan=karyawan, status__iexact='disetujui').count()

    # --- Hari Kerja Bulan Ini (Senin–Jumat) ---
    total_hari = (datetime(tahun, bulan + 1, 1) - timedelta(days=1)).day if bulan != 12 else 31
    hari_kerja = sum(
        1 for day in range(1, total_hari + 1)
        if datetime(tahun, bulan, day).weekday() < 5
    )


    # --- Libur Nasional Terdekat (30 hari ke depan) ---
    today = datetime.today()
    libur_terdekat = []
    tanggal_mulai = today.date()
    tanggal_sampai = tanggal_mulai + timedelta(days=30)

    for hari in range((tanggal_sampai - tanggal_mulai).days):
        tanggal = tanggal_mulai + timedelta(days=hari)
        
        if tanggal.weekday() == 6:
            continue  # Lewati hari Minggu

        try:
            t = TanggalMerah()
            t.set_date(str(tanggal.year), f"{tanggal.month:02d}", f"{tanggal.day:02d}")
            if t.check():
                for event in t.get_event():
                    # Override khusus 26 Des 2025
                    summary = event
                    if tanggal.year == 2025 and tanggal.month == 12 and tanggal.day == 26:
                        if "Tinju" in event or "Cuti Bersama" in event:
                            summary = "WFH"

                    libur_terdekat.append({
                        "summary": summary,
                        "date": tanggal
                    })
        except Exception:
            continue

    context = {
        "sisa_cuti": sisa_cuti,
        "total_pengajuan_cuti": total_pengajuan_cuti,
        "total_pengajuan_izin": total_pengajuan_izin,
        "hari_kerja": hari_kerja,
        "libur_terdekat": libur_terdekat,
        "selected_bulan": str(bulan),
        "selected_tahun": str(tahun),
        "has_birthday_today": has_birthday_today,
        "birthday_employees": birthday_employees,
    }

    return render(request, "karyawan/index.html", context)


@login_required
def calendar_events(request):
    events = []

    # Gabungkan cuti berdasarkan tanggal
    grouped_cuti = defaultdict(list)
    for c in Cuti.objects.filter(status='disetujui'):
        current_date = c.tanggal_mulai
        while current_date <= c.tanggal_selesai:
            grouped_cuti[current_date].append(c.id_karyawan.nama)
            current_date += timedelta(days=1)

    for date, names in grouped_cuti.items():
        events.append({
            "title": f"Cuti ({len(names)} orang)",
            "start": date.isoformat(),
            "color": "#4e73df",
            "description": ", ".join(names)
        })

    # Izin
    grouped_izin_wfh = defaultdict(list)
    grouped_izin_sakit = defaultdict(list)
    for i in Izin.objects.filter(status='disetujui'):
        if i.jenis_izin == 'wfh':
            grouped_izin_wfh[i.tanggal_izin].append(i.id_karyawan.nama)
        elif i.jenis_izin == 'sakit':
            grouped_izin_sakit[i.tanggal_izin].append(i.id_karyawan.nama)

    # WFH events
    for date, names in grouped_izin_wfh.items():
        events.append({
            "title": f"WFH ({len(names)} orang)",
            "start": date.isoformat(),
            "color": "#11cdef",
            "description": ", ".join(names)
        })

    # Sick leave events
    for date, names in grouped_izin_sakit.items():
        events.append({
            "title": f"Sakit ({len(names)} orang)",
            "start": date.isoformat(),
            "color": "#fb6340",
            "description": ", ".join(names)
        })

    # Tambahkan data ulang tahun karyawan
    today = datetime.now().date()
    
    # PERBAIKAN: Standardisasi range tanggal (sama dengan HRD)
    start_date = today - timedelta(days=365)  # 1 tahun ke belakang
    end_date = today + timedelta(days=365)    # 1 tahun ke depan
    
    # Ambil semua karyawan aktif yang memiliki tanggal lahir
    karyawan_list = Karyawan.objects.filter(
        status_keaktifan='Aktif',
        tanggal_lahir__isnull=False
    ).select_related('user')
        
    # Buat events untuk ulang tahun dalam rentang 2 tahun
    for karyawan in karyawan_list:        
        # Hitung ulang tahun untuk tahun lalu, tahun ini, dan tahun depan
        for year in [today.year - 1, today.year, today.year + 1]:
            try:
                birthday_this_year = karyawan.tanggal_lahir.replace(year=year)
                
                # Tampilkan ulang tahun dalam rentang yang ditentukan
                if start_date <= birthday_this_year <= end_date:
                    events.append({
                        "title": f"🎂 Ulang Tahun: {karyawan.nama}",
                        "start": birthday_this_year.isoformat(),
                        "color": "#e83e8c",
                        "description": f"Ulang tahun {karyawan.nama}",
                        "allDay": True
                    })
            except ValueError as e:
                # Handle leap year issues (Feb 29)
                if karyawan.tanggal_lahir.month == 2 and karyawan.tanggal_lahir.day == 29:
                    birthday_this_year = karyawan.tanggal_lahir.replace(year=year, day=28)
                    if start_date <= birthday_this_year <= end_date:
                        events.append({
                            "title": f"🎂 Ulang Tahun: {karyawan.nama}",
                            "start": birthday_this_year.isoformat(),
                            "color": "#e83e8c",
                            "description": f"Ulang tahun {karyawan.nama}",
                            "allDay": True
                        })

    # PERBAIKAN: Tanggal Merah dengan range yang konsisten
    current_date = start_date
    
    while current_date <= end_date:
        try:
            t = TanggalMerah()
            t.set_date(str(current_date.year), f"{current_date.month:02d}", f"{current_date.day:02d}")
            if t.check():
                for event in t.get_event():
                    if event.lower() == 'sunday':
                        continue

                    # Override khusus 26 Des 2025
                    title = event
                    color = "#dc3545"

                    if current_date.year == 2025 and current_date.month == 12 and current_date.day == 26:
                        if "Tinju" in event or "Cuti Bersama" in event:
                            title = "WFH"
                            color = "#11cdef" # Warna WFH (sedikit beda di view ini)

                    events.append({
                        "title": title,
                        "start": current_date.isoformat(),
                        "color": color,
                        "allDay": True
                    })
        except Exception:
            pass
        current_date += timedelta(days=1)

    # Cuti Bersama
    for cb in CutiBersama.objects.all():
        if cb.jenis in ['WFH', 'WFA']:
            title = f"{cb.jenis}: {cb.keterangan}" if cb.keterangan else cb.jenis
            color = "#36b9cc" # Cyan for WFH/WFA
        else:
            title = f"Cuti Bersama: {cb.keterangan}" if cb.keterangan else "Cuti Bersama"
            color = "#6f42c1"
        
        # Override khusus 26 Des 2025
        if cb.tanggal.year == 2025 and cb.tanggal.month == 12 and cb.tanggal.day == 26:
            title = "WFH"
            color = "#36b9cc"

        events.append({
            "title": title,
            "start": cb.tanggal.isoformat(),
            "color": color,
            "allDay": True
        })

    # Add a debug event if no events are found
    if not events:
        events.append({
            "title": "Debug Event",
            "start": today.isoformat(),
            "color": "#cccccc",
            "allDay": True
        })

    return JsonResponse(events, safe=False)

@login_required
def data_dashboard_karyawan(request):
    import calendar
    
    user = request.user
    karyawan = user.karyawan

    # Mengambil bulan dan tahun terakhir dari data absensi GLOBAL (bukan per karyawan)
    latest_data = Absensi.objects.aggregate(
        latest_bulan=Max('bulan'),
        latest_tahun=Max('tahun')
    )
    bulan = latest_data['latest_bulan'] or datetime.now().month
    tahun = latest_data['latest_tahun'] or datetime.now().year

    # --- Perhitungan Sisa Cuti: Jumlahkan sisa_cuti dari semua tahun sejak join ---
    tanggal_join = karyawan.mulai_kontrak
    if tanggal_join:
        # Ambil total sisa cuti dari semua tahun sejak join
        sisa_cuti = JatahCuti.objects.filter(
            karyawan=karyawan,
            tahun__gte=tanggal_join.year
        ).aggregate(
            total_sisa=Coalesce(Sum('sisa_cuti'), Value(0))
        )['total_sisa']
        
        # Pastikan tidak negatif
        sisa_cuti = max(0, sisa_cuti)
    else:
        sisa_cuti = 0

    # hitung semua data yang sama seperti view utama
    total_pengajuan_cuti = Cuti.objects.filter(id_karyawan=karyawan, tanggal_mulai__year=tahun, tanggal_mulai__month=bulan).count()
    total_pengajuan_izin = Izin.objects.filter(id_karyawan=karyawan, tanggal_izin__year=tahun, tanggal_izin__month=bulan).count()


    return JsonResponse({
        "sisa_cuti": sisa_cuti,
        "total_pengajuan_cuti": total_pengajuan_cuti,
        "total_pengajuan_izin": total_pengajuan_izin,
        "nama_bulan": calendar.month_name[bulan],
        "tahun": tahun,
    })