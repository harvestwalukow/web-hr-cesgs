from datetime import datetime, timedelta
from django.db.models import Q
from apps.hrd.models import JatahCuti, DetailJatahCuti, CutiBersama, Karyawan
import logging
from django.contrib.auth.models import User
from ..models import Cuti
from pytanggalmerah import TanggalMerah

def is_holiday_or_weekend(check_date):
    """
    Memeriksa apakah suatu tanggal adalah hari Sabtu/Minggu atau tanggal merah.
    """
    # Pengecualian khusus untuk 26 Desember 2025 (WFH)
    if check_date.year == 2025 and check_date.month == 12 and check_date.day == 26:
        return False # Dianggap hari kerja (WFH)

    # Cek apakah hari Sabtu (5) atau Minggu (6)
    if check_date.weekday() >= 5:
        return True

    # Cek apakah tanggal cuti bersama (hanya jenis 'Cuti Bersama' yang dianggap libur)
    if CutiBersama.objects.filter(tanggal=check_date, jenis='Cuti Bersama').exists():
        return True

    # Cek apakah tanggal merah nasional menggunakan pytanggalmerah
    try:
        t = TanggalMerah()
        t.set_date(str(check_date.year), f"{check_date.month:02d}", f"{check_date.day:02d}")
        # Filter keluar hari Minggu karena sudah ditangani di atas
        if t.check() and "Minggu" not in t.get_event():
            return True
    except Exception:
        # Abaikan error jika pytanggalmerah gagal (misal tahun terlalu jauh)
        pass

    return False

def hitung_hari_kerja(start_date, end_date):
    """
    Menghitung jumlah hari kerja (tidak termasuk Sabtu, Minggu, dan tanggal merah) 
    dalam rentang tanggal tertentu.
    """
    delta = end_date - start_date
    hari_kerja = 0
    for i in range(delta.days + 1):
        day = start_date + timedelta(days=i)
        if not is_holiday_or_weekend(day):
            hari_kerja += 1
    return hari_kerja

def tentukan_bulan_tersedia_berdasarkan_kontrak(karyawan, tahun):
    """
    Menentukan bulan-bulan yang tersedia untuk jatah cuti berdasarkan periode kontrak.
    Bulan sebelum mulai kontrak dan setelah batas kontrak akan dikunci (tidak tersedia).
    
    Args:
        karyawan: Objek Karyawan
        tahun: Tahun yang akan dihitung
        
    Returns:
        dict: Dictionary dengan key bulan (1-12) dan value boolean (tersedia/tidak)
    """
    bulan_tersedia = {}
    
    # Default semua bulan tidak tersedia (terkunci)
    for bulan in range(1, 13):
        bulan_tersedia[bulan] = False
    
    
    # Jika tidak ada tanggal mulai kontrak, gunakan logika lama (semua bulan tersedia)
    if not karyawan.mulai_kontrak:
        for bulan in range(1, 13):
            bulan_tersedia[bulan] = True
        return bulan_tersedia
    
    # Tentukan bulan mulai dan bulan akhir kontrak untuk tahun ini
    bulan_mulai = None
    bulan_akhir = None
    
    # Cek mulai kontrak
    if karyawan.mulai_kontrak.year < tahun:
        # Kontrak dimulai sebelum tahun ini, mulai dari Januari
        bulan_mulai = 1
    elif karyawan.mulai_kontrak.year == tahun:
        # Kontrak dimulai di tahun ini
        bulan_mulai = karyawan.mulai_kontrak.month
    else:
        # Kontrak belum dimulai di tahun ini, semua bulan tetap terkunci
        return bulan_tersedia
    
    # Cek batas kontrak
    if karyawan.batas_kontrak:
        if karyawan.batas_kontrak.year > tahun:
            # Kontrak berakhir setelah tahun ini, sampai Desember
            bulan_akhir = 12
        elif karyawan.batas_kontrak.year == tahun:
            # Kontrak berakhir di tahun ini
            bulan_akhir = karyawan.batas_kontrak.month
        else:
            # Kontrak sudah berakhir sebelum tahun ini, semua bulan tetap terkunci
            return bulan_tersedia
    else:
        # Tidak ada batas kontrak, sampai Desember
        bulan_akhir = 12
    
    # Set bulan dalam periode kontrak sebagai tersedia
    if bulan_mulai is not None and bulan_akhir is not None:
        for bulan in range(bulan_mulai, bulan_akhir + 1):
            bulan_tersedia[bulan] = True
    
    return bulan_tersedia

def hitung_jatah_cuti(karyawan, tahun, isi_detail_cuti_bersama=True):
    """
    Menghitung jatah cuti karyawan untuk tahun tertentu.
    Fungsi ini akan membuat atau memperbarui record JatahCuti dan DetailJatahCuti.
    Hanya berlaku untuk role Karyawan Tetap dan HRD.
    Jatah cuti dihitung berdasarkan periode kontrak karyawan.
    """
    # Cek apakah karyawan memiliki role yang tepat
    if karyawan.user.role not in ['Karyawan Tetap', 'HRD']:
        return None
    
    # Hitung total cuti berdasarkan periode kontrak untuk tahun ini
    bulan_tersedia_kontrak = tentukan_bulan_tersedia_berdasarkan_kontrak(karyawan, tahun)
    total_cuti_berdasarkan_kontrak = sum(1 for tersedia in bulan_tersedia_kontrak.values() if tersedia)
    
    # Jika tidak ada bulan yang tersedia, hapus jatah cuti yang ada (jika ada) dan return None
    if total_cuti_berdasarkan_kontrak == 0:
        # Hapus jatah cuti yang ada untuk tahun ini jika tidak ada bulan yang tersedia
        existing_jatah = JatahCuti.objects.filter(karyawan=karyawan, tahun=tahun).first()
        if existing_jatah:
            # Hapus detail yang tidak dipakai
            DetailJatahCuti.objects.filter(jatah_cuti=existing_jatah, dipakai=False).delete()
            # Jika tidak ada detail yang tersisa, hapus jatah cuti
            if not DetailJatahCuti.objects.filter(jatah_cuti=existing_jatah).exists():
                existing_jatah.delete()
        return None
    
    # Cari atau buat JatahCuti
    jatah_cuti, created = JatahCuti.objects.get_or_create(
        karyawan=karyawan,
        tahun=tahun,
        defaults={
            'total_cuti': total_cuti_berdasarkan_kontrak,
            'sisa_cuti': total_cuti_berdasarkan_kontrak
        }
    )
    
    # Update total_cuti jika ada perubahan periode kontrak
    if jatah_cuti.total_cuti != total_cuti_berdasarkan_kontrak:
        jatah_cuti.total_cuti = total_cuti_berdasarkan_kontrak
    
    # Cek apakah ada cuti bersama yang perlu diisi untuk tahun ini
    cuti_bersama_yang_perlu_diisi = []
    if isi_detail_cuti_bersama:
        # Hanya cuti bersama yang bertipe 'Cuti Bersama' yang memotong jatah cuti
        cuti_bersama_tahun_ini = CutiBersama.objects.filter(tanggal__year=tahun, jenis='Cuti Bersama')
        for cb in cuti_bersama_tahun_ini:
            # Cek apakah cuti bersama ini sudah diisi dalam detail
            detail_cb = DetailJatahCuti.objects.filter(
                jatah_cuti=jatah_cuti,
                tahun=tahun,
                bulan=cb.tanggal.month,
                keterangan__icontains='cuti bersama'
            ).first()
            
            if not detail_cb:
                cuti_bersama_yang_perlu_diisi.append(cb)
    
    # Hitung sisa cuti berdasarkan detail yang sudah dipakai
    if not created:
        # Hitung jumlah detail yang sudah dipakai
        detail_dipakai = DetailJatahCuti.objects.filter(
            jatah_cuti=jatah_cuti,
            tahun=tahun,
            dipakai=True
        ).count()
        
        # Sisa cuti = total cuti berdasarkan kontrak - detail yang sudah dipakai - cuti bersama yang perlu diisi
        sisa_cuti_baru = total_cuti_berdasarkan_kontrak - detail_dipakai - len(cuti_bersama_yang_perlu_diisi)
        jatah_cuti.sisa_cuti = max(0, sisa_cuti_baru)  # Pastikan tidak negatif
    else:
        # Untuk jatah cuti baru, kurangi dengan cuti bersama
        jatah_cuti.sisa_cuti = total_cuti_berdasarkan_kontrak - len(cuti_bersama_yang_perlu_diisi)
    
    jatah_cuti.save()
    
    # Inisialisasi DetailJatahCuti untuk semua bulan dengan penanda tersedia/tidak tersedia
    # Cek apakah sudah ada detail untuk tahun ini
    existing_details = DetailJatahCuti.objects.filter(jatah_cuti=jatah_cuti, tahun=tahun)
    existing_bulan = [detail.bulan for detail in existing_details]
    
    # Update atau hapus detail yang sudah ada
    for detail in existing_details:
        tersedia_baru = bulan_tersedia_kontrak.get(detail.bulan, False)
        
        if not tersedia_baru:
            # Jika bulan tidak tersedia, hapus detail (kecuali jika sudah dipakai)
            if not detail.dipakai:
                detail.delete()
                continue
        
        # Update status tersedia dan keterangan untuk detail yang sudah ada
        keterangan_baru = detail.keterangan  # Pertahankan keterangan yang sudah ada jika dipakai
        
        if not tersedia_baru and not detail.dipakai:
            # Tentukan keterangan baru untuk bulan yang tidak tersedia
            if karyawan.mulai_kontrak and detail.bulan < karyawan.mulai_kontrak.month and karyawan.mulai_kontrak.year == tahun:
                keterangan_baru = 'Belum masuk kerja'
            elif karyawan.batas_kontrak and detail.bulan > karyawan.batas_kontrak.month and karyawan.batas_kontrak.year == tahun:
                keterangan_baru = 'Kontrak sudah berakhir'
            elif not karyawan.mulai_kontrak:
                keterangan_baru = 'Tidak ada data kontrak'
            else:
                keterangan_baru = 'Di luar periode kontrak'
        elif tersedia_baru and not detail.dipakai:
            # Jika bulan tersedia dan tidak dipakai, kosongkan keterangan
            keterangan_baru = ''
        
        # Update detail jika ada perubahan
        if detail.tersedia != tersedia_baru or detail.keterangan != keterangan_baru:
            detail.tersedia = tersedia_baru
            detail.keterangan = keterangan_baru
            detail.save()
    
    # Buat detail untuk bulan yang belum ada
    for bulan in range(1, 13):
        if bulan not in existing_bulan:
            tersedia = bulan_tersedia_kontrak.get(bulan, False)
            
            # Tentukan keterangan berdasarkan status ketersediaan
            keterangan = ''
            if not tersedia:
                if karyawan.mulai_kontrak and bulan < karyawan.mulai_kontrak.month and karyawan.mulai_kontrak.year == tahun:
                    keterangan = 'Belum masuk kerja'
                elif karyawan.batas_kontrak and bulan > karyawan.batas_kontrak.month and karyawan.batas_kontrak.year == tahun:
                    keterangan = 'Kontrak sudah berakhir'
                elif not karyawan.mulai_kontrak:
                    keterangan = 'Tidak ada data kontrak'
                else:
                    keterangan = 'Di luar periode kontrak'
            
            DetailJatahCuti.objects.create(
                jatah_cuti=jatah_cuti,
                tahun=tahun,
                bulan=bulan,
                dipakai=False,
                jumlah_hari=0,
                keterangan=keterangan,
                tersedia=tersedia
            )
    
    # Jika ada cuti bersama yang perlu diisi, selalu isi ke dalam detail
    # Ini memastikan bahwa saldo cuti yang dikurangi dengan cuti bersama
    # selalu tercermin dalam detail cuti
    if cuti_bersama_yang_perlu_diisi and isi_detail_cuti_bersama:
        isi_dari_bulan_kanan_cuti_bersama(jatah_cuti, cuti_bersama_yang_perlu_diisi, tahun)
    
    return jatah_cuti

def get_kosong_slot_tahun_sama(karyawan, jumlah_hari, tahun):
    """Mencari slot kosong DetailJatahCuti untuk karyawan hanya di tahun yang sama.
    
    Fungsi ini hanya akan mencari slot kosong di tahun yang ditentukan,
    sesuai dengan kebijakan baru bahwa cuti bersama hanya boleh memotong
    jatah cuti di tahun yang sama.
    
    Args:
        karyawan: Objek Karyawan yang akan dicari slot kosongnya
        jumlah_hari: Jumlah slot kosong yang dibutuhkan
        tahun: Tahun yang akan dicari slot kosongnya
        
    Returns:
        List of DetailJatahCuti: Daftar slot kosong yang ditemukan di tahun tersebut
    """
    bulan_kosong = []
    
    # Cari jatah cuti untuk tahun yang ditentukan
    jatah_cuti_tahun = JatahCuti.objects.filter(karyawan=karyawan, tahun=tahun).first()
    
    if jatah_cuti_tahun:
        # Cari detail kosong untuk jatah cuti tahun ini
        detail_kosong = DetailJatahCuti.objects.filter(
            jatah_cuti=jatah_cuti_tahun,
            dipakai=False
        ).order_by('bulan')  # Urutkan dari bulan terkecil
        
        for detail in detail_kosong:
            bulan_kosong.append(detail)
            
            # Jika sudah cukup, hentikan pencarian
            if len(bulan_kosong) >= jumlah_hari:
                break
    
    return bulan_kosong

def get_kosong_global_slot(karyawan, jumlah_hari, tahun_referensi):
    """Mencari slot kosong DetailJatahCuti untuk karyawan dari tahun manapun.
    
    Fungsi ini akan mencari slot kosong dengan prioritas sebagai berikut:
    1. Tahun-tahun sebelumnya (hingga 3 tahun ke belakang)
    2. Tahun referensi (biasanya tahun saat ini)
    3. Tahun-tahun berikutnya (hingga 3 tahun ke depan)
    
    Hasil pencarian diurutkan dari tahun dan bulan paling kecil (paling kiri/awal).
    Ini memungkinkan cuti bersama untuk mengisi slot kosong di tahun-tahun sebelumnya terlebih dahulu.
    
    Args:
        karyawan: Objek Karyawan yang akan dicari slot kosongnya
        jumlah_hari: Jumlah slot kosong yang dibutuhkan
        tahun_referensi: Tahun referensi untuk pencarian (biasanya tahun saat ini)
        
    Returns:
        List of DetailJatahCuti: Daftar slot kosong yang ditemukan, diurutkan dari tahun dan bulan paling kecil
    """
    # Inisialisasi list untuk menyimpan slot kosong
    bulan_kosong = []
    
    # 1. Cari di tahun-tahun sebelumnya terlebih dahulu
    # Cari jatah cuti untuk tahun-tahun sebelumnya (hingga 3 tahun ke belakang)
    # Mulai dari tahun paling jauh untuk memastikan pengisian dari kiri (tahun paling awal)
    for tahun_cek in range(tahun_referensi-3, tahun_referensi):
        if tahun_cek <= 0:  # Pastikan tahun valid
            continue
            
        jatah_cuti_tahun = JatahCuti.objects.filter(karyawan=karyawan, tahun=tahun_cek).first()
        if jatah_cuti_tahun:
            # Cari detail kosong untuk jatah cuti ini
            detail_kosong = DetailJatahCuti.objects.filter(
                jatah_cuti=jatah_cuti_tahun,
                dipakai=False
            ).order_by('bulan')  # Urutkan dari bulan terkecil
            
            for detail in detail_kosong:
                bulan_kosong.append(detail)
                
                # Jika sudah cukup, hentikan pencarian
                if len(bulan_kosong) >= jumlah_hari:
                    break
            
            # Jika sudah cukup, hentikan pencarian
            if len(bulan_kosong) >= jumlah_hari:
                break
    
    # 2. Jika masih belum cukup, cari slot kosong di tahun referensi
    if len(bulan_kosong) < jumlah_hari:
        jatah_cuti_tahun_ini = JatahCuti.objects.filter(karyawan=karyawan, tahun=tahun_referensi).first()
        if jatah_cuti_tahun_ini:
            detail_kosong = DetailJatahCuti.objects.filter(
                jatah_cuti=jatah_cuti_tahun_ini,
                dipakai=False
            ).order_by('bulan')  # Urutkan dari bulan terkecil
            
            for detail in detail_kosong:
                bulan_kosong.append(detail)
                
                # Jika sudah cukup, hentikan pencarian
                if len(bulan_kosong) >= jumlah_hari:
                    break
    
    # 3. Jika masih belum cukup, cari di tahun-tahun berikutnya
    if len(bulan_kosong) < jumlah_hari:
        # Cari jatah cuti untuk tahun-tahun berikutnya
        for tahun_cek in range(tahun_referensi+1, tahun_referensi+4):
            jatah_cuti_tahun = JatahCuti.objects.filter(karyawan=karyawan, tahun=tahun_cek).first()
            if not jatah_cuti_tahun:
                # Buat jatah cuti untuk tahun ini jika belum ada
                jatah_cuti_tahun = hitung_jatah_cuti(karyawan, tahun_cek)
            
            if jatah_cuti_tahun:
                # Cari detail kosong untuk jatah cuti ini
                detail_kosong = DetailJatahCuti.objects.filter(
                    jatah_cuti=jatah_cuti_tahun,
                    dipakai=False
                ).order_by('bulan')  # Urutkan dari bulan terkecil
                
                for detail in detail_kosong:
                    bulan_kosong.append(detail)
                    
                    # Jika sudah cukup, hentikan pencarian
                    if len(bulan_kosong) >= jumlah_hari:
                        break
                
                # Jika sudah cukup, hentikan pencarian
                if len(bulan_kosong) >= jumlah_hari:
                    break
    
    # Urutkan hasil berdasarkan tahun dan bulan dari yang terkecil (paling kiri/awal)
    bulan_kosong.sort(key=lambda x: (x.tahun, x.bulan))
    
    return bulan_kosong

def isi_slot_dan_update_sisa_cuti(karyawan, bulan_kosong, keterangan_list, tahun, is_cuti_bersama=True, allow_minus=False, tanggal_mulai=None, tanggal_selesai=None):
    logger = logging.getLogger(__name__)
    
    print(f"===== MULAI PENGISIAN SLOT CUTI =====")
    print(f"Karyawan: {karyawan.nama}, Jumlah slot yang akan diisi: {len(bulan_kosong)}, Tahun referensi: {tahun}")
    logger.info(f"===== MULAI PENGISIAN SLOT CUTI =====")
    logger.info(f"Karyawan: {karyawan.nama}, Jumlah slot yang akan diisi: {len(bulan_kosong)}, Tahun referensi: {tahun}")
    
    # Kelompokkan slot kosong berdasarkan tahun untuk memperbarui sisa_cuti per tahun
    slot_per_tahun = {}
    
    # Buat daftar tanggal cuti jika ini adalah cuti tahunan (bukan cuti bersama)
    tanggal_cuti = []
    if not is_cuti_bersama and tanggal_mulai and tanggal_selesai:
        current_date = tanggal_mulai
        while current_date <= tanggal_selesai:
            tanggal_cuti.append(current_date)
            current_date += timedelta(days=1)
    
    for i, detail in enumerate(bulan_kosong):
        if i < len(keterangan_list):
            if is_cuti_bersama:
                keterangan = f"Cuti Bersama: {keterangan_list[i].keterangan or keterangan_list[i].tanggal}"
            else:
                keterangan = keterangan_list[i]
    
    # Isi slot kosong
    for i, detail in enumerate(bulan_kosong):
        if i < len(keterangan_list):
            # Log status slot sebelum diubah
            
            detail.dipakai = True
            detail.jumlah_hari = 1
            
            # Set tanggal_terpakai jika ini adalah cuti tahunan dan ada daftar tanggal
            if not is_cuti_bersama and i < len(tanggal_cuti):
                detail.tanggal_terpakai = tanggal_cuti[i]
            
            # Set keterangan berdasarkan jenis item
            if is_cuti_bersama:
                detail.keterangan = f'Cuti Bersama: {keterangan_list[i].keterangan or keterangan_list[i].tanggal}'
            else:
                detail.keterangan = keterangan_list[i]
                
            detail.save()
            
            # Kelompokkan berdasarkan tahun untuk memperbarui sisa_cuti
            tahun_slot = detail.jatah_cuti.tahun
            if tahun_slot not in slot_per_tahun:
                slot_per_tahun[tahun_slot] = 0
            slot_per_tahun[tahun_slot] += 1
            
    
    # Hitung ulang sisa cuti untuk setiap tahun yang terdampak
    tahun_terdampak = set(slot_per_tahun.keys())
    tahun_terdampak.add(tahun)  # Pastikan tahun referensi juga dihitung ulang
    
    
    for tahun_slot in tahun_terdampak:
        jatah_cuti_tahun = JatahCuti.objects.filter(karyawan=karyawan, tahun=tahun_slot).first()
        if jatah_cuti_tahun:
            # Simpan nilai sisa cuti sebelumnya untuk log
            sisa_cuti_sebelumnya = jatah_cuti_tahun.sisa_cuti
            
            # Hitung total detail yang dipakai untuk tahun ini
            total_dipakai = DetailJatahCuti.objects.filter(
                jatah_cuti=jatah_cuti_tahun,
                dipakai=True
            ).count()
            
            # Perbarui sisa cuti, pastikan tidak menjadi negatif jika tidak allow_minus
            if not allow_minus:
                jatah_cuti_tahun.sisa_cuti = max(0, jatah_cuti_tahun.total_cuti - total_dipakai)
            else:
                jatah_cuti_tahun.sisa_cuti = jatah_cuti_tahun.total_cuti - total_dipakai
            
            jatah_cuti_tahun.save()
            
    return True

def isi_dari_bulan_kiri(jatah_cuti, jumlah_hari, keterangan, tahun):
    """Mengisi cuti tahunan mulai dari slot kosong paling kiri (tahun paling awal).
    
    Fungsi ini akan mencari slot kosong mulai dari tahun-tahun sebelumnya (hingga 3 tahun ke belakang),
    kemudian tahun saat ini, dan jika masih belum cukup, akan mencari di tahun-tahun berikutnya.
    Slot kosong akan diurutkan dari tahun dan bulan paling kecil (paling kiri/awal) untuk memastikan
    cuti tahunan diletakkan pada slot kosong paling awal yang tersedia.
    """
    # Gunakan fungsi get_kosong_global_slot untuk mencari slot kosong dari semua tahun yang tersedia
    bulan_kosong = get_kosong_global_slot(jatah_cuti.karyawan, jumlah_hari, tahun)
    
    # Buat list keterangan dengan panjang jumlah_hari
    keterangan_list = [keterangan] * jumlah_hari
    
    # Gunakan fungsi umum untuk mengisi slot dan memperbarui sisa cuti
    return isi_slot_dan_update_sisa_cuti(jatah_cuti.karyawan, bulan_kosong, keterangan_list, tahun, is_cuti_bersama=False)

def proses_cuti_hangus(karyawan, tahun_sekarang):
    """Memproses jatah cuti yang sudah hangus (lebih dari 1 tahun).
    
    Fungsi ini akan menandai cuti yang sudah hangus dan memperbarui saldo cuti
    di tahun tersebut. Cuti yang hangus akan mengurangi saldo cuti di tahun
    yang bersangkutan.
    """
    logger = logging.getLogger(__name__)
    
    current_date = datetime.now().date()
    tahun_batas = current_date.year - 1
    bulan_batas = current_date.month
    
    print(f"===== MULAI PROSES CUTI HANGUS =====")
    print(f"Memproses cuti hangus untuk karyawan {karyawan.nama}, tahun referensi: {tahun_sekarang}")
    logger.info(f"===== MULAI PROSES CUTI HANGUS =====")
    logger.info(f"Memproses cuti hangus untuk karyawan {karyawan.nama}, tahun referensi: {tahun_sekarang}")
    
    # Cari detail jatah cuti yang sudah expired
    detail_expired = DetailJatahCuti.objects.filter(
        jatah_cuti__karyawan=karyawan,
        tahun__lt=tahun_batas,
        dipakai=False
    )
    
    # Juga cari yang tahun sama tapi bulan sudah lewat 1 tahun
    detail_expired_bulan = DetailJatahCuti.objects.filter(
        jatah_cuti__karyawan=karyawan,
        tahun=tahun_batas,
        bulan__lt=bulan_batas,
        dipakai=False
    )
    
    # Kumpulkan detail yang hangus berdasarkan tahun untuk memperbarui saldo cuti
    hangus_per_tahun = {}
    
    # Tandai sebagai hangus dan hitung jumlah yang hangus per tahun
    for detail in detail_expired:
        detail.dipakai = True
        detail.jumlah_hari = 1
        detail.keterangan = 'Hangus (Expired)'
        detail.save()
        
        # Log detail cuti hangus
        print(f"Cuti hangus: Karyawan {karyawan.nama}, Tahun {detail.tahun}, Bulan {detail.bulan}")
        logger.info(f"Cuti hangus: Karyawan {karyawan.nama}, Tahun {detail.tahun}, Bulan {detail.bulan}")
        
        # Tambahkan ke perhitungan per tahun
        tahun = detail.tahun
        if tahun not in hangus_per_tahun:
            hangus_per_tahun[tahun] = 0
        hangus_per_tahun[tahun] += 1
    
    for detail in detail_expired_bulan:
        detail.dipakai = True
        detail.jumlah_hari = 1
        detail.keterangan = 'Hangus (Expired)'
        detail.save()
        
        # Log detail cuti hangus
        print(f"Cuti hangus (bulan): Karyawan {karyawan.nama}, Tahun {detail.tahun}, Bulan {detail.bulan}")
        logger.info(f"Cuti hangus (bulan): Karyawan {karyawan.nama}, Tahun {detail.tahun}, Bulan {detail.bulan}")
        
        # Tambahkan ke perhitungan per tahun
        tahun = detail.tahun
        if tahun not in hangus_per_tahun:
            hangus_per_tahun[tahun] = 0
        hangus_per_tahun[tahun] += 1
    
    # Perbarui saldo cuti untuk setiap tahun yang memiliki cuti hangus
    for tahun, jumlah_hangus in hangus_per_tahun.items():
        jatah_cuti = JatahCuti.objects.filter(karyawan=karyawan, tahun=tahun).first()
        if jatah_cuti:
            # Simpan nilai sisa cuti sebelumnya untuk log
            sisa_cuti_sebelumnya = jatah_cuti.sisa_cuti
            
            # Kurangi sisa cuti dengan jumlah yang hangus
            jatah_cuti.sisa_cuti = max(0, jatah_cuti.sisa_cuti - jumlah_hangus)
            jatah_cuti.save()
            
            # Log perubahan sisa cuti
            print(f"Pembaruan jatah cuti hangus: Karyawan {karyawan.nama}, Tahun {tahun}, Jumlah hangus: {jumlah_hangus}, Sisa cuti sebelumnya: {sisa_cuti_sebelumnya}, Sisa cuti sekarang: {jatah_cuti.sisa_cuti}")
            logger.info(f"Pembaruan jatah cuti hangus: Karyawan {karyawan.nama}, Tahun {tahun}, Jumlah hangus: {jumlah_hangus}, Sisa cuti sebelumnya: {sisa_cuti_sebelumnya}, Sisa cuti sekarang: {jatah_cuti.sisa_cuti}")
            
            # Panggil fungsi untuk menggeser data cuti ke kiri
            # Ini hanya menggeser data, tidak mengubah sisa_cuti lagi
            geser_data_cuti_ke_kiri(jatah_cuti, tahun)
    
    print(f"===== SELESAI PROSES CUTI HANGUS =====\n")
    logger.info(f"===== SELESAI PROSES CUTI HANGUS =====\n")

def isi_cuti_tahunan(karyawan, tanggal_mulai, tanggal_selesai, allow_minus=False):
    """Mengisi detail jatah cuti untuk cuti tahunan yang disetujui dari bulan kosong paling kiri.
    
    Fungsi ini akan mencari slot kosong mulai dari tahun-tahun sebelumnya (hingga 3 tahun ke belakang),
    kemudian tahun saat ini, dan jika masih belum cukup, akan mencari di tahun-tahun berikutnya.
    Hal ini memungkinkan cuti tahunan untuk mengisi slot kosong di tahun-tahun sebelumnya.
    
    Args:
        karyawan: Objek Karyawan yang mengajukan cuti
        tanggal_mulai: Tanggal mulai cuti
        tanggal_selesai: Tanggal selesai cuti
        allow_minus: Boolean, jika True maka saldo cuti boleh minus
        
    Returns:
        Boolean: True jika berhasil, False jika gagal (saldo tidak cukup)
    """
    tahun = tanggal_mulai.year
    
    # Pastikan ada jatah cuti untuk tahun ini
    jatah_cuti = hitung_jatah_cuti(karyawan, tahun, isi_detail_cuti_bersama=False)
    if not jatah_cuti:
        return False
    
    # Hitung jumlah hari kerja cuti
    jumlah_hari = hitung_hari_kerja(tanggal_mulai, tanggal_selesai)
    
    # Cek saldo cuti jika tidak diizinkan minus
    if not allow_minus and jatah_cuti.sisa_cuti < jumlah_hari:
        return False
    
    # Isi dari bulan kosong paling kiri, mulai dari tahun-tahun sebelumnya
    keterangan_cuti = f'Cuti Tahunan: {tanggal_mulai} - {tanggal_selesai}'
    
    # Gunakan fungsi get_kosong_global_slot untuk mencari slot kosong dari semua tahun yang tersedia
    bulan_kosong = get_kosong_global_slot(karyawan, jumlah_hari, tahun)
    
    # Urutkan bulan_kosong berdasarkan tahun dan bulan dari yang terkecil (paling kiri/awal)
    bulan_kosong.sort(key=lambda x: (x.tahun, x.bulan))
    
    # Buat list keterangan dengan panjang jumlah_hari
    keterangan_list = [keterangan_cuti] * jumlah_hari
    
    # Gunakan fungsi umum untuk mengisi slot dan memperbarui sisa cuti
    result = isi_slot_dan_update_sisa_cuti(karyawan, bulan_kosong, keterangan_list, tahun, is_cuti_bersama=False, allow_minus=allow_minus, tanggal_mulai=tanggal_mulai, tanggal_selesai=tanggal_selesai)
    
    # Hitung ulang sisa cuti untuk memastikan saldo cuti diperbarui dengan benar
    if result:
        rapikan_cuti_tahunan(karyawan, tahun)
    
    return result


def kembalikan_jatah_tidak_ambil_cuti(karyawan, cuti_bersama_list):
    """Memproses ketika HR menyetujui 'Tidak Ambil Cuti Bersama' dan mengembalikan jatah cuti."""
    tahun = None
    jatah_cuti = None
    
    for cb in cuti_bersama_list:
        # Cari detail jatah cuti yang berisi cuti bersama ini
        detail_cuti_bersama = DetailJatahCuti.objects.filter(
            jatah_cuti__karyawan=karyawan,
            dipakai=True,
            keterangan__icontains=f'Cuti Bersama: {cb.keterangan or cb.tanggal}'
        ).first()
        
        if detail_cuti_bersama:
            # Simpan tahun dan jatah cuti untuk digunakan nanti
            if not tahun:
                tahun = detail_cuti_bersama.tahun
            if not jatah_cuti:
                jatah_cuti = detail_cuti_bersama.jatah_cuti
                
            # Kosongkan kembali slot bulan terakhir yang terisi
            detail_cuti_bersama.dipakai = False
            detail_cuti_bersama.jumlah_hari = 0
            detail_cuti_bersama.keterangan = ''
            detail_cuti_bersama.save()
            
            # Tambah sisa cuti
            jatah_cuti = detail_cuti_bersama.jatah_cuti
            jatah_cuti.sisa_cuti += 1
            jatah_cuti.save()
    
    # Jika ada detail yang diubah, panggil fungsi untuk menggeser data ke kiri
    if tahun and jatah_cuti:
        geser_data_cuti_ke_kiri(jatah_cuti, tahun)
        
        # Hitung ulang sisa cuti untuk memastikan saldo cuti diperbarui dengan benar
        rapikan_cuti_tahunan(karyawan, tahun)

def geser_data_cuti_ke_kiri(jatah_cuti, tahun):
    """Menggeser data cuti ke slot kosong paling kiri.
    
    Fungsi ini akan mengambil semua detail jatah cuti yang terpakai,
    mengurutkannya berdasarkan keterangan (untuk menjaga urutan pengambilan cuti),
    lalu menggesernya ke slot kosong paling kiri.
    
    Fungsi ini juga memungkinkan pergeseran data cuti antar tahun, misalnya
    cuti bersama tahun 2025 bisa mengisi slot kosong di tahun 2024.
    
    Args:
        jatah_cuti: Objek JatahCuti yang akan dirapikan
        tahun: Tahun dari detail jatah cuti yang akan dirapikan
    """
    # Ambil semua detail jatah cuti untuk tahun ini
    detail_jatah_cuti = DetailJatahCuti.objects.filter(
        jatah_cuti=jatah_cuti,
        tahun=tahun
    ).order_by('bulan')
    
    # Ambil semua detail yang terpakai dan urutkan berdasarkan keterangan
    # untuk menjaga urutan pengambilan cuti
    detail_terpakai = list(detail_jatah_cuti.filter(dipakai=True).order_by('keterangan'))
    
    if not detail_terpakai:
        return
    
    # Kosongkan semua detail untuk tahun ini
    for detail in detail_jatah_cuti:
        detail.dipakai = False
        detail.jumlah_hari = 0
        detail.keterangan = ''
        detail.save()
    
    # Isi ulang dari bulan paling kiri, mencari slot kosong di tahun-tahun sebelumnya juga
    for i, detail in enumerate(detail_terpakai):
        # Cari detail kosong paling kiri, mulai dari tahun-tahun sebelumnya
        # Mulai dari tahun sebelumnya dan mundur hingga 3 tahun ke belakang
        detail_kosong = None
        
        # Cek tahun saat ini dan tahun-tahun sebelumnya
        for tahun_cek in range(tahun-3, tahun+1):
            if tahun_cek <= 0:  # Pastikan tahun valid
                continue
                
            # Cari slot kosong di tahun ini
            detail_kosong_tahun = DetailJatahCuti.objects.filter(
                jatah_cuti=jatah_cuti,
                tahun=tahun_cek,
                dipakai=False
            ).order_by('tahun', 'bulan').first()
            
            if detail_kosong_tahun:
                detail_kosong = detail_kosong_tahun
                break
        
        # Jika tidak ada slot kosong di tahun-tahun sebelumnya, cek tahun berikutnya
        if not detail_kosong:
            # Cari di tahun berikutnya
            detail_kosong = DetailJatahCuti.objects.filter(
                jatah_cuti=jatah_cuti,
                tahun__gt=tahun,
                dipakai=False
            ).order_by('tahun', 'bulan').first()
        
        if detail_kosong:
            # Pindahkan data
            detail_kosong.dipakai = True
            detail_kosong.jumlah_hari = detail.jumlah_hari
            detail_kosong.keterangan = detail.keterangan
            detail_kosong.save()

def rapikan_cuti_tahunan(karyawan, tahun):
    """Merapikan data cuti tahunan setelah pengembalian jatah cuti."""
    # Pastikan ada jatah cuti untuk tahun ini
    jatah_cuti = JatahCuti.objects.filter(karyawan=karyawan, tahun=tahun).first()
    
    if not jatah_cuti:
        return
    
    # Ambil semua detail jatah cuti untuk tahun ini
    detail_jatah_cuti = DetailJatahCuti.objects.filter(
        jatah_cuti=jatah_cuti,
        tahun=tahun
    ).order_by('bulan')
    
    # Hitung ulang sisa cuti berdasarkan detail yang dipakai
    total_dipakai = detail_jatah_cuti.filter(dipakai=True).count()
    jatah_cuti.sisa_cuti = jatah_cuti.total_cuti - total_dipakai
    jatah_cuti.save()
    
    # Geser data cuti ke kiri
    geser_data_cuti_ke_kiri(jatah_cuti, tahun)

def get_jatah_cuti_data(tahun, karyawan_id=None):
    """Mengambil data jatah cuti untuk ditampilkan di frontend."""
    # Filter karyawan
    karyawan_filter = Q(user__role='HRD') | Q(user__role='Karyawan Tetap')
    karyawan_filter &= Q(status_keaktifan='Aktif')
    
    if karyawan_id:
        karyawan_filter &= Q(id=karyawan_id)
    
    # Ambil semua karyawan dengan prefetch untuk user (untuk role)
    karyawan_list = Karyawan.objects.filter(karyawan_filter).select_related('user').order_by('nama')
    
    # Ambil semua jatah cuti untuk tahun yang diminta
    jatah_cuti_dict = {}
    jatah_cuti_list = JatahCuti.objects.filter(tahun=tahun, karyawan__in=karyawan_list)
    
    # Buat dictionary untuk akses cepat
    for jc in jatah_cuti_list:
        jatah_cuti_dict[jc.karyawan_id] = jc
    
    # Ambil semua detail jatah cuti sekaligus untuk mengurangi jumlah query
    all_details = DetailJatahCuti.objects.filter(
        jatah_cuti__in=jatah_cuti_list,
        tahun=tahun
    ).select_related('jatah_cuti')
    
    # Buat dictionary untuk akses cepat ke detail per karyawan dan bulan
    detail_dict = {}
    for detail in all_details:
        karyawan_id = detail.jatah_cuti.karyawan_id
        if karyawan_id not in detail_dict:
            detail_dict[karyawan_id] = {}
        detail_dict[karyawan_id][detail.bulan] = detail
    
    data = []
    current_date = datetime.now().date()
    
    for karyawan in karyawan_list:
        # Cek apakah karyawan sudah masuk kerja pada tahun yang diminta
        if karyawan.mulai_kontrak and karyawan.mulai_kontrak.year > tahun:
            # Karyawan belum masuk kerja pada tahun ini, skip
            continue
        
        # Gunakan fungsi helper untuk menentukan bulan yang tersedia berdasarkan kontrak
        bulan_tersedia_kontrak = tentukan_bulan_tersedia_berdasarkan_kontrak(karyawan, tahun)
        
        # Ambil jatah cuti dari dictionary atau buat baru jika belum ada
        jatah_cuti = jatah_cuti_dict.get(karyawan.id)
        
        if not jatah_cuti:
            # Buat jatah cuti baru jika belum ada
            jatah_cuti = hitung_jatah_cuti(karyawan, tahun, isi_detail_cuti_bersama=False)
            if jatah_cuti:
                jatah_cuti_dict[karyawan.id] = jatah_cuti
        
        if not jatah_cuti:
            continue
        
        # Ambil detail per bulan dari dictionary yang sudah dibuat
        bulan_data = []
        karyawan_details = detail_dict.get(karyawan.id, {})
        
        for bulan in range(1, 13):
            detail = karyawan_details.get(bulan)
            
            # Tentukan apakah bulan ini tersedia berdasarkan periode kontrak
            tersedia = bulan_tersedia_kontrak.get(bulan, False)

            if detail:
                # Cek apakah expired
                expired = False
                if tahun < current_date.year - 1:
                    expired = True
                elif tahun == current_date.year - 1 and bulan < current_date.month:
                    expired = True
                
                bulan_data.append({
                    'bulan': bulan,
                    'dipakai': detail.dipakai,
                    'jumlah_hari': detail.jumlah_hari,
                    'keterangan': detail.keterangan,
                    'expired': expired,
                    'tersedia': detail.tersedia if hasattr(detail, 'tersedia') else tersedia
                })
            else:
                # Tentukan keterangan berdasarkan status ketersediaan
                keterangan = ''
                if not tersedia:
                    if karyawan.mulai_kontrak and bulan < karyawan.mulai_kontrak.month and karyawan.mulai_kontrak.year == tahun:
                        keterangan = 'Belum masuk kerja'
                    elif karyawan.batas_kontrak and bulan > karyawan.batas_kontrak.month and karyawan.batas_kontrak.year == tahun:
                        keterangan = 'Kontrak sudah berakhir'
                    elif not karyawan.mulai_kontrak:
                        keterangan = 'Tidak ada data kontrak'
                    else:
                        keterangan = 'Di luar periode kontrak'
                
                bulan_data.append({
                    'bulan': bulan,
                    'dipakai': False,
                    'jumlah_hari': 0,
                    'keterangan': keterangan,
                    'expired': False,
                    'tersedia': tersedia
                })
        
        data.append({
            'karyawan': karyawan,
            'jatah_cuti': jatah_cuti,
            'bulan_data': bulan_data,
            'sisa_cuti': jatah_cuti.sisa_cuti
        })
    
    return data

def validate_manual_cuti_input(karyawan_id, tahun, bulan, dipakai, tanggal_mulai=None, tanggal_selesai=None, jenis_cuti=None, skip_overlap_check=False):
    """
    Validasi input manual jatah cuti sebelum menyimpan.
    
    Args:
        skip_overlap_check: Jika True, skip validasi overlap dengan cuti yang sudah ada
    
    Returns:
        dict: {
            'is_valid': bool,
            'errors': list,
            'jumlah_hari': int (jika valid)
        }
    """
    from datetime import datetime, timedelta
    from ..models import Cuti, Karyawan, JatahCuti, DetailJatahCuti
    
    errors = []
    jumlah_hari = 0
    
    try:
        karyawan = Karyawan.objects.get(id=karyawan_id)
        jatah_cuti = JatahCuti.objects.get(karyawan=karyawan, tahun=tahun)
    except (Karyawan.DoesNotExist, JatahCuti.DoesNotExist) as e:
        errors.append("Data karyawan atau jatah cuti tidak ditemukan")
        return {'is_valid': False, 'errors': errors, 'jumlah_hari': 0}
    
    # 1. Validasi field wajib jika dipakai=True
    if dipakai:
        if not tanggal_mulai:
            errors.append("Tanggal mulai cuti harus diisi")
        if not tanggal_selesai:
            errors.append("Tanggal selesai cuti harus diisi")
        if not jenis_cuti:
            errors.append("Jenis cuti harus dipilih")
        
        # Jika ada field yang kosong, return early
        if errors:
            return {'is_valid': False, 'errors': errors, 'jumlah_hari': 0}
    
    # 2. Validasi konsistensi field saat dipakai=False
    if not dipakai:
        if tanggal_mulai or tanggal_selesai or jenis_cuti:
            errors.append("Tanggal dan jenis cuti harus dikosongkan jika status tidak dipakai")
        return {'is_valid': len(errors) == 0, 'errors': errors, 'jumlah_hari': 0}
    
    # Konversi tanggal string ke datetime.date
    try:
        if isinstance(tanggal_mulai, str):
            tanggal_mulai = datetime.strptime(tanggal_mulai, '%Y-%m-%d').date()
        if isinstance(tanggal_selesai, str):
            tanggal_selesai = datetime.strptime(tanggal_selesai, '%Y-%m-%d').date()
    except ValueError:
        errors.append("Format tanggal tidak valid (gunakan YYYY-MM-DD)")
        return {'is_valid': False, 'errors': errors, 'jumlah_hari': 0}
    
    # Validasi logika tanggal
    if tanggal_mulai > tanggal_selesai:
        errors.append("Tanggal mulai tidak boleh lebih besar dari tanggal selesai")
        return {'is_valid': False, 'errors': errors, 'jumlah_hari': 0}
    
    # Hitung jumlah hari
    jumlah_hari = (tanggal_selesai - tanggal_mulai).days + 1
    
    # 3. Validasi duplikasi bulan
    existing_detail = DetailJatahCuti.objects.filter(
        jatah_cuti=jatah_cuti,
        tahun=tahun,
        bulan=bulan,
        dipakai=True
    ).first()
    
    if existing_detail:
        errors.append(f"Bulan {bulan} tahun {tahun} sudah digunakan untuk cuti sebelumnya")
    
    # 4. Validasi tanggal overlap dengan cuti lain yang disetujui (skip jika diminta)
    if not skip_overlap_check:
        overlapping_cuti = Cuti.objects.filter(
            id_karyawan=karyawan,
            status='disetujui'
        ).filter(
            # Cek overlap: (start1 <= end2) and (end1 >= start2)
            tanggal_mulai__lte=tanggal_selesai,
            tanggal_selesai__gte=tanggal_mulai
        )
        
        if overlapping_cuti.exists():
            overlap_dates = []
            for cuti in overlapping_cuti:
                overlap_dates.append(f"{cuti.tanggal_mulai.strftime('%d/%m/%Y')} - {cuti.tanggal_selesai.strftime('%d/%m/%Y')} ({cuti.get_jenis_cuti_display()})")
            
            errors.append(f"Tanggal cuti bertabrakan dengan cuti yang sudah disetujui: {', '.join(overlap_dates)}")
    
    # 5. Validasi sisa cuti mencukupi (khusus untuk cuti tahunan)
    if jenis_cuti == 'tahunan':
        if jatah_cuti.sisa_cuti < jumlah_hari:
            errors.append(f"Sisa cuti tidak mencukupi. Dibutuhkan: {jumlah_hari} hari, tersedia: {jatah_cuti.sisa_cuti} hari")
    
    # 6. Validasi tanggal tidak boleh di masa lalu (opsional)
    today = datetime.now().date()
    if tanggal_mulai < today:
        errors.append("Tidak dapat mengajukan cuti untuk tanggal yang sudah lewat")
    
    return {
        'is_valid': len(errors) == 0,
        'errors': errors,
        'jumlah_hari': jumlah_hari
    }


def distributeDaysByMonth(startMonth, startYear, days):
    """
    Helper function untuk mendistribusikan hari cuti secara berurutan per bulan.
    
    Args:
        startMonth (int): Bulan mulai (1-12)
        startYear (int): Tahun mulai
        days (int): Jumlah hari yang akan didistribusikan
    
    Returns:
        list: Daftar tuple (year, month, increment) sepanjang days
    """
    distribution = []
    current_month = startMonth
    current_year = startYear
    
    for _ in range(days):
        distribution.append((current_year, current_month, 1))
        
        # Pindah ke bulan berikutnya
        current_month += 1
        if current_month > 12:
            current_month = 1
            current_year += 1
    
    return distribution


def update_manual_jatah_cuti(karyawan_id, tahun, bulan, dipakai, keterangan='', tanggal=None, jenis_cuti=None, file_persetujuan=None, user=None):
    """Update manual jatah cuti sederhana: 1 sel bulan = 1 tanggal cuti bebas."""
    from django.contrib.auth.models import User
    from ..models import Cuti
    from datetime import datetime
    import logging
    
    logger = logging.getLogger(__name__)
    logger.info(f"UPDATE MANUAL JATAH CUTI BEBAS - Karyawan: {karyawan_id}, Tahun: {tahun}, Bulan: {bulan}, Dipakai: {dipakai}")
    
    try:
        karyawan = Karyawan.objects.get(id=karyawan_id)
        jatah_cuti = JatahCuti.objects.get(karyawan=karyawan, tahun=tahun)
        
        logger.info(f"Karyawan ditemukan: {karyawan.nama}, Jatah cuti: {jatah_cuti.sisa_cuti}/{jatah_cuti.total_cuti}")
        
        # Validasi tanggal jika dipakai
        if dipakai and not tanggal:
            return {
                'success': False, 
                'message': 'Tanggal cuti wajib diisi ketika status dipakai dipilih'
            }
        
        tanggal_obj = None
        if dipakai and tanggal:
            if isinstance(tanggal, str):
                tanggal_obj = datetime.strptime(tanggal, '%Y-%m-%d').date()
            else:
                tanggal_obj = tanggal
                
        # Buat atau update DetailJatahCuti untuk bulan ini
        detail, created = DetailJatahCuti.objects.get_or_create(
            jatah_cuti=jatah_cuti,
            tahun=tahun,
            bulan=bulan,
            defaults={
                'dipakai': dipakai,
                'jumlah_hari': 1 if dipakai else 0,
                'keterangan': keterangan,
                'tanggal_terpakai': tanggal_obj if dipakai and tanggal else None
            }
        )
        
        if not created:
            # Update existing record
            old_dipakai = detail.dipakai
            old_jumlah_hari = detail.jumlah_hari
            
            # Hapus entri Cuti terkait jika berubah dari dipakai ke tidak dipakai
            if old_dipakai and not dipakai:
                if detail.tanggal_terpakai:
                    related_cuti = Cuti.objects.filter(
                        id_karyawan=karyawan,
                        tanggal_mulai=detail.tanggal_terpakai,
                        tanggal_selesai=detail.tanggal_terpakai,
                        status='disetujui'
                    ).first()
                    
                    if related_cuti:
                        related_cuti.delete()
                        logger.info(f"Deleted related Cuti: {related_cuti.id}")
            
            # Update detail
            detail.dipakai = dipakai
            detail.jumlah_hari = 1 if dipakai else 0
            detail.keterangan = keterangan if dipakai else ''
            detail.tanggal_terpakai = tanggal_obj if dipakai and tanggal else None
            detail.save()
            
            # Update sisa cuti berdasarkan perubahan
            if old_dipakai != dipakai:
                if dipakai and not old_dipakai:
                    # Dari kosong ke terpakai: kurangi 1 hari
                    jatah_cuti.sisa_cuti = max(0, jatah_cuti.sisa_cuti - 1)
                elif not dipakai and old_dipakai:
                    # Dari terpakai ke kosong: tambah 1 hari
                    jatah_cuti.sisa_cuti += 1
            
            jatah_cuti.save()
        else:
            # New record: kurangi sisa cuti jika dipakai
            if dipakai:
                jatah_cuti.sisa_cuti = max(0, jatah_cuti.sisa_cuti - 1)
                jatah_cuti.save()
        
        # Buat entri Cuti jika diperlukan
        if dipakai and tanggal and jenis_cuti and user:
            existing_cuti = Cuti.objects.filter(
                id_karyawan=karyawan,
                tanggal_mulai=tanggal_obj,
                tanggal_selesai=tanggal_obj,
                jenis_cuti=jenis_cuti
            ).first()
            
            if not existing_cuti:
                cuti_data = {
                    'id_karyawan': karyawan,
                    'tanggal_mulai': tanggal_obj,
                    'tanggal_selesai': tanggal_obj,
                    'jenis_cuti': jenis_cuti,
                    'status': 'disetujui',
                    'approval': user
                }
                
                if file_persetujuan:
                    cuti_data['file_persetujuan'] = file_persetujuan
                
                cuti_baru = Cuti.objects.create(**cuti_data)
                message = f'Berhasil menandai 1 hari cuti pada {tanggal_obj.strftime("%d %B %Y")} dan membuat entri cuti baru'
            else:
                if file_persetujuan:
                    existing_cuti.file_persetujuan = file_persetujuan
                    existing_cuti.save()
                message = f'Berhasil menandai 1 hari cuti pada {tanggal_obj.strftime("%d %B %Y")} (entri cuti sudah ada)'
        else:
            if dipakai:
                message = f'Berhasil menandai 1 hari cuti pada {tanggal_obj.strftime("%d %B %Y")}'
            else:
                message = 'Berhasil menghapus penandaan cuti'
        
        # Cek expired
        current_date = datetime.now().date()
        expired = False
        if tahun < current_date.year - 1:
            expired = True
        elif tahun == current_date.year - 1 and bulan < current_date.month:
            expired = True
        
        result = {
            'success': True, 
            'message': message,
            'sisa_cuti': jatah_cuti.sisa_cuti,
            'data': {
                'dipakai': dipakai,
                'keterangan': keterangan,
                'tanggal': tanggal,
                'sisa_cuti': jatah_cuti.sisa_cuti,
                'expired': expired,
                'jumlah_hari': 1 if dipakai else 0
            }
        }
        
        logger.info(f"SUCCESS: {result}")
        return result
        
    except Exception as e:
        logger.error(f"ERROR in update_manual_jatah_cuti: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return {'success': False, 'message': f'Error: {str(e)}'}

def get_expired_cuti_notifications(tahun=None):
    """Mendapatkan notifikasi cuti yang sudah expired untuk ditampilkan di frontend."""
    if not tahun:
        tahun = datetime.now().year
    
    current_date = datetime.now().date()
    expired_notifications = []
    
    # Juga cari yang tahun lalu tapi bulan sudah lewat 1 tahun
    detail_expired_bulan = DetailJatahCuti.objects.filter(
        tahun=current_date.year - 1,
        bulan__lt=current_date.month,
        dipakai=False
    ).select_related('jatah_cuti__karyawan')
    
    import calendar
    
    for detail in detail_expired_bulan:
        expired_notifications.append({
            'karyawan': detail.jatah_cuti.karyawan.nama,
            'bulan': calendar.month_name[detail.bulan],
            'tahun': detail.tahun,
            'message': f'Cuti bulan {calendar.month_name[detail.bulan]} {detail.tahun} telah hangus karena telah melewati 1 tahun.'
        })
    
    return expired_notifications


def validasi_cuti_dua_tahun(karyawan, jumlah_hari, tahun_referensi):
    """Validasi apakah total sisa cuti dari tahun sekarang dan tahun sebelumnya mencukupi.
    
    Args:
        karyawan: Objek Karyawan
        jumlah_hari: Jumlah hari cuti yang diajukan
        tahun_referensi: Tahun referensi (biasanya tahun sekarang)
        
    Returns:
        tuple: (is_valid, error_message, detail_sisa_cuti)
    """
    
    # Dapatkan tanggal saat ini untuk pengecekan cuti hangus
    current_date = datetime.now().date()
    tahun_batas = current_date.year - 1
    bulan_batas = current_date.month
    
    # Ambil jatah cuti dari tahun sekarang dan tahun sebelumnya saja
    tahun_sebelumnya = tahun_referensi - 1
    
    jatah_cuti_list = JatahCuti.objects.filter(
        karyawan=karyawan, 
        tahun__in=[tahun_sebelumnya, tahun_referensi]
    ).order_by('tahun')
    
    # Hitung total sisa cuti yang valid (tidak hangus)
    total_sisa_cuti = 0
    detail_sisa = []
    
    for jc in jatah_cuti_list:
        # Jika tahun jatah cuti lebih kecil dari tahun batas, semua cuti sudah hangus
        if jc.tahun < tahun_batas:
            continue
        # Jika tahun jatah cuti sama dengan tahun batas, hitung hanya bulan yang belum hangus
        elif jc.tahun == tahun_batas:
            # Hitung jumlah slot kosong yang belum hangus
            detail_aktif_count = DetailJatahCuti.objects.filter(
                jatah_cuti=jc,
                dipakai=False,
                bulan__gte=bulan_batas
            ).count()
            
            if detail_aktif_count > 0:
                detail_sisa.append(f"{jc.tahun} tersisa {detail_aktif_count} hari")
                total_sisa_cuti += detail_aktif_count
        # Jika tahun jatah cuti lebih besar dari tahun batas, semua cuti masih valid
        else:
            if jc.sisa_cuti > 0:
                detail_sisa.append(f"{jc.tahun} tersisa {jc.sisa_cuti} hari")
                total_sisa_cuti += jc.sisa_cuti
    
    if total_sisa_cuti >= jumlah_hari:
        return True, None, detail_sisa
    else:
        detail_text = ", ".join(detail_sisa) if detail_sisa else "tidak ada sisa cuti"
        error_message = f"Pengajuan melebihi jatah cuti: {detail_text}. Total dibutuhkan: {jumlah_hari} hari."
        return False, error_message, detail_sisa


def get_kosong_slot_dua_tahun(karyawan, jumlah_hari, tahun_referensi):
    """Mencari slot kosong dari tahun sebelumnya dan tahun sekarang saja.
    
    Args:
        karyawan: Objek Karyawan
        jumlah_hari: Jumlah hari yang dibutuhkan
        tahun_referensi: Tahun referensi
        
    Returns:
        list: List DetailJatahCuti yang kosong, diurutkan dari tahun sebelumnya dulu
    """
    
    # Dapatkan tanggal saat ini untuk pengecekan cuti hangus
    current_date = datetime.now().date()
    tahun_batas = current_date.year - 1
    bulan_batas = current_date.month
    
    tahun_sebelumnya = tahun_referensi - 1
    bulan_kosong = []
    
    # Cari slot kosong dari tahun sebelumnya terlebih dahulu
    for tahun in [tahun_sebelumnya, tahun_referensi]:
        try:
            jatah_cuti = JatahCuti.objects.get(karyawan=karyawan, tahun=tahun)
            
            # Filter untuk memastikan tidak mengambil slot yang seharusnya hangus
            if tahun < tahun_batas:
                # Jika tahun lebih kecil dari tahun batas, semua slot sudah hangus
                continue
            elif tahun == tahun_batas:
                # Jika tahun sama dengan tahun batas, hanya ambil bulan yang belum hangus
                detail_kosong = DetailJatahCuti.objects.filter(
                    jatah_cuti=jatah_cuti,
                    dipakai=False,
                    bulan__gte=bulan_batas
                ).order_by('bulan')
            else:
                # Jika tahun lebih besar dari tahun batas, ambil semua slot kosong
                detail_kosong = DetailJatahCuti.objects.filter(
                    jatah_cuti=jatah_cuti,
                    dipakai=False
                ).order_by('bulan')
            
            bulan_kosong.extend(detail_kosong)
            
            # Jika sudah cukup, hentikan pencarian
            if len(bulan_kosong) >= jumlah_hari:
                break
                
        except JatahCuti.DoesNotExist:
            # Jika belum ada jatah cuti untuk tahun ini, buat dulu
            jatah_cuti = hitung_jatah_cuti(karyawan, tahun, isi_detail_cuti_bersama=False)
            if jatah_cuti:
                # Lakukan pengecekan yang sama seperti di atas
                if tahun < tahun_batas:
                    continue
                elif tahun == tahun_batas:
                    detail_kosong = DetailJatahCuti.objects.filter(
                        jatah_cuti=jatah_cuti,
                        dipakai=False,
                        bulan__gte=bulan_batas
                    ).order_by('bulan')
                else:
                    detail_kosong = DetailJatahCuti.objects.filter(
                        jatah_cuti=jatah_cuti,
                        dipakai=False
                    ).order_by('bulan')
                    
                bulan_kosong.extend(detail_kosong)
    
    return bulan_kosong[:jumlah_hari]


def isi_dari_bulan_kiri_cuti_bersama_h_minus_1(jatah_cuti, cuti_bersama, tahun, tanggal_besok):
    """Mengisi cuti bersama H-1 dengan validasi ketat tanggal.
    
    Fungsi ini khusus untuk memproses cuti bersama H-1 dengan validasi
    bahwa tanggal cuti bersama benar-benar adalah tanggal besok.
    
    Args:
        jatah_cuti: Objek JatahCuti karyawan
        cuti_bersama: Objek CutiBersama tunggal (bukan list)
        tahun: Tahun referensi
        tanggal_besok: Tanggal besok untuk validasi
        
    Returns:
        Boolean: True jika berhasil, False jika gagal validasi
    """
    logger = logging.getLogger(__name__)
    
    # VALIDASI KETAT: Pastikan tanggal cuti bersama adalah tanggal besok
    if cuti_bersama.tanggal != tanggal_besok:
        print(f"VALIDASI GAGAL: Tanggal cuti bersama {cuti_bersama.tanggal} bukan tanggal besok {tanggal_besok}")
        logger.error(f"VALIDASI GAGAL: Tanggal cuti bersama {cuti_bersama.tanggal} bukan tanggal besok {tanggal_besok}")
        return False
    
    # VALIDASI TAMBAHAN: Pastikan tahun cuti bersama sesuai
    if cuti_bersama.tanggal.year != tahun:
        print(f"VALIDASI GAGAL: Tahun cuti bersama {cuti_bersama.tanggal.year} tidak sesuai dengan tahun referensi {tahun}")
        logger.error(f"VALIDASI GAGAL: Tahun cuti bersama {cuti_bersama.tanggal.year} tidak sesuai dengan tahun referensi {tahun}")
        return False
    
    print(f"VALIDASI BERHASIL: Memproses cuti bersama {cuti_bersama.tanggal} untuk karyawan {jatah_cuti.karyawan.nama}")
    logger.info(f"VALIDASI BERHASIL: Memproses cuti bersama {cuti_bersama.tanggal} untuk karyawan {jatah_cuti.karyawan.nama}")
    
    # Gunakan fungsi baru yang hanya mencari slot di tahun yang sama
    bulan_kosong = get_kosong_slot_tahun_sama(jatah_cuti.karyawan, 1, tahun)
    
    # Jika slot kosong tidak mencukupi di tahun yang sama, berikan peringatan
    if len(bulan_kosong) < 1:
        print(f"PERINGATAN: Karyawan {jatah_cuti.karyawan.nama} tidak memiliki slot kosong di tahun {tahun} untuk cuti bersama {cuti_bersama.tanggal}")
        logger.warning(f"Karyawan {jatah_cuti.karyawan.nama} tidak memiliki slot kosong di tahun {tahun} untuk cuti bersama {cuti_bersama.tanggal}")
        return False
    
    # Gunakan fungsi umum untuk mengisi slot dan memperbarui sisa cuti
    # Hanya proses satu cuti bersama
    result = isi_slot_dan_update_sisa_cuti(jatah_cuti.karyawan, bulan_kosong[:1], [cuti_bersama], tahun, is_cuti_bersama=True)
    
    if result:
        print(f"BERHASIL: Cuti bersama {cuti_bersama.tanggal} berhasil diproses untuk {jatah_cuti.karyawan.nama}")
        logger.info(f"BERHASIL: Cuti bersama {cuti_bersama.tanggal} berhasil diproses untuk {jatah_cuti.karyawan.nama}")
    else:
        print(f"GAGAL: Cuti bersama {cuti_bersama.tanggal} gagal diproses untuk {jatah_cuti.karyawan.nama}")
        logger.error(f"GAGAL: Cuti bersama {cuti_bersama.tanggal} gagal diproses untuk {jatah_cuti.karyawan.nama}")
    
    return result

def potong_jatah_cuti_h_minus_1():
    """Memotong jatah cuti H-1 (sehari sebelum) tanggal cuti bersama.
    
    Fungsi ini akan dijalankan setiap hari melalui cron job untuk mengecek
    apakah ada cuti bersama yang akan terjadi besok, dan jika ada,
    memotong jatah cuti karyawan yang belum mengajukan TidakAmbilCuti.
    """
    logger = logging.getLogger(__name__)
    besok = datetime.now().date() + timedelta(days=1)
    
    # Cari cuti bersama yang akan terjadi besok (hanya jenis 'Cuti Bersama')
    cuti_bersama_besok = CutiBersama.objects.filter(tanggal=besok, jenis='Cuti Bersama')
    
    if not cuti_bersama_besok.exists():
        print(f"Tidak ada cuti bersama untuk tanggal {besok}")
        logger.info(f"Tidak ada cuti bersama untuk tanggal {besok}")
        return
    
    print(f"===== MEMOTONG JATAH CUTI H-1 UNTUK TANGGAL {besok} =====")
    logger.info(f"===== MEMOTONG JATAH CUTI H-1 UNTUK TANGGAL {besok} =====")
    
    # Ambil semua karyawan tetap dan HRD yang aktif
    karyawan_list = Karyawan.objects.filter(
        Q(user__role='HRD') | Q(user__role='Karyawan Tetap'),
        status_keaktifan='Aktif'
    )
    
    tahun = besok.year
    
    for karyawan in karyawan_list:
        # PERBAIKAN: Pastikan parameter isi_detail_cuti_bersama=False
        jatah_cuti = hitung_jatah_cuti(karyawan, tahun, isi_detail_cuti_bersama=False)
        if not jatah_cuti:
            continue
        
        # Proses setiap cuti bersama secara individual dengan validasi ketat
        cuti_bersama_yang_perlu_dipotong = []
        for cb in cuti_bersama_besok:
            # VALIDASI TAMBAHAN: Pastikan tanggal cuti bersama benar-benar besok
            if cb.tanggal != besok:
                print(f"PERINGATAN: Cuti bersama {cb.tanggal} bukan tanggal besok ({besok}), dilewati")
                logger.warning(f"Cuti bersama {cb.tanggal} bukan tanggal besok ({besok}), dilewati")
                continue
            
            # Cek apakah karyawan sudah mengajukan untuk tidak ambil cuti bersama ini
            sudah_ajukan = karyawan.tidakambilcuti_set.filter(
                status='disetujui',
                tanggal=cb
            ).exists()
            
            # Cek apakah jatah cuti untuk tanggal ini sudah dipotong sebelumnya
            sudah_dipotong = DetailJatahCuti.objects.filter(
                jatah_cuti__karyawan=karyawan,
                dipakai=True,
                keterangan__icontains=f'Cuti Bersama: {cb.keterangan or cb.tanggal}'
            ).exists()
            
            if not sudah_ajukan and not sudah_dipotong:
                # PERBAIKAN: Proses satu per satu dengan validasi tanggal
                success = isi_dari_bulan_kiri_cuti_bersama_h_minus_1(jatah_cuti, cb, tahun, besok)
                if success:
                    cuti_bersama_yang_perlu_dipotong.append(cb)
                    print(f"Jatah cuti dipotong untuk {karyawan.nama}: {cb.keterangan or cb.tanggal}")
                    logger.info(f"Jatah cuti dipotong untuk {karyawan.nama}: {cb.keterangan or cb.tanggal}")
        
        # Hitung ulang sisa cuti untuk memastikan saldo cuti diperbarui dengan benar
        if cuti_bersama_yang_perlu_dipotong:
            rapikan_cuti_tahunan(karyawan, tahun)
            print(f"Total jatah cuti dipotong untuk {karyawan.nama}: {len(cuti_bersama_yang_perlu_dipotong)} hari")
            logger.info(f"Total jatah cuti dipotong untuk {karyawan.nama}: {len(cuti_bersama_yang_perlu_dipotong)} hari")
    
    print(f"===== SELESAI MEMOTONG JATAH CUTI H-1 =====")
    logger.info(f"===== SELESAI MEMOTONG JATAH CUTI H-1 =====")


def isi_cuti_tahunan_dua_tahun(karyawan, tanggal_mulai, tanggal_selesai, allow_minus=False):
    """Mengisi detail jatah cuti untuk cuti tahunan dengan prioritas tahun sebelumnya dulu.
    
    Fungsi ini akan memotong jatah cuti mulai dari tahun sebelumnya terlebih dahulu,
    kemudian tahun sekarang jika masih diperlukan.
    
    Args:
        karyawan: Objek Karyawan yang mengajukan cuti
        tanggal_mulai: Tanggal mulai cuti
        tanggal_selesai: Tanggal selesai cuti
        allow_minus: Boolean, jika True maka saldo cuti boleh minus
        
    Returns:
        Boolean: True jika berhasil, False jika gagal (saldo tidak cukup)
    """
    logger = logging.getLogger(__name__)
    
    tahun = tanggal_mulai.year
    
    print(f"\n===== MULAI PENGAJUAN CUTI TAHUNAN =====")
    print(f"Karyawan: {karyawan.nama}, Tanggal: {tanggal_mulai} - {tanggal_selesai}, Tahun referensi: {tahun}")
    logger.info(f"===== MULAI PENGAJUAN CUTI TAHUNAN =====")
    logger.info(f"Karyawan: {karyawan.nama}, Tanggal: {tanggal_mulai} - {tanggal_selesai}, Tahun referensi: {tahun}")
    
    # Hitung jumlah hari kerja cuti
    jumlah_hari = hitung_hari_kerja(tanggal_mulai, tanggal_selesai)
    print(f"Jumlah hari cuti: {jumlah_hari}")
    logger.info(f"Jumlah hari cuti: {jumlah_hari}")
    
    # Proses cuti hangus terlebih dahulu untuk memastikan status cuti terkini
    # Proses untuk tahun sekarang dan tahun sebelumnya
    print(f"Memproses cuti hangus sebelum pengajuan...")
    logger.info(f"Memproses cuti hangus sebelum pengajuan...")
    proses_cuti_hangus(karyawan, tahun)
    proses_cuti_hangus(karyawan, tahun - 1)
    
    # Validasi terlebih dahulu
    print(f"Validasi cuti dua tahun...")
    logger.info(f"Validasi cuti dua tahun...")
    is_valid, error_message, _ = validasi_cuti_dua_tahun(karyawan, jumlah_hari, tahun)
    if not allow_minus and not is_valid:
        print(f"Validasi gagal: {error_message}")
        logger.info(f"Validasi gagal: {error_message}")
        return False
    
    # Pastikan ada jatah cuti untuk tahun ini
    jatah_cuti = hitung_jatah_cuti(karyawan, tahun, isi_detail_cuti_bersama=False)
    if not jatah_cuti:
        print(f"Tidak ada jatah cuti untuk tahun {tahun}")
        logger.info(f"Tidak ada jatah cuti untuk tahun {tahun}")
        return False
    
    # Isi dari slot kosong dengan prioritas tahun sebelumnya dulu
    keterangan_cuti = f'Cuti Tahunan: {tanggal_mulai} - {tanggal_selesai}'
    
    # Gunakan fungsi khusus untuk mencari slot kosong dari 2 tahun saja
    # Fungsi ini sudah dimodifikasi untuk tidak mengambil slot yang seharusnya hangus
    print(f"Mencari slot kosong dari dua tahun...")
    logger.info(f"Mencari slot kosong dari dua tahun...")
    bulan_kosong = get_kosong_slot_dua_tahun(karyawan, jumlah_hari, tahun)
    
    # Buat list keterangan dengan panjang jumlah_hari
    keterangan_list = [keterangan_cuti] * jumlah_hari
    
    # Gunakan fungsi umum untuk mengisi slot dan memperbarui sisa cuti
    print(f"Mengisi slot dan memperbarui sisa cuti...")
    logger.info(f"Mengisi slot dan memperbarui sisa cuti...")
    result = isi_slot_dan_update_sisa_cuti(karyawan, bulan_kosong, keterangan_list, tahun, 
                                         is_cuti_bersama=False, allow_minus=allow_minus,
                                         tanggal_mulai=tanggal_mulai, tanggal_selesai=tanggal_selesai)
    
    # PENTING: Fungsi isi_slot_dan_update_sisa_cuti sudah menghitung ulang sisa cuti dengan benar
    # Tidak perlu memanggil rapikan_cuti_tahunan lagi karena akan menyebabkan pengurangan dobel
    # Jika rapikan_cuti_tahunan dipanggil di sini, akan terjadi pengurangan dobel pada sisa cuti
    
    print(f"===== SELESAI PENGAJUAN CUTI TAHUNAN =====\n")
    logger.info(f"===== SELESAI PENGAJUAN CUTI TAHUNAN =====\n")
    
    return result

def isi_cuti_bersama_h_minus_1(tahun):
    """
    Mengisi detail jatah cuti untuk cuti bersama sesuai aturan H-1.
    
    Aturan sesuai AGENTS.md:
    - Cuti bersama hanya memotong jatah cuti di tahun yang sama
    - Potongan dilakukan H-1 (sehari sebelum tanggal cuti bersama)  
    - Alokasi mengisi dari bulan terakhir yang kosong (Desember -> Januari)
    """
    from datetime import timedelta
    import logging
    
    logger = logging.getLogger(__name__)
    logger.info(f"===== MULAI PROSES CUTI BERSAMA H-1 UNTUK TAHUN {tahun} =====")
    
    # Ambil semua cuti bersama untuk tahun ini (hanya jenis 'Cuti Bersama')
    cuti_bersama = CutiBersama.objects.filter(tanggal__year=tahun, jenis='Cuti Bersama').order_by('tanggal')
    
    if not cuti_bersama.exists():
        logger.info(f"Tidak ada cuti bersama untuk tahun {tahun}")
        return
    
    # Ambil semua karyawan tetap dan HRD yang aktif
    karyawan_list = Karyawan.objects.filter(
        Q(user__role='HRD') | Q(user__role='Karyawan Tetap'),
        status_keaktifan='Aktif'
    )
    
    current_date = datetime.now().date()
    
    for karyawan in karyawan_list:
        logger.info(f"Memproses karyawan: {karyawan.nama}")
        

        
        # Pastikan ada jatah cuti untuk tahun ini
        jatah_cuti = hitung_jatah_cuti(karyawan, tahun, isi_detail_cuti_bersama=False)
        if not jatah_cuti:
            logger.warning(f"Gagal membuat jatah cuti untuk {karyawan.nama}")
            continue
        
        # Kumpulkan cuti bersama yang perlu diproses untuk karyawan ini
        cuti_bersama_yang_perlu_diisi = []
        
        for cb in cuti_bersama:
            # Cek tanggal H-1 
            tanggal_h_minus_1 = cb.tanggal - timedelta(days=1)
            
            # Hanya proses jika hari ini adalah H-1 atau sudah lewat tanggal cuti bersama
            if current_date >= tanggal_h_minus_1:
                # Cek apakah karyawan sudah mengajukan untuk tidak ambil cuti bersama ini
                try:
                    sudah_ajukan = karyawan.tidakambilcuti_set.filter(
                        status='disetujui',
                        tanggal=cb
                    ).exists()
                except:
                    # Jika model TidakAmbilCuti belum ada, anggap tidak ada yang mengajukan
                    sudah_ajukan = False
                
                if not sudah_ajukan:
                    cuti_bersama_yang_perlu_diisi.append(cb)
                    logger.info(f"Cuti bersama {cb.tanggal} akan diisi untuk {karyawan.nama}")
        
        if not cuti_bersama_yang_perlu_diisi:
            logger.info(f"Tidak ada cuti bersama yang perlu diisi untuk {karyawan.nama}")
            continue
        
        # Isi cuti bersama menggunakan fungsi khusus dengan aturan tahun yang sama
        isi_dari_bulan_kanan_cuti_bersama(jatah_cuti, cuti_bersama_yang_perlu_diisi, tahun)
        
        logger.info(f"Selesai memproses cuti bersama untuk {karyawan.nama}")
    
    logger.info(f"===== SELESAI PROSES CUTI BERSAMA H-1 UNTUK TAHUN {tahun} =====")

def isi_dari_bulan_kanan_cuti_bersama(jatah_cuti, cuti_bersama_list, tahun):
    """
    Mengisi cuti bersama dari slot kosong di tahun yang sama, dimulai dari bulan terakhir (Desember -> Januari).
    
    Sesuai AGENTS.md:
    - Cuti bersama hanya boleh memotong jatah cuti di tahun yang sama
    - Alokasi mengisi dari bulan terakhir yang kosong (Desember, November, Oktober, dst)
    """
    import logging
    
    logger = logging.getLogger(__name__)
    logger.info(f"Mengisi cuti bersama untuk {jatah_cuti.karyawan.nama}, jumlah: {len(cuti_bersama_list)} hari")
    
    # Cari slot kosong di tahun yang sama, urutkan dari bulan terbesar (Desember ke Januari)
    detail_kosong = DetailJatahCuti.objects.filter(
        jatah_cuti=jatah_cuti,
        tahun=tahun,
        dipakai=False
    ).order_by('-bulan')  # Urutkan dari bulan terbesar (Desember -> Januari)
    
    if detail_kosong.count() < len(cuti_bersama_list):
        logger.warning(f"Slot kosong tidak mencukupi untuk {jatah_cuti.karyawan.nama}. "
                      f"Dibutuhkan: {len(cuti_bersama_list)}, Tersedia: {detail_kosong.count()}")
        return False
    
    # Isi slot kosong dengan cuti bersama
    for i, cb in enumerate(cuti_bersama_list):
        if i < detail_kosong.count():
            detail = detail_kosong[i]
            detail.dipakai = True
            detail.jumlah_hari = 1
            detail.keterangan = f"Cuti Bersama: {cb.keterangan or cb.tanggal.strftime('%d %B %Y')}"
            detail.tanggal_terpakai = cb.tanggal
            detail.save()
            
            logger.info(f"Mengisi slot {detail.tahun}-{detail.bulan:02d} dengan cuti bersama {cb.tanggal}")
    
    # Update sisa cuti
    sisa_cuti_baru = max(0, jatah_cuti.sisa_cuti - len(cuti_bersama_list))
    jatah_cuti.sisa_cuti = sisa_cuti_baru
    jatah_cuti.save()
    
    logger.info(f"Sisa cuti {jatah_cuti.karyawan.nama} diupdate menjadi {sisa_cuti_baru}")
    return True

def isi_cuti_tahunan_dari_kiri(karyawan, jumlah_hari, keterangan, tahun, tanggal_mulai=None, tanggal_selesai=None):
    """
    Mengisi cuti tahunan dari slot kosong paling kiri (Januari -> Desember).
    
    Sesuai AGENTS.md:
    - Cuti tahunan dialokasikan dari bulan paling kiri kosong (Januari → Desember)
    """
    import logging
    
    logger = logging.getLogger(__name__)
    logger.info(f"Mengisi cuti tahunan untuk {karyawan.nama}, jumlah: {jumlah_hari} hari")
    
    # Cari slot kosong dari bulan terkecil (Januari ke Desember)
    bulan_kosong = get_kosong_slot_tahun_sama(karyawan, jumlah_hari, tahun)
    
    if len(bulan_kosong) < jumlah_hari:
        logger.warning(f"Slot kosong tidak mencukupi untuk {karyawan.nama}. "
                      f"Dibutuhkan: {jumlah_hari}, Tersedia: {len(bulan_kosong)}")
        return False
    
    # Buat daftar tanggal cuti jika ada tanggal mulai dan selesai
    tanggal_cuti = []
    if tanggal_mulai and tanggal_selesai:
        current_date = tanggal_mulai
        while current_date <= tanggal_selesai and len(tanggal_cuti) < jumlah_hari:
            tanggal_cuti.append(current_date)
            current_date += timedelta(days=1)
    
    # Isi slot kosong dengan cuti tahunan
    for i in range(jumlah_hari):
        if i < len(bulan_kosong):
            detail = bulan_kosong[i]
            detail.dipakai = True
            detail.jumlah_hari = 1
            detail.keterangan = keterangan
            
            # Set tanggal terpakai jika ada
            if i < len(tanggal_cuti):
                detail.tanggal_terpakai = tanggal_cuti[i]
            
            detail.save()
            logger.info(f"Mengisi slot {detail.tahun}-{detail.bulan:02d} dengan cuti tahunan")
    
    # Update sisa cuti
    jatah_cuti = JatahCuti.objects.filter(karyawan=karyawan, tahun=tahun).first()
    if jatah_cuti:
        sisa_cuti_baru = max(0, jatah_cuti.sisa_cuti - jumlah_hari)
        jatah_cuti.sisa_cuti = sisa_cuti_baru
        jatah_cuti.save()
        
        logger.info(f"Sisa cuti {karyawan.nama} diupdate menjadi {sisa_cuti_baru}")
    
    return True