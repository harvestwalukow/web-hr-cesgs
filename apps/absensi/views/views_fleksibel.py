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
from apps.hrd.models import Karyawan
from ..models import AbsensiMagang
from ..forms import AbsensiMagangForm, AbsensiPulangForm
from ..utils import validate_user_location

# Time restrictions
MAX_CHECKIN_TIME = time(13, 0)  # 1:00 PM
MAX_CHECKOUT_TIME = time(22, 0)  # 10:00 PM
MIN_WORK_DURATION_HOURS = 9  # 9 hours minimum

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
    """View untuk halaman absensi lokasi (9 jam fleksibel)"""
    dashboard_url = get_dashboard_url(request.user)
    
    try:
        karyawan = Karyawan.objects.get(user=request.user)
    except Karyawan.DoesNotExist:
        messages.error(request, 'Data karyawan tidak ditemukan')
        return redirect(dashboard_url)
    
    # Cek apakah sudah absen hari ini
    today = datetime.now().date()
    from apps.absensi.utils import is_wfh_day
    is_wfh, wfh_keterangan = is_wfh_day(today)

    absensi_hari_ini = AbsensiMagang.objects.filter(
        id_karyawan=karyawan,
        tanggal=today
    ).first()
    
    # Cek apakah sudah melewati batas waktu check-in (13:00)
    current_time = datetime.now().time()
    checkin_blocked = current_time > MAX_CHECKIN_TIME and not absensi_hari_ini
    
    if request.method == 'POST':
        # Block check-in after 1pm
        if current_time > MAX_CHECKIN_TIME and not absensi_hari_ini:
            messages.error(request, 'Batas waktu absen masuk adalah pukul 13:00. Silakan hubungi HRD.')
            return redirect(dashboard_url)
        
        form = AbsensiMagangForm(request.POST, user=request.user)
        if form.is_valid():
            if absensi_hari_ini:
                messages.info(request, 'Anda sudah melakukan absensi hari ini')
                return redirect('magang_dashboard')
            
            # PROSES ABSENSI (9 jam fleksibel - tidak ada status tepat waktu/terlambat)
            absensi = form.save(commit=False)
            absensi.id_karyawan = karyawan
            absensi.tanggal = today
            absensi.jam_masuk = current_time
            absensi.status = 'Tepat Waktu'  # Status tidak ditampilkan (9 jam fleksibel)
            
            # Ambil koordinat dari form
            latitude = request.POST.get('latitude')
            longitude = request.POST.get('longitude')
            
            # Auto-set keterangan based on geofence: WFO jika di ASEEC, WFH jika di luar
            if latitude and longitude:
                # Check geofence to determine WFO or WFH
                location_result = validate_user_location(float(latitude), float(longitude))
                if location_result['valid']:
                    if location_result.get('is_wfh_day'):
                        absensi.keterangan = 'WFH'  # WFH day = WFH
                    else:
                        absensi.keterangan = 'WFO'  # Within geofence = WFO
                else:
                    absensi.keterangan = 'WFH'  # Outside geofence = WFH
                
                absensi.lokasi_masuk = f"{latitude}, {longitude}"
                address = get_address_from_coordinates(latitude, longitude)
                if address:
                    absensi.alamat_masuk = address
                else:
                    absensi.alamat_masuk = "Alamat tidak ditemukan"
            else:
                absensi.keterangan = 'WFH'  # No coords = default WFH
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
        'title': 'Absensi Masuk',
        'is_wfh': is_wfh,
        'wfh_keterangan': wfh_keterangan,
        'checkin_blocked': checkin_blocked,
        'max_checkin_time': MAX_CHECKIN_TIME.strftime('%H:%M')
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
    from apps.absensi.utils import is_wfh_day
    is_wfh, wfh_keterangan = is_wfh_day(today)

    absensi_hari_ini = AbsensiMagang.objects.filter(
        id_karyawan=karyawan,
        tanggal=today
    ).first()
    
    if not absensi_hari_ini:
        messages.error(request, 'Anda belum melakukan absen masuk hari ini. Absen pulang tidak dapat dilakukan.')
        return redirect(dashboard_url)
    
    # Cek waktu checkout (max 10pm)
    current_time = datetime.now().time()
    checkout_blocked = current_time > MAX_CHECKOUT_TIME
    
    # Cek durasi kerja (9 jam minimum dengan opsi konfirmasi)
    warning_message = None
    jam_kerja = 0
    needs_confirmation = False
    
    if absensi_hari_ini.jam_masuk:
        jam_masuk_dt = datetime.combine(today, absensi_hari_ini.jam_masuk)
        sekarang = datetime.now()
        durasi = sekarang - jam_masuk_dt
        jam_kerja = durasi.total_seconds() / 3600
        
        if jam_kerja < MIN_WORK_DURATION_HOURS:
            jam_kurang = MIN_WORK_DURATION_HOURS - jam_kerja
            jam = int(jam_kurang)
            menit = int((jam_kurang - jam) * 60)
            warning_message = f'Anda belum mencapai {MIN_WORK_DURATION_HOURS} jam kerja. Masih kurang {jam} jam {menit} menit.'
            needs_confirmation = True
    
    if request.method == 'POST':
        # Block checkout after 10pm
        if current_time > MAX_CHECKOUT_TIME:
            messages.error(request, 'Batas waktu absen pulang adalah pukul 22:00. Silakan hubungi HRD.')
            return redirect(dashboard_url)
        
        # Check if early checkout confirmation is required
        if needs_confirmation and not request.POST.get('confirm_early'):
            messages.warning(request, 'Anda belum mencapai 9 jam kerja. Silakan konfirmasi untuk melanjutkan.')
            return redirect('absen_pulang_fleksibel')
        
        form = AbsensiPulangForm(request.POST, user=request.user)
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
            else:
                absensi_hari_ini.lokasi_pulang = "Koordinat tidak tersedia"
                absensi_hari_ini.alamat_pulang = "Alamat tidak tersedia"
            
            absensi_hari_ini.save()
            messages.success(request, f'Absen pulang berhasil pada {current_time.strftime("%H:%M:%S")}')
            
            # Redirect berdasarkan role
            if request.user.role == 'HRD':
                return redirect('hrd_dashboard')
            elif request.user.role == 'Karyawan Tetap':
                return redirect('karyawan_dashboard')
            else:
                return redirect('magang_dashboard')
            

    else:
        form = AbsensiMagangForm(user=request.user)
    
    context = {
        'form': form,
        'karyawan': karyawan,
        'absensi_hari_ini': absensi_hari_ini,
        'title': 'Absensi Pulang',
        'warning_message': warning_message,
        'jam_kerja': round(jam_kerja, 1),
        'is_wfh': is_wfh,
        'wfh_keterangan': wfh_keterangan,
        'needs_confirmation': needs_confirmation,
        'checkout_blocked': checkout_blocked,
        'max_checkout_time': MAX_CHECKOUT_TIME.strftime('%H:%M'),
        'min_work_hours': MIN_WORK_DURATION_HOURS
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
    
    # Hitung total untuk statistik (WFO/WFH, bukan Tepat Waktu/Terlambat)
    total_wfo = absensi_query.filter(keterangan='WFO').count()
    total_wfh = absensi_query.filter(keterangan='WFH').count()
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
        'total_wfh': total_wfh,
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
        # Validasi lokasi menggunakan geofencing (termasuk cek WFH day)
        result = validate_user_location(float(latitude), float(longitude))
        
        return JsonResponse({
            'status': 'success',
            'is_within_geofence': result['valid'],
            'distance': result['distance'],
            'office_name': result['office_name'],
            'radius': result['radius'],
            'message': result['message'],
            'is_wfh_day': result.get('is_wfh_day', False),
            'wfh_keterangan': result.get('wfh_keterangan', None)
        })
        
    except Exception as e:
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=500)

