import json
from datetime import datetime, time
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponse
from django.conf import settings
from django.contrib import messages
from django.views.decorators.csrf import csrf_exempt
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut, GeocoderServiceError
from apps.authentication.decorators import role_required
from apps.hrd.models import Karyawan
from ..models import AbsensiMagang
from ..forms import AbsensiMagangForm, AbsensiPulangForm
from ..utils import validate_user_location

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
    """View untuk halaman absensi lokasi (8 jam fleksibel)"""
    dashboard_url = get_dashboard_url(request.user)
    
    try:
        karyawan = Karyawan.objects.get(user=request.user)
    except Karyawan.DoesNotExist:
        messages.error(request, 'Data karyawan tidak ditemukan')
        return redirect(dashboard_url)
    
    # Cek apakah sudah absen hari ini
    today = datetime.now().date()
    absensi_hari_ini = AbsensiMagang.objects.filter(
        id_karyawan=karyawan,
        tanggal=today
    ).first()
    
    if request.method == 'POST':
        form = AbsensiMagangForm(request.POST, user=request.user)
        if form.is_valid():
            if absensi_hari_ini:
                messages.info(request, 'Anda sudah melakukan absensi hari ini')
                return redirect('magang_dashboard')
            
            # Validasi keterangan
            keterangan = form.cleaned_data.get('keterangan')
            if not keterangan:
                messages.error(request, 'Keterangan wajib diisi')
                return redirect('absen_magang')
            
            # PROSES ABSENSI (8 jam fleksibel - tidak ada status tepat waktu/terlambat)
            absensi = form.save(commit=False)
            absensi.id_karyawan = karyawan
            absensi.tanggal = today
            current_time = datetime.now().time()
            absensi.jam_masuk = current_time
            absensi.keterangan = keterangan
            absensi.status = 'Tepat Waktu'  # Status tidak ditampilkan (8 jam fleksibel)
            
            # Ambil koordinat dari form
            latitude = request.POST.get('latitude')
            longitude = request.POST.get('longitude')
            
            if latitude and longitude:
                absensi.lokasi_masuk = f"{latitude}, {longitude}"
                address = get_address_from_coordinates(latitude, longitude)
                if address:
                    absensi.alamat_masuk = address
                else:
                    absensi.alamat_masuk = "Alamat tidak ditemukan"
            else:
                absensi.lokasi_masuk = "Koordinat tidak tersedia"
                absensi.alamat_masuk = "Alamat tidak tersedia"
            
            # Simpan screenshot bukti (jika dikirim)
            screenshot_data = request.POST.get('screenshot_data')
            if screenshot_data:
                try:
                    format, imgstr = screenshot_data.split(';base64,')
                    ext = format.split('/')[-1]
                    file_name = f"absen_{karyawan.id}_{today}.{ext}"
                    data = ContentFile(base64.b64decode(imgstr), name=file_name)
                    absensi.screenshot_masuk = data
                except Exception as e:
                    print(f"Error saving screenshot: {e}")
            
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
        form = AbsensiMagangForm(user=request.user)
    
    context = {
        'form': form,
        'karyawan': karyawan,
        'absensi_hari_ini': absensi_hari_ini,
        'title': 'Absensi Masuk'
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
    absensi_hari_ini = AbsensiMagang.objects.filter(
        id_karyawan=karyawan,
        tanggal=today
    ).first()
    
    if not absensi_hari_ini:
        messages.error(request, 'Anda belum melakukan absen masuk hari ini. Absen pulang tidak dapat dilakukan.')
        return redirect(dashboard_url)
    
    # Cek apakah sudah mencapai minimal 8 jam kerja
    if absensi_hari_ini.jam_masuk:
        jam_masuk_dt = datetime.combine(today, absensi_hari_ini.jam_masuk)
        sekarang = datetime.now()
        durasi = sekarang - jam_masuk_dt
        jam_kerja = durasi.total_seconds() / 3600
        
        if jam_kerja < 8:
            jam_kurang = 8 - jam_kerja
            jam = int(jam_kurang)
            menit = int((jam_kurang - jam) * 60)
            messages.warning(request, f'Anda belum mencapai 8 jam kerja. Masih kurang {jam} jam {menit} menit.')
            return redirect(dashboard_url)
    

    
    if request.method == 'POST':
        form = AbsensiPulangForm(request.POST, user=request.user)
        if form.is_valid():
            # PROSES ABSENSI PULANG
            current_time = datetime.now().time()
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
            
            # Simpan screenshot bukti (jika ada)
            screenshot_data = request.POST.get('screenshot_data')
            if screenshot_data:
                try:
                    format, imgstr = screenshot_data.split(';base64,')
                    ext = format.split('/')[-1]
                    file_name = f"pulang_{karyawan.id}_{today}.{ext}"
                    data = ContentFile(base64.b64decode(imgstr), name=file_name)
                    absensi_hari_ini.screenshot_pulang = data
                except Exception as e:
                    print(f"Error saving return screenshot: {e}")
            
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
        'title': 'Absensi Pulang'
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
    
    # Hitung total untuk statistik
    total_tepat_waktu = absensi_query.filter(status='Tepat waktu').count()
    total_terlambat = absensi_query.filter(status='Terlambat').count()
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
        'total_tepat_waktu': total_tepat_waktu,
        'total_terlambat': total_terlambat,
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
