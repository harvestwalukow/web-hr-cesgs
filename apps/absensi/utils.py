import pandas as pd
import re
import logging
from rapidfuzz import process
from pytanggalmerah import TanggalMerah
from django.utils.timezone import make_aware
from datetime import datetime, date, time
from django.db.models import Q, Count
from apps.hrd.models import Karyawan, Izin, Cuti
from .models import Absensi, Rules

t = TanggalMerah(cache_path=None, cache_time=600)

logger = logging.getLogger(__name__)

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

            # Cek apakah karyawan memiliki izin WFH atau Telat di tanggal tsb
            izin_di_tanggal_ini = Izin.objects.filter(
                id_karyawan=karyawan,
                tanggal_izin=tanggal_absensi,
                jenis_izin__in=['wfh', 'telat'],
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
            elif izin_di_tanggal_ini:
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
