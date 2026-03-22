"""
Cron untuk menjalankan jadwal reminder check-in/overtime via Web Push.
"""
from django_cron import CronJobBase, Schedule
from datetime import datetime
from webpush import send_user_notification
from apps.notifikasi.models import ReminderSchedule
from apps.hrd.models import Karyawan
from apps.absensi.models import AbsensiMagang
import logging

logger = logging.getLogger(__name__)

# Pesan reminder hardcoded
CHECKIN_HEAD = "Reminder Absen Masuk"
CHECKIN_BODY = """Halo {nama}, Anda belum melakukan absen masuk hari ini."""

OVERTIME_HEAD = "Notifikasi Lembur"
OVERTIME_BODY = """Halo {nama}, Anda masih bekerja melewati jam 18:30 WIB. Silakan melakukan Klaim Lembur."""


def _get_url_role(user_role):
    """Helper to determine URL segment based on user role."""
    if user_role in ['Magang', 'Part Time', 'Freelance', 'Project']:
        return "magang"
    return "karyawan"


def _user_has_webpush_subscription(user):
    """Cek apakah user sudah subscribe Web Push."""
    return hasattr(user, 'webpush_info') and user.webpush_info.exists()


def execute_checkin_reminder():
    """Kirim reminder absen masuk via Web Push ke karyawan yang belum absen masuk hari ini."""
    today = datetime.now().date()
    target_roles = ['Part Time', 'Freelance', 'Project', 'Karyawan Tetap', 'HRD']
    karyawan_list = Karyawan.objects.filter(
        user__role__in=target_roles,
        status_keaktifan='Aktif'
    )
    sent_count = 0
    failed_count = 0
    base_url = "https://hr.esgi.ai"

    for karyawan in karyawan_list:
        absensi = AbsensiMagang.objects.filter(
            id_karyawan=karyawan,
            tanggal=today,
            jam_masuk__isnull=False
        ).first()

        if not absensi and _user_has_webpush_subscription(karyawan.user):
            try:
                url_role = _get_url_role(karyawan.user.role)
                body = CHECKIN_BODY.format(nama=karyawan.nama, url_role=url_role)
                payload = {
                    "head": CHECKIN_HEAD,
                    "body": body,
                    "url": f"{base_url}/{url_role}/absensi/",
                }
                send_user_notification(user=karyawan.user, payload=payload, ttl=1000)
                sent_count += 1
                logger.info(f"Check-in reminder (Web Push) sent to {karyawan.nama}")
                AbsensiMagang.objects.get_or_create(
                    id_karyawan=karyawan,
                    tanggal=today,
                    defaults={'reminder_sent': True}
                )
            except Exception as e:
                failed_count += 1
                logger.error(f"Failed to send check-in reminder to {karyawan.nama}: {str(e)}")

    return sent_count, failed_count


def execute_overtime_alert():
    """Kirim reminder klaim lembur via Web Push ke karyawan WFO yang sudah CI tapi belum CO."""
    today = datetime.now().date()
    target_roles = ['Magang', 'Part Time', 'Freelance', 'Project', 'Karyawan Tetap', 'HRD']
    karyawan_list = Karyawan.objects.filter(
        user__role__in=target_roles,
        status_keaktifan='Aktif'
    )
    sent_count = 0
    failed_count = 0
    base_url = "https://hr.esgi.ai"

    for karyawan in karyawan_list:
        absensi = AbsensiMagang.objects.filter(
            id_karyawan=karyawan,
            tanggal=today,
            jam_masuk__isnull=False,
            jam_pulang__isnull=True,
            keterangan='WFO'
        ).first()

        if absensi and not absensi.overtime_alert_sent and _user_has_webpush_subscription(karyawan.user):
            try:
                url_role = _get_url_role(karyawan.user.role)
                body = OVERTIME_BODY.format(nama=karyawan.nama, url_role=url_role)
                payload = {
                    "head": OVERTIME_HEAD,
                    "body": body,
                    "url": f"{base_url}/{url_role}/pengajuan-izin/",
                }
                send_user_notification(user=karyawan.user, payload=payload, ttl=1000)
                sent_count += 1
                absensi.overtime_alert_sent = True
                absensi.save()
                logger.info(f"Overtime alert (Web Push) sent to {karyawan.nama}")
            except Exception as e:
                failed_count += 1
                logger.error(f"Failed to send overtime alert to {karyawan.nama}: {str(e)}")

    return sent_count, failed_count


class ReminderScheduleCron(CronJobBase):
    """
    Menjalankan jadwal reminder yang aktif.
    Kirim via Web Push (notifikasi sistem browser).
    """
    RUN_EVERY_MINS = 15
    schedule = Schedule(run_every_mins=RUN_EVERY_MINS)
    code = 'notifikasi.reminder_schedule'

    def do(self):
        now = datetime.now()
        today = now.date()
        current_time = now.time()

        schedules = ReminderSchedule.objects.filter(is_active=True)
        for schedule in schedules:
            try:
                if schedule.last_run_date == today:
                    continue
                if schedule.run_time > current_time:
                    continue

                if schedule.schedule_type == 'checkin_reminder':
                    sent, failed = execute_checkin_reminder()
                    logger.info(f"Check-in reminder: {sent} sent, {failed} failed")
                    print(f"Reminder Schedule: Check-in reminder - {sent} sent, {failed} failed")
                elif schedule.schedule_type == 'overtime_alert':
                    sent, failed = execute_overtime_alert()
                    logger.info(f"Overtime alert: {sent} sent, {failed} failed")
                    print(f"Reminder Schedule: Overtime alert - {sent} sent, {failed} failed")
                else:
                    continue

                schedule.last_run_date = today
                schedule.save()
            except Exception as e:
                logger.error(f"Error running schedule {schedule.schedule_type}: {str(e)}")
