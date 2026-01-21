"""
Cron jobs for Attendance System
- Check-in reminder at 10:00 AM
- Overtime alert at 18:31 for employees still working
- Finalize WFH status at 23:59 for employees who didn't check out
"""
from django_cron import CronJobBase, Schedule
from datetime import datetime
from apps.hrd.models import Karyawan
from apps.absensi.models import AbsensiMagang
from apps.absensi.helpers.whatsapp import send_checkin_reminder, send_overtime_alert
from apps.absensi.utils import validate_user_location
import logging

logger = logging.getLogger(__name__)


class CheckinReminderCron(CronJobBase):
    """
    Cron job to check at 10:00 AM daily for employees who haven't checked in
    Sends WhatsApp reminder to check in before 11:00 AM deadline
    """
    RUN_AT_TIMES = ['10:00']  # Run at 10:00 AM WIB
    
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
            absensi = AbsensiMagang.objects.filter(
                id_karyawan=karyawan,
                tanggal=today,
                jam_masuk__isnull=False,
                jam_pulang__isnull=True  # Haven't checked out yet
            ).first()
            
            # Send overtime alert only if:
            # 1. Checked in but not checked out
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


class FinalizeWFHStatusCron(CronJobBase):
    """
    Cron job to finalize WFH status at 23:59 for employees who checked in 
    but never checked out. Determines final WFO/WFH based on check-in location.
    """
    RUN_AT_TIMES = ['23:59']  # Run at 23:59 WIB (end of day)
    
    schedule = Schedule(run_at_times=RUN_AT_TIMES)
    code = 'absensi.finalize_wfh_status'
    
    def do(self):
        """Execute WFH status finalization task"""
        today = datetime.now().date()
        
        # Find all attendance with check-in but no check-out
        pending = AbsensiMagang.objects.filter(
            tanggal=today,
            jam_masuk__isnull=False,
            jam_pulang__isnull=True,
            keterangan__isnull=True  # Not yet finalized
        )
        
        finalized_count = 0
        failed_count = 0
        
        for absensi in pending:
            try:
                if absensi.lokasi_masuk:
                    # Parse location coordinates
                    lat, lon = absensi.lokasi_masuk.split(', ')
                    location_result = validate_user_location(float(lat), float(lon))
                    
                    # If checked in outside office, finalize as WFH
                    if not location_result['valid']:
                        absensi.keterangan = 'WFH'
                        absensi.save()
                        finalized_count += 1
                        logger.info(f"Finalized WFH status for {absensi.id_karyawan.nama} (never checked out)")
                    else:
                        # Checked in at office but never checked out - default to WFO
                        absensi.keterangan = 'WFO'
                        absensi.save()
                        finalized_count += 1
                        logger.info(f"Finalized WFO status for {absensi.id_karyawan.nama} (never checked out)")
                        
            except Exception as e:
                failed_count += 1
                logger.error(f"Failed to finalize status for {absensi.id_karyawan.nama}: {str(e)}")
        
        logger.info(f"WFH finalization cron completed. Finalized: {finalized_count}, Failed: {failed_count}")
        print(f"✅ WFH finalization cron: {finalized_count} finalized, {failed_count} failed")
