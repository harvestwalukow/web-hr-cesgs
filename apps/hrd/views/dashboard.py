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

    # Ambil bulan dan tahun dari request
    bulan = request.GET.get("bulan", str(datetime.now().month))
    tahun = request.GET.get("tahun", str(datetime.now().year))
        
    bulan_ini = datetime.now().month
    tahun_ini = datetime.now().year

    # Hitung total karyawan tetap (aktif dan bukan magang)
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

    print(f"🔍 Filter Data: Bulan={bulan}, Tahun={tahun}")

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
    
    # Hitung jumlah karyawan per divisi
    jumlah_per_divisi = Karyawan.objects.filter(status_keaktifan='Aktif').values('divisi').annotate(jumlah=Count('id')).order_by('divisi')
    
    # Get karyawan names per divisi
    karyawan_per_divisi = {}
    for divisi in jumlah_per_divisi:
        karyawan_per_divisi[divisi['divisi']] = list(Karyawan.objects.filter(
        status_keaktifan='Aktif',
        divisi=divisi['divisi']
        ).values_list('nama', flat=True))
    
    # Konversi ke dictionary untuk template
    jumlah_per_divisi_dict = {item['divisi']: item['jumlah'] for item in jumlah_per_divisi}
    
    # jumlah divisi paginasi dengan nama karyawan
    jumlah_divisi_json = json.dumps([{
    "divisi": k,
    "jumlah": v,
    "karyawan": karyawan_per_divisi[k]
    } for k, v in jumlah_per_divisi_dict.items()], cls=DjangoJSONEncoder)
    
    # tanggal merah 
    today = datetime.now().date()
    next_30_days = [today + timedelta(days=i) for i in range(1, 31)]

    libur_terdekat = []

    for d in next_30_days:
        if d.weekday() == 6:
            continue  # Lewati hari Minggu

        t = TanggalMerah()
        t.set_date(str(d.year), f"{d.month:02d}", f"{d.day:02d}")
        if t.check():
            events = t.get_event()
            if events:
                for event in events:
                    libur_terdekat.append({
                        'summary': event,
                        'date': d
                    })

    # context
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
        'jumlah_per_divisi_dict': jumlah_per_divisi_dict,
        'libur_json': json.dumps(libur_terdekat, cls=DjangoJSONEncoder),
        "jumlah_divisi_json": jumlah_divisi_json,
        "has_birthday_today": has_birthday_today,
        "birthday_employees": birthday_employees,
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
            "color": "#36b9cc",  # Cyan
            "description": ", ".join(names),
            "allDay": True
        })

    # Telat events
    for date, names in grouped_izin_telat.items():
        events.append({
            "title": f"Izin Telat ({len(names)} orang)",
            "start": date.isoformat(),
            "color": "#f6c23e",  # Orange
            "description": ", ".join(names),
            "allDay": True
        })

    # Tambahkan data ulang tahun karyawan
    today = datetime.now().date()
    end_date = today + timedelta(days=365)
    
    # Ambil semua karyawan aktif yang memiliki tanggal lahir
    karyawan_list = Karyawan.objects.filter(
        status_keaktifan='Aktif',
        tanggal_lahir__isnull=False
    ).select_related('user')
        
    # Buat events untuk ulang tahun dalam 1 tahun ke depan
    for karyawan in karyawan_list:        
        # Hitung ulang tahun untuk tahun ini dan tahun depan
        for year in [today.year, today.year + 1]:
            try:
                birthday_this_year = karyawan.tanggal_lahir.replace(year=year)
                
                # Ubah kondisi agar lebih fleksibel - tampilkan semua ulang tahun dalam rentang
                if birthday_this_year >= today - timedelta(days=30) and birthday_this_year <= end_date:
                    events.append({
                        "title": f"🎂 Ulang Tahun: {karyawan.nama}",
                        "start": birthday_this_year.isoformat(),
                        "color": "#e83e8c",  # Pink untuk ulang tahun
                        "description": f"Ulang tahun {karyawan.nama}",
                        "allDay": True
                    })
            except ValueError as e:
                # Handle leap year issues (Feb 29)
                if karyawan.tanggal_lahir.month == 2 and karyawan.tanggal_lahir.day == 29:
                    # For leap year babies, use Feb 28 in non-leap years
                    birthday_this_year = karyawan.tanggal_lahir.replace(year=year, day=28)
                    if birthday_this_year >= today - timedelta(days=30) and birthday_this_year <= end_date:
                        events.append({
                            "title": f"🎂 Ulang Tahun: {karyawan.nama}",
                            "start": birthday_this_year.isoformat(),
                            "color": "#e83e8c",
                            "description": f"Ulang tahun {karyawan.nama}",
                            "allDay": True
                        })

    # Tanggal Merah 1 tahun ke depan
    current_date = today

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


    # Cuti Bersama
    for cb in CutiBersama.objects.all():
        events.append({
            "title": f"Cuti Bersama: {cb.keterangan or 'Cuti Bersama'}",
            "start": cb.tanggal.isoformat(),
            "color": "#6f42c1",
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

    # import pprint
    # pprint.pprint(events)
    
    # print(f"Debug: Total events: {len(events)}")
    return JsonResponse(events, safe=False)