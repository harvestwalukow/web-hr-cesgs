"""
Cron jobs for Attendance System
- Auto-checkout at 00:01 for employees who forgot to check out
- Check-in reminder and Overtime alert: HR-managed via Kelola Notifikasi, delivery via Web Push (apps.notifikasi.cron)
"""
from django_cron import CronJobBase, Schedule
from datetime import datetime, timedelta, time as dt_time
from apps.absensi.models import AbsensiMagang
import logging

logger = logging.getLogger(__name__)


class AutoCheckoutCron(CronJobBase):
    """
    Cron job to run at 00:01 daily.
    Auto-generates checkout (CO) at 23:59 for employees who forgot to check-out.
    CO location = same as CI (WFO stays WFO, WFA stays WFA).
    """
    RUN_AT_TIMES = ['00:01']  # Run at 00:01 WIB (start of new day)
    
    schedule = Schedule(run_at_times=RUN_AT_TIMES)
    code = 'absensi.auto_checkout'
    
    def do(self):
        """Auto-generate checkout for yesterday's records that have CI but no CO"""
        yesterday = datetime.now().date() - timedelta(days=1)
        
        # Find all absensi with jam_masuk but no jam_pulang for yesterday
        belum_pulang = AbsensiMagang.objects.filter(
            tanggal=yesterday,
            jam_masuk__isnull=False,
            jam_pulang__isnull=True
        )
        
        processed = 0
        for absensi in belum_pulang:
            # Set jam_pulang = 23:59 (end of day)
            absensi.jam_pulang = dt_time(23, 59, 0)
            # Copy CI location to CO (same WFO/WFA)
            absensi.lokasi_pulang = absensi.lokasi_masuk or ''
            absensi.alamat_pulang = absensi.alamat_masuk or 'Auto CO - lokasi sama dengan CI'
            absensi.co_auto_generated = True
            # Keep keterangan from CI (WFO/WFA)
            if not absensi.keterangan:
                absensi.keterangan = 'WFO'
            absensi.save()
            processed += 1
            logger.info(f"Auto CO for {absensi.id_karyawan.nama} on {yesterday}")
        
        if processed > 0:
            logger.info(f"Auto checkout cron: {processed} records processed for {yesterday}")
            print(f"✅ Auto checkout: {processed} records for {yesterday}")
