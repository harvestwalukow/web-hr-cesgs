from datetime import date
from apps.hrd.utils.jatah_cuti import potong_jatah_cuti_h_minus_1_test

# Override tanggal agar "besok" = 24 Juli 2025
def tes_cron_simulasi():
    from datetime import timedelta

    # Sementara override tanggal agar dianggap hari ini adalah 23 Juli 2025
    target_besok = date(2025, 7, 24)
    potong_jatah_cuti_h_minus_1_test(target_besok)


# PINDAHIN KODE DIBAWAH INI KE JATAH_CUTI

# def potong_jatah_cuti_h_minus_1_test(target_besok):
#     """Memotong jatah cuti H-1 (sehari sebelum) tanggal cuti bersama.
    
#     Fungsi ini akan dijalankan setiap hari melalui cron job untuk mengecek
#     apakah ada cuti bersama yang akan terjadi besok, dan jika ada,
#     memotong jatah cuti karyawan yang belum mengajukan TidakAmbilCuti.
#     """
#     logger = logging.getLogger(__name__)
#     besok = target_besok
    
#     # Cari cuti bersama yang akan terjadi besok
#     cuti_bersama_besok = CutiBersama.objects.filter(tanggal=besok)
    
#     if not cuti_bersama_besok.exists():
#         print(f"Tidak ada cuti bersama untuk tanggal {besok}")
#         logger.info(f"Tidak ada cuti bersama untuk tanggal {besok}")
#         return
    
#     print(f"===== MEMOTONG JATAH CUTI H-1 UNTUK TANGGAL {besok} =====")
#     logger.info(f"===== MEMOTONG JATAH CUTI H-1 UNTUK TANGGAL {besok} =====")
    
#     # Ambil semua karyawan tetap dan HRD yang aktif
#     karyawan_list = Karyawan.objects.filter(
#         Q(user__role='HRD') | Q(user__role='Karyawan Tetap'),
#         status_keaktifan='Aktif'
#     )
    
#     tahun = besok.year
    
#     for karyawan in karyawan_list:
#         # Pastikan ada jatah cuti untuk tahun ini
#         jatah_cuti = hitung_jatah_cuti(karyawan, tahun, isi_detail_cuti_bersama=False)
#         if not jatah_cuti:
#             continue
        
#         # Proses setiap cuti bersama secara individual
#         cuti_bersama_yang_perlu_dipotong = []
#         for cb in cuti_bersama_besok:
#             # Cek apakah karyawan sudah mengajukan untuk tidak ambil cuti bersama ini
#             sudah_ajukan = karyawan.tidakambilcuti_set.filter(
#                 status='disetujui',
#                 tanggal=cb
#             ).exists()
            
#             # Cek apakah jatah cuti untuk tanggal ini sudah dipotong sebelumnya
#             sudah_dipotong = DetailJatahCuti.objects.filter(
#                 jatah_cuti__karyawan=karyawan,
#                 dipakai=True,
#                 keterangan__icontains=f'Cuti Bersama: {cb.keterangan or cb.tanggal}'
#             ).exists()
            
#             if not sudah_ajukan and not sudah_dipotong:
#                 # Proses satu per satu, bukan dalam list
#                 isi_dari_bulan_kiri_cuti_bersama(jatah_cuti, [cb], tahun)
#                 cuti_bersama_yang_perlu_dipotong.append(cb)
                
#                 print(f"Jatah cuti dipotong untuk {karyawan.nama}: {cb.keterangan or cb.tanggal}")
#                 logger.info(f"Jatah cuti dipotong untuk {karyawan.nama}: {cb.keterangan or cb.tanggal}")
        
#         # Hitung ulang sisa cuti untuk memastikan saldo cuti diperbarui dengan benar
#         if cuti_bersama_yang_perlu_dipotong:
#             rapikan_cuti_tahunan(karyawan, tahun)
#             print(f"Total jatah cuti dipotong untuk {karyawan.nama}: {len(cuti_bersama_yang_perlu_dipotong)} hari")
#             logger.info(f"Total jatah cuti dipotong untuk {karyawan.nama}: {len(cuti_bersama_yang_perlu_dipotong)} hari")
    
#     print(f"===== SELESAI MEMOTONG JATAH CUTI H-1 =====")
#     logger.info(f"===== SELESAI MEMOTONG JATAH CUTI H-1 =====")