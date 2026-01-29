import json
from datetime import datetime, time
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponse
from django.conf import settings
from django.contrib import messages
from django.views.decorators.csrf import csrf_exempt
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut, GeocoderServiceError
from apps.authentication.decorators import role_required
from apps.hrd.models import Karyawan, Izin
from ..models import AbsensiMagang
from ..forms import AbsensiMagangForm, AbsensiPulangForm
from ..utils import validate_user_location

# Time restrictions (8.5 hour work system)
MIN_CHECKIN_TIME = time(6, 0)   # 06:00 - earliest check-in allowed
REMINDER_CHECKIN_TIME = time(10, 0)  # 10:00 - setelah ini wajib Izin Telat
MAX_CHECKIN_TIME = time(11, 0)  # 11:00 - batas maksimal (bahkan dengan Izin Telat, secara bisnis tetap dipakai untuk reminder/deadline)
OVERTIME_THRESHOLD = time(18, 30)  # 6:30 PM - overtime alert threshold
MAX_CHECKOUT_TIME = time(22, 0)  # 10:00 PM - system checkout limit
MIN_WORK_DURATION_HOURS = 8.5  # 8.5 hours minimum work duration

# Fungsi untuk mendapatkan alamat dari koordinat
def get_address_from_coordinates(latitude, longitude):
    geolocator = Nominatim(user_agent="cesgs_web_hr_app", timeout=10)
    try:
        location = geolocator.reverse(f"{latitude}, {longitude}", exactly_one=True, language='id')
        if location:
            return location.address
    except (GeocoderTimedOut, GeocoderServiceError) as e:
        print(f"DEBUG: Geocoding error for {latitude}, {longitude}: {e}")
        return None
    except Exception as e:
        print(f"DEBUG: An unexpected error occurred during geocoding for {latitude}, {longitude}: {e}")
        return None
    return None



def get_dashboard_url(user):
    """Helper untuk mendapatkan URL dashboard berdasarkan role user"""
    if user.role == 'HRD':
        return 'hrd_dashboard'
    elif user.role == 'Karyawan Tetap':
        return 'karyawan_dashboard'
    else:
        return 'magang_dashboard'


@login_required
def absen_view(request):
    """View untuk halaman absensi lokasi (8.5 jam fleksibel)"""
    dashboard_url = get_dashboard_url(request.user)
    
    try:
        karyawan = Karyawan.objects.get(user=request.user)
    except Karyawan.DoesNotExist:
        messages.error(request, 'Data karyawan tidak ditemukan')
        return redirect(dashboard_url)
    
    # Cek apakah sudah absen hari ini
    today = datetime.now().date()
    from apps.absensi.utils import is_wfa_day
    is_wfa, wfa_keterangan = is_wfa_day(today)

    absensi_hari_ini = AbsensiMagang.objects.filter(
        id_karyawan=karyawan,
        tanggal=today
    ).first()
    
    # "Sudah check-in" = record ada DAN jam_masuk terisi. Placeholder (dari cron reminder)
    # punya record tapi jam_masuk NULL → belum check-in.
    sudah_checkin = absensi_hari_ini is not None and absensi_hari_ini.jam_masuk is not None
    
    # Cek status waktu check-in (pakai sudah_checkin, bukan absensi_hari_ini)
    current_time = datetime.now().time()
    checkin_too_early = current_time < MIN_CHECKIN_TIME and not sudah_checkin
    # Flag awal warning zone (10:00 - 11:00), akan direvisi setelah cek Izin Telat
    checkin_in_warning_zone = REMINDER_CHECKIN_TIME <= current_time < MAX_CHECKIN_TIME and not sudah_checkin
    
    # Setelah pukul 10:00, check-in dianggap \"blocked\" secara default
    checkin_blocked = current_time >= REMINDER_CHECKIN_TIME and not sudah_checkin
    
    # Setelah pukul 10:00, hanya boleh check-in jika punya Izin Telat yang DISSETUJUI
    has_approved_late_permission = False
    if checkin_blocked:
        has_approved_late_permission = Izin.objects.filter(
            id_karyawan=karyawan,
            tanggal_izin=today,
            jenis_izin='telat',
            status='disetujui'
        ).exists()
    checkin_blocked_no_permission = checkin_blocked and not has_approved_late_permission
    
    # Penyesuaian flag untuk tampilan:
    # - Jika blocked TANPA izin telat  -> hanya tampil pesan blocked (tanpa warning countdown 11:00).
    # - Jika blocked DENGAN izin telat -> tidak tampilkan warning (izin sudah disetujui HR).
    if checkin_blocked_no_permission:
        checkin_in_warning_zone = False
    elif checkin_blocked and has_approved_late_permission:
        checkin_in_warning_zone = False  # Tidak tampilkan warning jika izin telat sudah disetujui HR
    
    if request.method == 'POST':
        # Block check-in before 6 AM
        if current_time < MIN_CHECKIN_TIME and not sudah_checkin:
            messages.error(request, f'Check-in hanya dapat dilakukan mulai pukul {MIN_CHECKIN_TIME.strftime("%H:%M")} WIB.')
            return redirect(dashboard_url)
        
        # Mulai pukul 10:00, WAJIB punya Izin Telat yang disetujui untuk bisa check-in.
        if current_time >= REMINDER_CHECKIN_TIME and not sudah_checkin:
            has_approved_late_permission_post = Izin.objects.filter(
                id_karyawan=karyawan,
                tanggal_izin=today,
                jenis_izin='telat',
                status='disetujui'
            ).exists()
            
            if not has_approved_late_permission_post:
                messages.error(
                    request,
                    'Setelah pukul 10:00 WIB, check-in hanya dapat dilakukan jika Anda memiliki '
                    'Izin Telat yang sudah disetujui HR.'
                )
                return redirect(dashboard_url)
            else:
                messages.warning(request, 'Check-in dengan izin telat yang disetujui HR.')
        
        form = AbsensiMagangForm(request.POST, user=request.user)
        if form.is_valid():
            if sudah_checkin:
                messages.info(request, 'Anda sudah melakukan absensi hari ini')
                return redirect('magang_dashboard')
            
            # Update placeholder (dari cron reminder) atau buat baru
            if absensi_hari_ini and absensi_hari_ini.jam_masuk is None:
                absensi = absensi_hari_ini
            else:
                absensi = form.save(commit=False)
                absensi.id_karyawan = karyawan
                absensi.tanggal = today
            
            absensi.jam_masuk = current_time
            
            # Set status based on check-in time
            if current_time < REMINDER_CHECKIN_TIME:
                absensi.status = 'Tepat Waktu'  # Normal check-in (6 AM - 10 AM)
            else:
                absensi.status = 'Terlambat'  # Warning zone check-in (10 AM - 11 AM)
            
            # Ambil koordinat dari form
            latitude = request.POST.get('latitude')
            longitude = request.POST.get('longitude')
            
            # Auto-set keterangan based on geofence: WFO jika di ASEEC, WFA jika di luar
            if latitude and longitude:
                # Check geofence to determine WFO or WFA
                location_result = validate_user_location(float(latitude), float(longitude))
                if location_result['valid']:
                    if location_result.get('is_wfa_day'):
                        absensi.keterangan = 'WFA'  # WFA day = WFA
                    else:
                        absensi.keterangan = 'WFO'  # Within geofence = WFO
                else:
                    absensi.keterangan = 'WFA'  # Outside geofence = WFA
                
                absensi.lokasi_masuk = f"{latitude}, {longitude}"
                address = get_address_from_coordinates(latitude, longitude)
                if address:
                    absensi.alamat_masuk = address
                else:
                    absensi.alamat_masuk = "Alamat tidak ditemukan"
            else:
                absensi.keterangan = 'WFA'  # No coords = default WFA
                absensi.lokasi_masuk = "Koordinat tidak tersedia"
                absensi.alamat_masuk = "Alamat tidak tersedia"
            
            absensi.save()
            messages.success(request, f'Absensi berhasil disimpan pada {current_time.strftime("%H:%M:%S")}')
            
            # Redirect berdasarkan role
            if request.user.role == 'HRD':
                return redirect('hrd_dashboard')
            elif request.user.role == 'Karyawan Tetap':
                return redirect('karyawan_dashboard')
            else:
                return redirect('magang_dashboard')
        else:
            # Form validation failed - show errors
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f'{field}: {error}')
    else:
        form = AbsensiMagangForm(user=request.user)
    
    context = {
        'form': form,
        'karyawan': karyawan,
        'absensi_hari_ini': absensi_hari_ini,
        'sudah_checkin': sudah_checkin,
        'title': 'Absensi Masuk',
        'is_wfa': is_wfa,
        'wfa_keterangan': wfa_keterangan,
        'checkin_too_early': checkin_too_early,
        'checkin_in_warning_zone': checkin_in_warning_zone,
        'checkin_blocked': checkin_blocked,
        'checkin_blocked_no_permission': checkin_blocked_no_permission,
        'min_checkin_time': MIN_CHECKIN_TIME.strftime('%H:%M'),
        'reminder_checkin_time': REMINDER_CHECKIN_TIME.strftime('%H:%M'),
        'max_checkin_time': MAX_CHECKIN_TIME.strftime('%H:%M'),
        'current_time': current_time.strftime('%H:%M:%S')
    }
    return render(request, 'absensi/absen.html', context)

@login_required
def absen_pulang_view(request):
    """View untuk halaman absensi pulang"""
    dashboard_url = get_dashboard_url(request.user)
    
    try:
        karyawan = Karyawan.objects.get(user=request.user)
    except Karyawan.DoesNotExist:
        messages.error(request, 'Data karyawan tidak ditemukan')
        return redirect(dashboard_url)
    
    # Cek apakah sudah absen masuk hari ini
    today = datetime.now().date()
    current_time = datetime.now().time()
    from apps.absensi.utils import is_wfa_day
    is_wfa, wfa_keterangan = is_wfa_day(today)

    absensi_hari_ini = AbsensiMagang.objects.filter(
        id_karyawan=karyawan,
        tanggal=today
    ).first()
    
    # Sudah check-in = record ada DAN jam_masuk terisi. Placeholder (cron) = belum check-in.
    sudah_checkin = absensi_hari_ini is not None and absensi_hari_ini.jam_masuk is not None
    
    # Jika belum check-in (no record atau placeholder): redirect
    if not sudah_checkin:
        if current_time > MAX_CHECKIN_TIME:
            has_approved_late_permission = Izin.objects.filter(
                id_karyawan=karyawan,
                tanggal_izin=today,
                jenis_izin='telat',
                status='disetujui'
            ).exists()
            if not has_approved_late_permission:
                messages.error(request, 
                    'Anda belum check-in hari ini dan sudah melewati batas waktu. '
                    'Silakan ajukan izin telat terlebih dahulu.')
                return redirect(dashboard_url)
        else:
            messages.error(request, 'Anda belum melakukan absen masuk hari ini. Absen pulang tidak dapat dilakukan.')
            return redirect(dashboard_url)
    
    # Cek waktu checkout
    checkout_blocked = current_time > MAX_CHECKOUT_TIME
    is_overtime = current_time >= OVERTIME_THRESHOLD and not absensi_hari_ini.jam_pulang
    
    # Cek durasi kerja (8.5 jam minimum)
    warning_message = None
    overtime_message = None
    jam_kerja = 0
    needs_confirmation = False
    ci_di_kantor = False
    
    if absensi_hari_ini.jam_masuk:
        jam_masuk_dt = datetime.combine(today, absensi_hari_ini.jam_masuk)
        sekarang = datetime.now()
        durasi = sekarang - jam_masuk_dt
        jam_kerja = durasi.total_seconds() / 3600
        
        # Tentukan kategori WFO/WFA berdasarkan kombinasi CI & CO
        ci_di_kantor = False
        if absensi_hari_ini.lokasi_masuk:
            try:
                lat_masuk_str, lon_masuk_str = absensi_hari_ini.lokasi_masuk.split(', ')
                ci_location_result = validate_user_location(float(lat_masuk_str), float(lon_masuk_str))
                ci_di_kantor = ci_location_result.get('valid', False) and not ci_location_result.get('is_wfa_day', False)
            except Exception:
                ci_di_kantor = False
        
        # Flag sementara untuk jenis kombinasi CI/CO, default diasumsikan WFO
        co_di_kantor = False
        # co_di_kantor baru bisa dihitung setelah dapat koordinat CO di blok POST,
        # tapi untuk perhitungan messaging awal kita pakai asumsi lama (berbasis jam saja).
        
        # Aturan durasi minimum:
        # - WFA murni (CI luar & CO luar): hard block < 8.5 jam (diterapkan di blok POST)
        # - Kasus lain: gunakan mekanisme existing (konfirmasi early checkout).
        if jam_kerja < MIN_WORK_DURATION_HOURS:
            jam_kurang = MIN_WORK_DURATION_HOURS - jam_kerja
            jam = int(jam_kurang)
            menit = int((jam_kurang - jam) * 60)
            warning_message = f'Anda belum mencapai {MIN_WORK_DURATION_HOURS} jam kerja. Masih kurang {jam} jam {menit} menit.'
            needs_confirmation = True
        
        # Check if working overtime (past 18:30) - tetap berlaku untuk WFO.
        if is_overtime:
            overtime_message = 'Anda sudah melewati jam pulang normal (18:30). Anda dapat mengajukan klaim lembur untuk hari ini (Max 49 rb).'
    
    if request.method == 'POST':
        # Block checkout after 10pm
        if current_time > MAX_CHECKOUT_TIME:
            messages.error(request, 'Batas waktu absen pulang adalah pukul 22:00. Silakan hubungi HRD.')
            return redirect(dashboard_url)
        
        # Untuk kasus non-WFA murni, tetap gunakan mekanisme konfirmasi early checkout existing
        if needs_confirmation and not request.POST.get('confirm_early'):
            messages.warning(request, f'Anda belum mencapai {MIN_WORK_DURATION_HOURS} jam kerja. Silakan konfirmasi untuk melanjutkan.')
            return redirect('absen_pulang_fleksibel')
        
        form = AbsensiPulangForm(request.POST, request.FILES, user=request.user)
        if form.is_valid():
            # PROSES ABSENSI PULANG
            absensi_hari_ini.jam_pulang = current_time
            
            # Ambil koordinat dari form
            latitude = request.POST.get('latitude')
            longitude = request.POST.get('longitude')
            
            if latitude and longitude:
                absensi_hari_ini.lokasi_pulang = f"{latitude}, {longitude}"
                address = get_address_from_coordinates(latitude, longitude)
                if address:
                    absensi_hari_ini.alamat_pulang = address
                else:
                    absensi_hari_ini.alamat_pulang = "Alamat tidak ditemukan"
                
                # CRITICAL: Determine WFO/WFA based on kombinasi CHECK-IN & CHECK-OUT location
                co_location_result = validate_user_location(float(latitude), float(longitude))
                
                co_di_kantor = co_location_result.get('valid', False) and not co_location_result.get('is_wfa_day', False)
                
                # Hitung ulang flag CI di kantor berdasarkan lokasi_masuk
                ci_di_kantor = False
                if absensi_hari_ini.lokasi_masuk:
                    try:
                        lat_masuk_str, lon_masuk_str = absensi_hari_ini.lokasi_masuk.split(', ')
                        ci_location_result = validate_user_location(float(lat_masuk_str), float(lon_masuk_str))
                        ci_di_kantor = ci_location_result.get('valid', False) and not ci_location_result.get('is_wfa_day', False)
                    except Exception:
                        ci_di_kantor = False
                
                # Kombinasi kasus:
                # 1) CI luar & CO luar  -> WFA murni (aturan durasi 8.5 jam)
                # 2) CI luar & CO kantor -> WFO (aturan lembur 18.30, min checkout 18:30)
                # 3) Lainnya mengikuti final berdasarkan lokasi CO (existing behavior).
                
                # NEW: CI luar + CO di ASEEC => checkout hanya boleh setelah 18:30
                if not ci_di_kantor and co_di_kantor and current_time < OVERTIME_THRESHOLD:
                    messages.error(request,
                        f'CI di luar kantor dan CO di kantor: Check-out hanya dapat dilakukan setelah pukul {OVERTIME_THRESHOLD.strftime("%H:%M")} WIB.')
                    return redirect('absen_pulang_fleksibel')
                
                if not ci_di_kantor and not co_di_kantor:
                    # WFA murni
                    final_keterangan = 'WFA'
                elif not ci_di_kantor and co_di_kantor:
                    # CI luar, CO kantor => WFO
                    final_keterangan = 'WFO'
                else:
                    # Default: gunakan hasil lokasi CO (WFO/WFA)
                    if co_di_kantor:
                        final_keterangan = 'WFO'
                    else:
                        final_keterangan = 'WFA'
                
                # Jika WFA murni, terapkan aturan durasi 8.5 jam (hard block + lembur berbasis durasi)
                if final_keterangan == 'WFA':
                    # Hitung durasi kerja terbaru
                    jam_masuk_dt = datetime.combine(today, absensi_hari_ini.jam_masuk)
                    sekarang = datetime.now()
                    durasi = (sekarang - jam_masuk_dt).total_seconds() / 3600
                    
                    if not ci_di_kantor and not co_di_kantor and durasi < MIN_WORK_DURATION_HOURS:
                        # WFA murni & durasi < 8.5 jam -> block checkout
                        jam_kurang = MIN_WORK_DURATION_HOURS - durasi
                        jam = int(jam_kurang)
                        menit = int((jam_kurang - jam) * 60)
                        messages.error(
                            request,
                            f'Untuk WFA, check-out hanya dapat dilakukan setelah {MIN_WORK_DURATION_HOURS} jam kerja. '
                            f'Saat ini baru {int(durasi)} jam {int((durasi - int(durasi)) * 60)} menit.'
                        )
                        return redirect('absen_pulang_fleksibel')
                    
                    # Set lembur berbasis durasi untuk WFA murni
                    if not ci_di_kantor and not co_di_kantor and durasi > MIN_WORK_DURATION_HOURS:
                        is_overtime = True
                    
                    # If WFA, validate mandatory documentation
                    aktivitas = request.POST.get('aktivitas_wfa', '').strip()
                    dokumen = request.FILES.get('dokumen_persetujuan')
                    
                    if not aktivitas:
                        messages.error(request, 
                            'WFA: Mohon isi aktivitas yang Anda kerjakan hari ini.')
                        return redirect('absen_pulang_fleksibel')
                    
                    if not dokumen:
                        messages.error(request, 
                            'WFA: Mohon upload dokumen persetujuan atasan langsung (.png, .jpg, atau .pdf).')
                        return redirect('absen_pulang_fleksibel')
                    
                    absensi_hari_ini.aktivitas_wfa = aktivitas
                    absensi_hari_ini.dokumen_persetujuan = dokumen
                
                absensi_hari_ini.keterangan = final_keterangan
                
            else:
                absensi_hari_ini.lokasi_pulang = "Koordinat tidak tersedia"
                absensi_hari_ini.alamat_pulang = "Alamat tidak tersedia"
                # Default to WFA if no coordinates
                absensi_hari_ini.keterangan = 'WFA'
            
            absensi_hari_ini.save()
            messages.success(request, f'Absen pulang berhasil pada {current_time.strftime("%H:%M:%S")} ({absensi_hari_ini.keterangan})')
            
            # Redirect berdasarkan role
            if request.user.role == 'HRD':
                return redirect('hrd_dashboard')
            elif request.user.role == 'Karyawan Tetap':
                return redirect('karyawan_dashboard')
            else:
                return redirect('magang_dashboard')
            

    else:
        form = AbsensiMagangForm(user=request.user)
    
    # Untuk frontend: CI di kantor dan datetime check-in (WFA pure = CI luar & CO luar)
    checkin_datetime_iso = None
    if absensi_hari_ini.jam_masuk:
        jam_masuk_dt = datetime.combine(today, absensi_hari_ini.jam_masuk)
        checkin_datetime_iso = jam_masuk_dt.strftime('%Y-%m-%dT%H:%M:%S')
    
    context = {
        'form': form,
        'karyawan': karyawan,
        'absensi_hari_ini': absensi_hari_ini,
        'title': 'Absensi Pulang',
        'warning_message': warning_message,
        'overtime_message': overtime_message,
        'jam_kerja': round(jam_kerja, 1),
        'is_wfa': is_wfa,
        'wfa_keterangan': wfa_keterangan,
        'needs_confirmation': needs_confirmation,
        'checkout_blocked': checkout_blocked,
        'is_overtime': is_overtime,
        'overtime_threshold': OVERTIME_THRESHOLD.strftime('%H:%M'),
        'max_checkout_time': MAX_CHECKOUT_TIME.strftime('%H:%M'),
        'min_work_hours': MIN_WORK_DURATION_HOURS,
        'ci_di_kantor': ci_di_kantor,
        'checkin_datetime_iso': checkin_datetime_iso or '',
        'ci_luar_co_aseec_min_time': OVERTIME_THRESHOLD.strftime('%H:%M'),
    }
    return render(request, 'absensi/absen_pulang.html', context)


@login_required
def riwayat_absensi(request):
    """View untuk menampilkan riwayat absensi karyawan (semua role)"""
    try:
        karyawan = Karyawan.objects.get(user=request.user)
    except Karyawan.DoesNotExist:
        messages.error(request, 'Data karyawan tidak ditemukan')
        return redirect('magang_dashboard')
    
    # Filter berdasarkan bulan dan tahun jika ada
    bulan = request.GET.get('bulan')
    tahun = request.GET.get('tahun')
    keterangan = request.GET.get('keterangan')
    
    # Buat query dasar
    absensi_query = AbsensiMagang.objects.filter(id_karyawan=karyawan).order_by('-tanggal', '-jam_masuk')
    
    # Terapkan filter
    if bulan and bulan.isdigit():
        absensi_query = absensi_query.filter(tanggal__month=int(bulan))
    
    if tahun and tahun.isdigit():
        absensi_query = absensi_query.filter(tanggal__year=int(tahun))
    
    if keterangan:
        absensi_query = absensi_query.filter(keterangan=keterangan)
    
    # Hitung total untuk statistik (WFO/WFA, bukan Tepat Waktu/Terlambat)
    total_wfo = absensi_query.filter(keterangan='WFO').count()
    total_wfa = absensi_query.filter(keterangan='WFA').count()
    total_absensi = absensi_query.count()
    
    # Pagination
    from django.core.paginator import Paginator
    paginator = Paginator(absensi_query, 3)
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
    
    context = {
        'absensi_list': absensi_list,
        'karyawan': karyawan,
        'selected_month': int(bulan) if bulan and bulan.isdigit() else '',
        'selected_year': int(tahun) if tahun and tahun.isdigit() else '',
        'selected_keterangan': keterangan if keterangan else '',
        'months': months,
        'years': years,
        'total_wfo': total_wfo,
        'total_wfa': total_wfa,
        'total_absensi': total_absensi,
        'title': 'Riwayat Absensi'
    }
    
    return render(request, 'absensi/riwayat_absensi.html', context)


@login_required
def check_location(request):
    """API untuk memeriksa apakah lokasi user berada dalam radius kantor."""
    latitude = request.GET.get('lat')
    longitude = request.GET.get('lon')
    
    if not latitude or not longitude:
        return JsonResponse({
            'status': 'error',
            'message': 'Koordinat latitude dan longitude diperlukan'
        }, status=400)
    
    try:
        # Validasi lokasi menggunakan geofencing (termasuk cek WFA day)
        result = validate_user_location(float(latitude), float(longitude))
        
        return JsonResponse({
            'status': 'success',
            'is_within_geofence': result['valid'],
            'distance': result['distance'],
            'office_name': result['office_name'],
            'radius': result['radius'],
            'message': result['message'],
            'is_wfa_day': result.get('is_wfa_day', False),
            'wfa_keterangan': result.get('wfa_keterangan', None)
        })
        
    except Exception as e:
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=500)


@login_required
def check_overtime_status(request):
    """
    API endpoint to check if user should receive overtime notification.
    Returns JSON with overtime status for browser notifications.
    """
    try:
        karyawan = Karyawan.objects.get(user=request.user)
    except Karyawan.DoesNotExist:
        return JsonResponse({
            'status': 'error',
            'message': 'Data karyawan tidak ditemukan'
        }, status=404)
    
    today = datetime.now().date()
    current_time = datetime.now().time()
    
    # Check if already checked in today
    absensi_hari_ini = AbsensiMagang.objects.filter(
        id_karyawan=karyawan,
        tanggal=today
    ).first()
    
    # Determine if notification should be shown
    should_notify = False
    has_checked_in = False
    has_checked_out = False
    
    if absensi_hari_ini:
        has_checked_in = absensi_hari_ini.jam_masuk is not None
        has_checked_out = absensi_hari_ini.jam_pulang is not None
        
        # Show notification if:
        # 1. Has checked in today
        # 2. Has NOT checked out yet
        # 3. Current time is past OVERTIME_THRESHOLD (18:30)
        if has_checked_in and not has_checked_out and current_time >= OVERTIME_THRESHOLD:
            should_notify = True
    
    return JsonResponse({
        'status': 'success',
        'should_notify': should_notify,
        'has_checked_in': has_checked_in,
        'has_checked_out': has_checked_out,
        'current_time': current_time.strftime('%H:%M:%S'),
        'overtime_threshold': OVERTIME_THRESHOLD.strftime('%H:%M'),
        'message': 'Anda sudah melewati jam pulang normal. Jangan lupa check-out dan ajukan klaim lembur jika diperlukan.' if should_notify else 'OK'
    })

