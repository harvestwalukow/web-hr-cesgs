"""
Cron untuk menjalankan jadwal WhatsApp yang dikelola HR.
Menggantikan CheckinReminderCron dan OvertimeAlertCron.
"""
from django_cron import CronJobBase, Schedule
from datetime import datetime
from apps.notifikasi.models import WhatsAppSchedule
from apps.hrd.models import Karyawan
from apps.absensi.models import AbsensiMagang
from apps.absensi.helpers.whatsapp import send_checkin_reminder, send_overtime_alert
import logging

logger = logging.getLogger(__name__)


def execute_checkin_reminder(message_template=None):
    """Kirim reminder check-in ke karyawan yang belum absen masuk hari ini."""
    today = datetime.now().date()
    target_roles = ['Magang', 'Part Time', 'Freelance', 'Project', 'Karyawan Tetap', 'HRD']
    karyawan_list = Karyawan.objects.filter(
        user__role__in=target_roles,
        status_keaktifan='Aktif'
    )
    sent_count = 0
    failed_count = 0

    for karyawan in karyawan_list:
        absensi = AbsensiMagang.objects.filter(
            id_karyawan=karyawan,
            tanggal=today,
            jam_masuk__isnull=False
        ).first()

        if not absensi and karyawan.no_telepon:
            try:
                send_checkin_reminder(karyawan, message_template)
                sent_count += 1
                logger.info(f"Check-in reminder sent to {karyawan.nama}")
                AbsensiMagang.objects.get_or_create(
                    id_karyawan=karyawan,
                    tanggal=today,
                    defaults={'reminder_sent': True}
                )
            except Exception as e:
                failed_count += 1
                logger.error(f"Failed to send check-in reminder to {karyawan.nama}: {str(e)}")

    return sent_count, failed_count


def execute_overtime_alert(message_template=None):
    """Kirim overtime alert ke karyawan WFO yang sudah CI tapi belum CO."""
    today = datetime.now().date()
    target_roles = ['Part Time', 'Freelance', 'Project', 'Karyawan Tetap', 'HRD']
    karyawan_list = Karyawan.objects.filter(
        user__role__in=target_roles,
        status_keaktifan='Aktif'
    )
    sent_count = 0
    failed_count = 0

    for karyawan in karyawan_list:
        absensi = AbsensiMagang.objects.filter(
            id_karyawan=karyawan,
            tanggal=today,
            jam_masuk__isnull=False,
            jam_pulang__isnull=True,
            keterangan='WFO'
        ).first()

        if absensi and karyawan.no_telepon and not absensi.overtime_alert_sent:
            try:
                send_overtime_alert(karyawan, message_template)
                sent_count += 1
                absensi.overtime_alert_sent = True
                absensi.save()
                logger.info(f"Overtime alert sent to {karyawan.nama}")
            except Exception as e:
                failed_count += 1
                logger.error(f"Failed to send overtime alert to {karyawan.nama}: {str(e)}")

    return sent_count, failed_count


class SchedulerWhatsAppCron(CronJobBase):
    """
    Menjalankan jadwal WhatsApp yang aktif.
    Cek setiap 15 menit apakah ada jadwal yang harus dijalankan.
    """
    RUN_EVERY_MINS = 15
    schedule = Schedule(run_every_mins=RUN_EVERY_MINS)
    code = 'notifikasi.scheduler_whatsapp'

    def do(self):
        now = datetime.now()
        today = now.date()
        current_time = now.time()

        schedules = WhatsAppSchedule.objects.filter(is_active=True)
        for schedule in schedules:
            try:
                if schedule.last_run_date == today:
                    continue
                if schedule.run_time > current_time:
                    continue

                msg_tpl = schedule.message_template.strip() if schedule.message_template else None
                if schedule.schedule_type == 'checkin_reminder':
                    sent, failed = execute_checkin_reminder(msg_tpl)
                    logger.info(f"Check-in reminder: {sent} sent, {failed} failed")
                    print(f"WhatsApp Schedule: Check-in reminder - {sent} sent, {failed} failed")
                elif schedule.schedule_type == 'overtime_alert':
                    sent, failed = execute_overtime_alert(msg_tpl)
                    logger.info(f"Overtime alert: {sent} sent, {failed} failed")
                    print(f"WhatsApp Schedule: Overtime alert - {sent} sent, {failed} failed")
                else:
                    continue

                schedule.last_run_date = today
                schedule.save()
            except Exception as e:
                logger.error(f"Error running schedule {schedule.schedule_type}: {str(e)}")
