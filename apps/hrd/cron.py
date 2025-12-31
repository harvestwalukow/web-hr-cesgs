from django_cron import CronJobBase, Schedule
from apps.hrd.models import Karyawan
from django.utils.timezone import now
from apps.hrd.utils.jatah_cuti import potong_jatah_cuti_h_minus_1
from django.contrib.auth.models import User
from notifications.signals import notify
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class CekKontrakKaryawan(CronJobBase):
    RUN_EVERY_MINS = 1440  # Jalankan setiap 24 jam (1440 menit)

    schedule = Schedule(run_every_mins=RUN_EVERY_MINS)
    code = 'hrd.cek_kontrak_karyawan'  # Kode unik untuk cron job ini

    def do(self):
        karyawan_berakhir = Karyawan.objects.filter(
            batas_kontrak__lt=now().date(),
            status_keaktifan='Aktif'
        )
        count = karyawan_berakhir.update(status_keaktifan='Tidak Aktif')
        print(f"{count} karyawan dinonaktifkan.")  # Debugging

class PotongJatahCutiHMinus1(CronJobBase):
    """Cron job untuk memotong jatah cuti H-1 dari tanggal cuti bersama."""
    RUN_EVERY_MINS = 1440  # Jalankan setiap 24 jam (1440 menit)
    
    schedule = Schedule(run_every_mins=RUN_EVERY_MINS)
    code = 'hrd.potong_jatah_cuti_h_minus_1'  # Kode unik untuk cron job ini
    
    def do(self):
        """Jalankan pemotongan jatah cuti H-1."""
        try:
            potong_jatah_cuti_h_minus_1()
            print("Cron job pemotongan jatah cuti H-1 berhasil dijalankan.")
        except Exception as e:
            print(f"Error dalam cron job pemotongan jatah cuti H-1: {str(e)}")
            # Kirim notifikasi error ke HRD
            for user in User.objects.filter(role='HRD'):
                notify.send(
                    sender=user,
                    recipient=user,
                    verb="cron_error",
                    description=f"Error dalam pemotongan jatah cuti H-1: {str(e)}"
                )


class CekLemburKaryawan(CronJobBase):
    """
    Cron job untuk cek karyawan yang sudah kerja 10+ jam.
    Kirim notifikasi WhatsApp sebagai reminder untuk mengajukan lembur.
    """
    RUN_EVERY_MINS = 15  # Jalankan setiap 15 menit
    
    schedule = Schedule(run_every_mins=RUN_EVERY_MINS)
    code = 'hrd.cek_lembur_karyawan'
    
    def do(self):
        """Cek semua absensi aktif dan kirim notif jika sudah 10+ jam."""
        from apps.absensi.models import AbsensiMagang
        from apps.notifikasi.fonnte import send_whatsapp
        from apps.notifikasi.models import WhatsAppLog
        
        today = datetime.now().date()
        count_sent = 0
        
        # Ambil semua absensi hari ini yang sudah check-in tapi belum check-out
        absensi_aktif = AbsensiMagang.objects.filter(
            tanggal=today,
            jam_masuk__isnull=False,
            jam_pulang__isnull=True
        )
        
        for absensi in absensi_aktif:
            try:
                # Hitung durasi kerja
                jam_masuk = datetime.combine(today, absensi.jam_masuk)
                sekarang = datetime.now()
                durasi = sekarang - jam_masuk
                jam_kerja = durasi.total_seconds() / 3600
                
                # Jika sudah 10+ jam
                if jam_kerja >= 10:
                    karyawan = absensi.id_karyawan
                    
                    # Cek apakah sudah pernah kirim notif hari ini
                    notif_exists = WhatsAppLog.objects.filter(
                        karyawan=karyawan,
                        notification_type='overtime_alert',
                        sent_at__date=today
                    ).exists()
                    
                    if not notif_exists and karyawan.no_telepon:
                        # Kirim WhatsApp
                        message = f"""⏰ *Alert Lembur - HR CESGS*

Hai {karyawan.nama}!

Anda sudah bekerja selama *{int(jam_kerja)} jam* hari ini.

Jika Anda ingin mengajukan lembur, silakan buka:
👉 https://hr.esgi.ai/karyawan/pengajuan-izin/

Terima kasih atas dedikasi Anda! 💪

_Pesan otomatis dari HR CESGS_"""
                        
                        response = send_whatsapp(karyawan.no_telepon, message)
                        
                        # Log notification
                        WhatsAppLog.objects.create(
                            karyawan=karyawan,
                            notification_type='overtime_alert',
                            phone_number=karyawan.no_telepon,
                            message=message,
                            status='sent' if response.get('status') else 'failed',
                            fonnte_response=response
                        )
                        
                        if response.get('status'):
                            count_sent += 1
                            logger.info(f"Overtime alert dikirim ke {karyawan.nama}")
                        else:
                            logger.warning(f"Gagal kirim alert ke {karyawan.nama}: {response}")
                            
            except Exception as e:
                logger.error(f"Error processing absensi {absensi.id_absensi}: {str(e)}")
                continue
        
        print(f"CekLemburKaryawan: {count_sent} notifikasi terkirim.")
