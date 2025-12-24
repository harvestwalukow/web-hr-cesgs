from django.shortcuts import render
from django.db.models import Count
from django.db.models.functions import ExtractMonth
from django.contrib.auth.decorators import login_required
from apps.authentication.decorators import role_required
from apps.absensi.models import Absensi
from apps.hrd.models import Karyawan, Cuti, Izin, TidakAmbilCuti, CutiBersama
from datetime import datetime, timedelta
from django.http import JsonResponse
from pytanggalmerah import TanggalMerah
from collections import defaultdict
from django.core.paginator import Paginator
import json
from django.core.serializers.json import DjangoJSONEncoder

@login_required
@role_required(['HRD'])
def hrd_dashboard(request):

    # Check for birthday employees today
    today = datetime.now().date()
    birthday_employees = Karyawan.objects.filter(
        tanggal_lahir__month=today.month,
        tanggal_lahir__day=today.day,
        status_keaktifan='Aktif'
    ).select_related('user')
    
    has_birthday_today = birthday_employees.exists()

    # Check for contract expiring in 5 days
    five_days_from_now = today + timedelta(days=5)
    expiring_contracts = Karyawan.objects.filter(
        batas_kontrak__lte=five_days_from_now,
        batas_kontrak__gte=today,
        status_keaktifan='Aktif'
    ).select_related('user')
    
    has_expiring_contracts = expiring_contracts.exists()

    # Ambil bulan dan tahun dari request
    bulan = request.GET.get("bulan", str(datetime.now().month))
    tahun = request.GET.get("tahun", str(datetime.now().year))
        
    bulan_ini = datetime.now().month
    tahun_ini = datetime.now().year

    # Hitung total karyawan fulltime (aktif dan bukan magang)
    total_karyawan_tetap = Karyawan.objects.filter(
        status_keaktifan='Aktif'
    ).exclude(
        divisi__icontains='Magang' 
    ).count()
    
    # Hitung total cuti
    total_cuti = Cuti.objects.filter(
        jenis_cuti__in=[
            'tahunan', 'melahirkan', 'menikah', 'menikahkan_anak', 
            'berkabung_sedarah', 'berkabung_serumah', 'khitan_anak', 
            'baptis_anak', 'istri_melahirkan'
        ]
    ).count()

    # Hitung total cuti bulan ini yang disetujui
    cuti_bulan_ini = Cuti.objects.filter(
        jenis_cuti__in=[
            'tahunan', 'melahirkan', 'menikah', 'menikahkan_anak', 
            'berkabung_sedarah', 'berkabung_serumah', 'khitan_anak', 
            'baptis_anak', 'istri_melahirkan'
        ],
        tanggal_pengajuan__month=bulan_ini,
        tanggal_pengajuan__year=tahun_ini,
        status='disetujui'
    ).count()
    
    # Hitung total izin WFH (sesuaikan dengan model dan field yang Anda gunakan)
    total_izin_wfh = Izin.objects.filter(jenis_izin='wfh').count()
    
    # Hitung total izin telat
    total_izin_telat = Izin.objects.filter(jenis_izin__icontains='telat').count()

    # Hitung total izin telat bulan ini yang disetujui
    telat_bulan_ini = Izin.objects.filter(
        jenis_izin__icontains='telat',
        tanggal_izin__month=bulan_ini,
        tanggal_izin__year=tahun_ini,
        status='disetujui'
    ).count()

    # Perbaiki format tahun jika error
    if isinstance(tahun, str) and tahun.startswith("("):
        tahun = tahun.strip("()").replace("'", "").split(",")[0].strip()

    try:
        bulan = int(bulan)
        tahun = int(tahun)
    except ValueError:
        bulan = datetime.now().month
        tahun = datetime.now().year

    

    # --------- Top 5 Karyawan Terlambat ---------
    top_5_late = (
        Absensi.objects.filter(status_absensi="Terlambat", bulan=bulan, tahun=tahun)
        .values("id_karyawan__nama")
        .annotate(total_terlambat=Count("id_karyawan"))
        .order_by("-total_terlambat")[:5]
    )

    # --------- Top 5 Karyawan Tepat Waktu ---------
    absensi_hadir = Absensi.objects.filter(status_absensi="Tepat Waktu", bulan=bulan, tahun=tahun)

    karyawan_data = {}
    for absen in absensi_hadir:
        # Skip jika jam_masuk None
        if absen.jam_masuk is None:
            continue
            
        nama = absen.id_karyawan.nama
        jam_masuk = datetime.combine(absen.tanggal, absen.jam_masuk)
        jam_masuk_ideal = datetime.combine(absen.tanggal, datetime.strptime("09:00", "%H:%M").time())

        keterlambatan = (jam_masuk - jam_masuk_ideal).total_seconds() / 60
        keterlambatan = max(keterlambatan, 0)

        if nama not in karyawan_data:
            karyawan_data[nama] = {'total_tepat_waktu': 0, 'total_keterlambatan': 0}
        
        karyawan_data[nama]['total_tepat_waktu'] += 1
        karyawan_data[nama]['total_keterlambatan'] += keterlambatan

    top_5_ontime = sorted(
        karyawan_data.items(),
        key=lambda x: (-x[1]['total_tepat_waktu'], x[1]['total_keterlambatan'])
    )[:5]

    top_5_ontime = [
        {'nama': nama, 'total_tepat_waktu': data['total_tepat_waktu']}
        for nama, data in top_5_ontime
    ]
    
    # --------- Top 5 Jenis Cuti ---------
    top_jenis_cuti = (
        Cuti.objects.filter(tanggal_mulai__year=tahun)
        .values('jenis_cuti')
        .annotate(total=Count('id'))
        .order_by('-total')[:5]
    )

    top_cuti_labels = [item['jenis_cuti'] for item in top_jenis_cuti]
    top_cuti_values = [item['total'] for item in top_jenis_cuti]

    cuti_bulan_ini = Cuti.objects.filter(
        tanggal_mulai__month=bulan,
        tanggal_mulai__year=tahun,
        status='disetujui'
    ).count()

    izin_bulan_ini = Izin.objects.filter(
        tanggal_izin__month=bulan,
        tanggal_izin__year=tahun,
        status='disetujui'
    ).count()

    jumlah_cuti_menunggu = Cuti.objects.filter(status='menunggu').count()
    jumlah_izin_menunggu = Izin.objects.filter(status='menunggu').count()
    jumlah_tidak_ambil_cuti_menunggu = TidakAmbilCuti.objects.filter(status='menunggu').count()

    cuti_per_bulan = (
        Cuti.objects.filter(status='disetujui', tanggal_mulai__year=tahun)
        .annotate(bulan=ExtractMonth('tanggal_mulai'))
        .values('bulan')
        .annotate(total=Count('id'))
        .order_by('bulan')
    )

    izin_per_bulan = (
        Izin.objects.filter(status='disetujui', tanggal_izin__year=tahun)
        .annotate(bulan=ExtractMonth('tanggal_izin'))
        .values('bulan')
        .annotate(total=Count('id'))
        .order_by('bulan')
    )

    cuti_chart = [0] * 12
    izin_chart = [0] * 12

    for item in cuti_per_bulan:
        cuti_chart[item['bulan'] - 1] = item['total']

    for item in izin_per_bulan:
        izin_chart[item['bulan'] - 1] = item['total']

    # Dropdown pilihan bulan/tahun
    bulan_choices = [(str(i), datetime(2000, i, 1).strftime("%B")) for i in range(1, 13)]
    tahun_choices = [str(i) for i in range(2020, 2031)]
    
    # Hitung jumlah karyawan per divisi (raw)
    jumlah_per_divisi = (
        Karyawan.objects
        .filter(status_keaktifan='Aktif')
        .values('divisi')
        .annotate(jumlah=Count('id'))
        .order_by('divisi')
    )

    # Normalisasi divisi lama → kanonik
    alias_map = {
        None: 'Consulting',
        '': 'Consulting',
        '  ': 'Consulting',
        'Rinov': 'Research and Innovation',
        'Basic Research': 'CPEBR',
    }
    def canonical_divisi(val):
        if val is None:
            return alias_map[None]
        s = str(val)
        if s.strip() == '':
            return alias_map['']
        return alias_map.get(s, s)

    # Gabungkan count dan nama karyawan per divisi kanonik
    from collections import defaultdict
    jumlah_per_divisi_canon = defaultdict(int)
    karyawan_per_divisi = defaultdict(list)

    for d in jumlah_per_divisi:
        canon = canonical_divisi(d['divisi'])
        jumlah_per_divisi_canon[canon] += d['jumlah']
        # Ambil nama per nilai raw, lalu masukkan ke key kanonik
        names = list(Karyawan.objects.filter(
            status_keaktifan='Aktif',
            divisi=d['divisi']
        ).values_list('nama', flat=True))
        karyawan_per_divisi[canon].extend(names)

    # Map internal value -> label display sesuai choices
    choice_map = dict(Karyawan.DIVISI_CHOICES)

    # JSON untuk frontend: kirim label dan value kanonik
    jumlah_divisi_json = json.dumps([
        {
            "divisi_value": div_key,
            "divisi_label": choice_map.get(div_key, div_key),
            "jumlah": count,
            "karyawan": karyawan_per_divisi.get(div_key, [])
        }
        for div_key, count in jumlah_per_divisi_canon.items()
    ], cls=DjangoJSONEncoder)
    
    # tanggal merah 
    today = datetime.now().date()
    next_30_days = [today + timedelta(days=i) for i in range(1, 31)]

    libur_terdekat = []

    for d in next_30_days:
        if d.weekday() == 6:
            continue  # Lewati hari Minggu

        try:
            t = TanggalMerah()
            t.set_date(str(d.year), f"{d.month:02d}", f"{d.day:02d}")
            if t.check():
                events = t.get_event()
                if events:
                    for event in events:
                        # Override khusus 26 Des 2025
                        summary = event
                        if d.year == 2025 and d.month == 12 and d.day == 26:
                            if "Tinju" in event or "Cuti Bersama" in event:
                                summary = "WFH"

                        libur_terdekat.append({
                            'summary': summary,
                            'date': d
                        })
        except Exception:
            continue

    # context
    # Urutkan libur terdekat berdasarkan tanggal
    libur_terdekat.sort(key=lambda x: x['date'])

    # Paginasi untuk libur nasional
    paginator_libur = Paginator(libur_terdekat, 3) # Tampilkan 3 per halaman
    page_number_libur = request.GET.get('page_libur')
    page_obj_libur = paginator_libur.get_page(page_number_libur)

    # JSON untuk JavaScript frontend
    libur_json = json.dumps([
        {'summary': item['summary'], 'date': item['date'].isoformat()}
        for item in libur_terdekat
    ], cls=DjangoJSONEncoder)

    context = {
        "top_5_late": top_5_late,
        "top_5_ontime": top_5_ontime,
        "top_cuti_labels": top_cuti_labels,
        "top_cuti_values": top_cuti_values,
        'total_karyawan_tetap': total_karyawan_tetap,
        'cuti_bulan_ini': cuti_bulan_ini,
        'total_cuti': total_cuti,
        'total_izin_telat': total_izin_telat,
        'telat_bulan_ini': telat_bulan_ini,
        'total_izin_wfh': total_izin_wfh,
        "izin_bulan_ini": izin_bulan_ini,
        "cuti_chart": cuti_chart,
        "izin_chart": izin_chart,
        "jumlah_cuti_menunggu": jumlah_cuti_menunggu,
        "jumlah_izin_menunggu": jumlah_izin_menunggu,
        "jumlah_tidak_ambil_cuti_menunggu": jumlah_tidak_ambil_cuti_menunggu,
        "bulan_choices": bulan_choices,
        "tahun_choices": tahun_choices,
        "selected_bulan": str(bulan),
        "selected_tahun": str(tahun),
        'jumlah_per_divisi_dict': dict(jumlah_per_divisi_canon),
        "jumlah_divisi_json": jumlah_divisi_json,
        "has_birthday_today": has_birthday_today,
        "birthday_employees": birthday_employees,
        "has_expiring_contracts": has_expiring_contracts,
        "expiring_contracts": expiring_contracts,
        "page_obj_libur": page_obj_libur,
        "libur_json": libur_json,
    }

    return render(request, "hrd/index.html", context)

@login_required
@role_required(['HRD'])
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
            "description": ", ".join(names),
            "allDay": True
        })

    # Izin
    grouped_izin_wfh = defaultdict(list)
    grouped_izin_telat = defaultdict(list)

    for i in Izin.objects.filter(status='disetujui'):
        if i.jenis_izin.lower() in ['wfh', 'izin wfh']:
            grouped_izin_wfh[i.tanggal_izin].append(i.id_karyawan.nama)
        elif i.jenis_izin.lower() in ['telat', 'izin telat']:
            grouped_izin_telat[i.tanggal_izin].append(i.id_karyawan.nama)

    # WFH events
    for date, names in grouped_izin_wfh.items():
        events.append({
            "title": f"WFH ({len(names)} orang)",
            "start": date.isoformat(),
            "color": "#36b9cc",
            "description": ", ".join(names),
            "allDay": True
        })

    # Telat events
    for date, names in grouped_izin_telat.items():
        events.append({
            "title": f"Izin Telat ({len(names)} orang)",
            "start": date.isoformat(),
            "color": "#f6c23e",
            "description": ", ".join(names),
            "allDay": True
        })

    # Tambahkan data ulang tahun karyawan
    today = datetime.now().date()
    
    # PERBAIKAN: Standardisasi range tanggal
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
                            color = "#36b9cc" # Warna WFH

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
        title = f"Cuti Bersama: {cb.keterangan or 'Cuti Bersama'}"
        color = "#6f42c1"

        # Override khusus 26 Des 2025
        if cb.tanggal.year == 2025 and cb.tanggal.month == 12 and cb.tanggal.day == 26:
            title = "WFH"
            color = "#36b9cc" # Warna WFH

        events.append({
            "title": title,
            "start": cb.tanggal.isoformat(),
            "color": color,
            "allDay": True
        })

    # Debug jika kosong
    if not events:
        events.append({
            "title": "Debug Event",
            "start": today.isoformat(),
            "color": "#cccccc",
            "allDay": True
        })

    return JsonResponse(events, safe=False)