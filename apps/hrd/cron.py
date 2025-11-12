from django_cron import CronJobBase, Schedule
from apps.hrd.models import Karyawan
from django.utils.timezone import now
from apps.hrd.utils.jatah_cuti import potong_jatah_cuti_h_minus_1
from django.contrib.auth.models import User
from notifications.signals import notify

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

