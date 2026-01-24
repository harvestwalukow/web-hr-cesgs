import pandas as pd
import re
import logging
import math
from rapidfuzz import process
from pytanggalmerah import TanggalMerah
from django.utils.timezone import make_aware
from datetime import datetime, date, time, timedelta
from django.db.models import Q, Count
from apps.hrd.models import Karyawan, Izin, Cuti
from .models import Absensi, Rules

t = TanggalMerah(cache_path=None, cache_time=600)

logger = logging.getLogger(__name__)


# ============================================
# GEOFENCING UTILITY FUNCTIONS
# ============================================

def calculate_distance(lat1, lon1, lat2, lon2):
    """
    Menghitung jarak antara dua koordinat menggunakan formula Haversine.
    Args:
        lat1, lon1: Koordinat titik pertama (user)
        lat2, lon2: Koordinat titik kedua (kantor)
    Returns:
        Jarak dalam meter
    """
    # Konversi ke float jika decimal
    lat1, lon1, lat2, lon2 = map(float, [lat1, lon1, lat2, lon2])
    
    # Radius bumi dalam meter
    R = 6371000
    
    # Konversi ke radian
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)
    
    # Formula Haversine
    a = math.sin(delta_phi / 2) ** 2 + \
        math.cos(phi1) * math.cos(phi2) * \
        math.sin(delta_lambda / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    
    distance = R * c
    return distance


def is_within_geofence(user_lat, user_lon, office_lat, office_lon, radius):
    """
    Memeriksa apakah user berada dalam radius kantor.
    Args:
        user_lat, user_lon: Koordinat user
        office_lat, office_lon: Koordinat kantor
        radius: Radius toleransi dalam meter
    Returns:
        Tuple (bool, float): (dalam_radius, jarak_dalam_meter)
    """
    distance = calculate_distance(user_lat, user_lon, office_lat, office_lon)
    return distance <= radius, distance


def get_active_office_location():
    """
    Mendapatkan lokasi kantor yang aktif.
    Returns:
        LokasiKantor object atau None
    """
    from .models import LokasiKantor
    return LokasiKantor.objects.filter(is_active=True).order_by('id').first()


def is_wfa_day(check_date=None):
    """
    Memeriksa apakah tanggal tertentu adalah hari WFA yang ditetapkan HR.
    Jika tanggal tersebut ada di CutiBersama dengan jenis WFA, 
    maka geofencing tidak perlu diterapkan.
    
    Args:
        check_date: Tanggal yang akan dicek (default: hari ini)
    Returns:
        Tuple (bool, str): (is_wfa, keterangan)
    """
    from apps.hrd.models import CutiBersama
    
    if check_date is None:
        check_date = date.today()
    
    # Cek apakah tanggal ada di CutiBersama
    cuti_bersama = CutiBersama.objects.filter(tanggal=check_date).first()
    
    if cuti_bersama:
        # Cek field 'jenis' untuk WFA
        if cuti_bersama.jenis == 'WFA':
            return True, cuti_bersama.keterangan or 'WFA'
            
        # Fallback ke 'keterangan' untuk legacy data (support WFH for backward compatibility)
        keterangan = cuti_bersama.keterangan or 'Cuti Bersama'
        keterangan_lower = keterangan.lower()
        if 'wfa' in keterangan_lower or 'wfh' in keterangan_lower or 'work from anywhere' in keterangan_lower or 'work from home' in keterangan_lower:
            return True, keterangan
    
    return False, None


def validate_user_location(user_lat, user_lon, check_date=None):
    """
    Memvalidasi apakah lokasi user berada dalam radius kantor yang aktif.
    Jika hari tersebut adalah WFA day, geofencing di-bypass tetapi koordinat tetap dicatat.
    
    Args:
        user_lat, user_lon: Koordinat user
        check_date: Tanggal untuk cek WFA (default: hari ini)
    Returns:
        Dict dengan hasil validasi:
        {
            'valid': bool,
            'distance': float (dalam meter) atau None,
            'office_name': str atau None,
            'radius': int atau None,
            'message': str,
            'is_wfa_day': bool,
            'wfa_keterangan': str atau None
        }
    """
    # Cek apakah hari ini adalah WFA day
    wfa_day, wfa_keterangan = is_wfa_day(check_date)
    
    # Tetap hitung jarak ke kantor untuk audit (jika ada lokasi kantor aktif)
    office = get_active_office_location()
    distance = None
    within_radius = False

    if office and user_lat is not None and user_lon is not None:
        office_lat = float(office.latitude)
        office_lon = float(office.longitude)
        radius_m = int(office.radius)
        within_radius, dist = is_within_geofence(
            float(user_lat), float(user_lon),
            office_lat, office_lon,
            radius_m
        )
        distance = round(dist, 2)
        logger.info(
            'geofence check: user=(%s, %s) office=(%s, %s) radius=%sm -> distance=%.2fm within=%s',
            user_lat, user_lon, office_lat, office_lon, radius_m, distance, within_radius
        )

    if wfa_day:
        return {
            'valid': True,
            'distance': distance,
            'office_name': office.nama if office else None,
            'radius': office.radius if office else None,
            'message': f'Hari ini adalah {wfa_keterangan}. Anda bisa absen dari mana saja.',
            'is_wfa_day': True,
            'wfa_keterangan': wfa_keterangan
        }
    
    if not office:
        return {
            'valid': False,
            'distance': None,
            'office_name': None,
            'radius': None,
            'message': 'Tidak ada lokasi kantor yang aktif. Hubungi HRD.',
            'is_wfa_day': False,
            'wfa_keterangan': None
        }
    
    if within_radius:
        return {
            'valid': True,
            'distance': distance,
            'office_name': office.nama,
            'radius': office.radius,
            'message': f'Anda berada dalam radius {office.nama} ({round(distance, 0)} meter dari pusat)',
            'is_wfa_day': False,
            'wfa_keterangan': None
        }
    else:
        return {
            'valid': False,
            'distance': distance,
            'office_name': office.nama,
            'radius': office.radius,
            'message': f'Anda berada di luar radius {office.nama}',
            'is_wfa_day': False,
            'wfa_keterangan': None
        }


#  Parsing Waktu dengan Format `HH:MM`
def parse_time(value):
    """Mengubah string waktu `HH:MM` menjadi format time Django."""
    try:
        if isinstance(value, str) and re.match(r'^\d{2}:\d{2}$', value.strip()):
            return datetime.strptime(value.strip(), "%H:%M").time()
    except ValueError:
        return None  
    return None

# Deteksi Hari Libur dari `pytanggalmerah`
def is_hari_libur(tahun, bulan, day):
    """Cek apakah tanggal adalah hari libur atau akhir pekan (Sabtu/Minggu)."""
    t.set_date(str(tahun), f"{bulan:02d}", f"{day:02d}")  
    tanggal_obj = date(tahun, bulan, day)
    return tanggal_obj.weekday() in [5, 6] or t.check()  

# Ekstraksi Nama dari File Excel
def extract_id_name(data):
    """Mengekstrak ID dan Nama dari file absensi."""
    filtered_data = data[data.iloc[:, 4] == "User ID.："]
    extracted_names = filtered_data.iloc[:, 11].values  
    return extracted_names

# Identifikasi Baris Waktu
def identify_time_rows(data):
    """Menentukan baris yang berisi data waktu."""
    user_id_rows = data[data.iloc[:, 4] == "User ID.："].index
    return user_id_rows


def process_absensi(file_path, bulan, tahun, selected_rule, file_name=None, file_url=None, file_stream=None):
    try:
        # Jika tersedia stream in-memory, gunakan itu
        if file_stream is not None:
            data = pd.read_excel(file_stream, sheet_name="Catatan Kehadiran Karyawan", dtype=str)
        else:
            data = pd.read_excel(file_path, sheet_name="Catatan Kehadiran Karyawan", dtype=str)
    except Exception as e:
        logger.error(f"❌ ERROR: Gagal membaca file {file_path or 'in-memory'} - {e}")
        return

    daftar_karyawan = {
        (k.nama_catatan_kehadiran.upper() if k.nama_catatan_kehadiran else k.nama.upper()): k
        for k in Karyawan.objects.all()
    }

    extracted_names = extract_id_name(data)
    user_id_rows = identify_time_rows(data)

    for idx, user_row in enumerate(user_id_rows):
        user_name = extracted_names[idx].strip().upper()
        best_match = process.extractOne(user_name, daftar_karyawan.keys(), score_cutoff=80)

        if best_match:
            best_matched_name, _, _ = best_match
            karyawan = daftar_karyawan[best_matched_name]
            logger.info(f" Matched: {user_name} -> {best_matched_name}")
        else:
            logger.warning(f"⚠️ WARNING: Nama {user_name} tidak cocok di database.")
            continue

        for day in range(1, 32):
            try:
                tanggal_absensi = date(tahun, bulan, day)
            except ValueError:
                continue

            is_libur = is_hari_libur(tahun, bulan, day)
            jam_masuk, jam_keluar = None, None
            status_absensi = "Tidak Hadir"

            try:
                time_data = data.iloc[user_row + 2, day]
            except IndexError:
                time_data = None

            if pd.notna(time_data):
                entries = str(time_data).split('\n')
                valid_times = [t.strip() for t in entries if re.match(r'^\d{2}:\d{2}$', t.strip())]

                if valid_times:
                    parsed_times = [parse_time(t) for t in valid_times if parse_time(t)]

                    if len(parsed_times) == 1:
                        if parsed_times[0] > time(16, 0):
                            jam_keluar = parsed_times[0]
                        else:
                            jam_masuk = parsed_times[0]
                    elif len(parsed_times) >= 2:
                        jam_masuk = parsed_times[0]
                        jam_keluar = parsed_times[-1]

            # Cek apakah karyawan memiliki izin WFA atau Telat di tanggal tsb
            izin_di_tanggal_ini = Izin.objects.filter(
                id_karyawan=karyawan,
                tanggal_izin=tanggal_absensi,
                jenis_izin__in=['wfa', 'wfh', 'telat'],  # Support both WFA and legacy WFH
                status='disetujui'
            ).exists()

            izin_klaim_masuk_siang_h_minus_1 = Izin.objects.filter(
                id_karyawan=karyawan,
                tanggal_izin=tanggal_absensi - timedelta(days=1),
                jenis_izin='klaim_lembur',
                kompensasi_lembur='masuk_siang',
                status='disetujui'
            ).exists()
            
            # Cek apakah karyawan memiliki cuti di tanggal tsb
            cuti_di_tanggal_ini = Cuti.objects.filter(
                id_karyawan=karyawan,
                tanggal_mulai__lte=tanggal_absensi,
                tanggal_selesai__gte=tanggal_absensi,
                status='disetujui'
            ).exists()

            if is_libur:
                status_absensi = "Libur"
            elif cuti_di_tanggal_ini:
                status_absensi = "Cuti"
            elif izin_di_tanggal_ini or izin_klaim_masuk_siang_h_minus_1:
                status_absensi = "Tepat Waktu"
            elif jam_masuk:
                if selected_rule:
                    jam_masuk_dt = datetime.combine(date.today(), jam_masuk)
                    aturan_dt = datetime.combine(date.today(), selected_rule.jam_masuk)
                    if (jam_masuk_dt - aturan_dt).total_seconds() / 60 > selected_rule.toleransi_telat:
                        status_absensi = "Terlambat"
                    else:
                        status_absensi = "Tepat Waktu"
                else:
                    status_absensi = "Tepat Waktu"
            elif jam_keluar and not jam_masuk:
                status_absensi = "Terlambat"

            Absensi.objects.update_or_create(
                id_karyawan=karyawan,
                tanggal=tanggal_absensi,
                defaults={
                    "bulan": bulan,
                    "tahun": tahun,
                    "status_absensi": status_absensi,
                    "is_libur": is_libur,
                    "jam_masuk": jam_masuk,
                    "jam_keluar": jam_keluar,
                    "rules": selected_rule,
                    "nama_file": file_name,
                    "file_url": file_url,
                    "created_at": datetime.now()
                }
            )

    check_and_mark_holiday(bulan, tahun)
    logger.info(f"Data absensi untuk bulan {bulan}-{tahun} berhasil diproses!")


#  Fungsi untuk Menandai Hari Libur Jika Semua Tidak Masuk
def check_and_mark_holiday(bulan, tahun):
    """Cek apakah ada hari dalam bulan tersebut di mana semua karyawan tidak masuk, lalu tandai sebagai libur."""
    tanggal_absensi = Absensi.objects.filter(bulan=bulan, tahun=tahun).values_list('tanggal', flat=True).distinct()

    for tanggal in tanggal_absensi:
        jumlah_hadir = Absensi.objects.filter(
            tanggal=tanggal
        ).exclude(
            Q(jam_masuk__isnull=True) & Q(jam_keluar__isnull=True)
        ).count()

        if jumlah_hadir == 0:  
            Absensi.objects.filter(tanggal=tanggal).update(status_absensi="Libur", is_libur=True)
            logger.info(f"📅 {tanggal} ditandai sebagai LIBUR karena tidak ada yang hadir.")

    logger.info(f" Pengecekan libur selesai untuk bulan {bulan}-{tahun}!")
