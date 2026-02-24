"""
Cron jobs for Attendance System
- Check-in reminder at 10:00 AM
- Overtime alert at 18:31 for employees still working
- Finalize WFA status at 23:59 for employees who didn't check out
"""
from django_cron import CronJobBase, Schedule
from datetime import datetime, timedelta, time as dt_time
from apps.hrd.models import Karyawan
from apps.absensi.models import AbsensiMagang
from apps.absensi.helpers.whatsapp import send_checkin_reminder, send_overtime_alert
from apps.absensi.utils import validate_user_location
import logging

logger = logging.getLogger(__name__)


class CheckinReminderCron(CronJobBase):
    """
    Cron job to check at 09:00 AM daily for employees who haven't checked in
    Sends WhatsApp reminder to check in before 10:00 AM deadline
    """
    RUN_AT_TIMES = ['09:00']  # Run at 09:00 AM WIB
    
    schedule = Schedule(run_at_times=RUN_AT_TIMES)
    code = 'absensi.checkin_reminder'
    
    def do(self):
        """Execute check-in reminder task"""
        today = datetime.now().date()
        
        # Get all active employees (all roles)
        target_roles = ['Magang', 'Part Time', 'Freelance', 'Project', 'Karyawan Tetap', 'HRD']
        karyawan_list = Karyawan.objects.filter(
            user__role__in=target_roles,
            status_keaktifan='Aktif'
        )
        
        sent_count = 0
        failed_count = 0
        
        for karyawan in karyawan_list:
            # Check if already checked in today
            absensi = AbsensiMagang.objects.filter(
                id_karyawan=karyawan,
                tanggal=today,
                jam_masuk__isnull=False
            ).first()
            
            # Send reminder only if:
            # 1. Not checked in yet
            # 2. Has phone number
            # 3. Reminder not sent yet (check if there's a pending record)
            if not absensi and karyawan.no_telepon:
                try:
                    send_checkin_reminder(karyawan)
                    sent_count += 1
                    logger.info(f"Check-in reminder sent to {karyawan.nama}")
                    
                    # Create a pending absensi record to track reminder
                    AbsensiMagang.objects.get_or_create(
                        id_karyawan=karyawan,
                        tanggal=today,
                        defaults={'reminder_sent': True}
                    )
                    
                except Exception as e:
                    failed_count += 1
                    logger.error(f"Failed to send check-in reminder to {karyawan.nama}: {str(e)}")
        
        logger.info(f"Check-in reminder cron completed. Sent: {sent_count}, Failed: {failed_count}")
        print(f"✅ Check-in reminder cron: {sent_count} sent, {failed_count} failed")


class OvertimeAlertCron(CronJobBase):
    """
    Cron job to check at 18:31 for employees who have checked in 
    but haven't checked out yet, and send them overtime alert via WhatsApp
    ONLY triggering for employees at the office (WFO).
    """
    RUN_AT_TIMES = ['18:31']  # Run at 18:31 WIB (1 minute after threshold)
    
    schedule = Schedule(run_at_times=RUN_AT_TIMES)
    code = 'absensi.overtime_alert'
    
    def do(self):
        """Execute overtime alert task"""
        today = datetime.now().date()
        
        # Get all active employees (all roles)
        target_roles = ['Magang', 'Part Time', 'Freelance', 'Project', 'Karyawan Tetap', 'HRD']
        karyawan_list = Karyawan.objects.filter(
            user__role__in=target_roles,
            status_keaktifan='Aktif'
        )
        
        sent_count = 0
        failed_count = 0
        
        for karyawan in karyawan_list:
            # Check if checked in today but NOT checked out yet
            # AND status/keterangan is 'WFO'
            absensi = AbsensiMagang.objects.filter(
                id_karyawan=karyawan,
                tanggal=today,
                jam_masuk__isnull=False,
                jam_pulang__isnull=True,  # Haven't checked out yet
                keterangan='WFO'          # ONLY for WFO employees
            ).first()
            
            # Send overtime alert only if:
            # 1. Checked in (WFO) but not checked out
            # 2. Has phone number
            # 3. Alert not sent yet today
            if absensi and karyawan.no_telepon and not absensi.overtime_alert_sent:
                try:
                    send_overtime_alert(karyawan)
                    sent_count += 1
                    
                    # Mark alert as sent
                    absensi.overtime_alert_sent = True
                    absensi.save()
                    
                    logger.info(f"Overtime alert sent to {karyawan.nama}")
                    
                except Exception as e:
                    failed_count += 1
                    logger.error(f"Failed to send overtime alert to {karyawan.nama}: {str(e)}")
        
        logger.info(f"Overtime alert cron completed. Sent: {sent_count}, Failed: {failed_count}")
        print(f"✅ Overtime alert cron: {sent_count} sent, {failed_count} failed")


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
