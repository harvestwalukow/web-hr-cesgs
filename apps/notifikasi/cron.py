"""
Cron untuk menjalankan jadwal reminder check-in/overtime via Web Push.
"""
from django_cron import CronJobBase, Schedule
from datetime import datetime
from django.utils import timezone
from webpush import send_user_notification
from apps.notifikasi.models import ReminderSchedule
from apps.hrd.models import Karyawan
from apps.absensi.models import AbsensiMagang
from apps.absensi.utils import get_rule_for_date, get_effective_rule_config
import logging

logger = logging.getLogger(__name__)

# Pesan reminder hardcoded
CHECKIN_HEAD = "Reminder Absen Masuk"
CHECKIN_BODY = """Halo {nama}, Anda belum melakukan absen masuk hari ini."""

OVERTIME_HEAD = "Notifikasi Lembur"
OVERTIME_BODY = """Halo {nama}, Anda masih bekerja melewati jam 18:30 WIB. Silakan melakukan Klaim Lembur."""

CHECKOUT_HEAD = "Reminder Absen Pulang"
CHECKOUT_BODY = """Halo {nama}, durasi kerja Anda sudah mencapai batas minimal hari ini. Silakan lakukan absen pulang."""

CHECKOUT_TARGET_ROLES = ('Magang', 'Part Time', 'Freelance', 'Project', 'Karyawan Tetap', 'HRD')


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


def _required_work_hours_for_date(tanggal):
    """Durasi kerja minimal (jam) sesuai rule hari itu; fallback 8.5."""
    rule = get_rule_for_date(tanggal)
    if not rule:
        return 8.5
    cfg = get_effective_rule_config(rule, tanggal)
    if not cfg:
        return 8.5
    return float(cfg['durasi_kerja_jam'])


def execute_checkout_reminder():
    """
    Web Push ke karyawan yang sudah CI, belum CO, dan sudah melewati durasi kerja minimal (per orang).
    Dijalankan periodik (cron per menit) saat jadwal checkout_reminder aktif di Kelola Notifikasi.
    """
    if not ReminderSchedule.objects.filter(schedule_type='checkout_reminder', is_active=True).exists():
        return 0, 0

    now = timezone.localtime()
    today = now.date()
    base_url = "https://hr.esgi.ai"
    checkout_url = f"{base_url}/absensi/fleksibel/absen-pulang/"

    qs = AbsensiMagang.objects.filter(
        tanggal=today,
        jam_masuk__isnull=False,
        jam_pulang__isnull=True,
        checkout_reminder_sent=False,
    ).select_related('id_karyawan', 'id_karyawan__user')

    sent_count = 0
    failed_count = 0

    for absensi in qs:
        karyawan = absensi.id_karyawan
        user = karyawan.user
        if user.role not in CHECKOUT_TARGET_ROLES or karyawan.status_keaktifan != 'Aktif':
            continue
        if not _user_has_webpush_subscription(user):
            continue

        required_hours = _required_work_hours_for_date(today)
        start_dt = timezone.make_aware(
            datetime.combine(today, absensi.jam_masuk),
            timezone.get_current_timezone(),
        )
        elapsed_hours = (now - start_dt).total_seconds() / 3600.0
        if elapsed_hours < required_hours:
            continue

        try:
            payload = {
                "head": CHECKOUT_HEAD,
                "body": CHECKOUT_BODY.format(nama=karyawan.nama),
                "url": checkout_url,
            }
            send_user_notification(user=user, payload=payload, ttl=1000)
            sent_count += 1
            absensi.checkout_reminder_sent = True
            absensi.save(update_fields=['checkout_reminder_sent'])
            logger.info(f"Checkout reminder (Web Push) sent to {karyawan.nama}")
        except Exception as e:
            failed_count += 1
            logger.error(f"Failed to send checkout reminder to {karyawan.nama}: {str(e)}")

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
                # Reminder absen pulang di-handle CheckoutReminderCron (per menit, berbasis durasi)
                if schedule.schedule_type == 'checkout_reminder':
                    continue
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


class CheckoutReminderCron(CronJobBase):
    """
    Cek setiap menit: karyawan sudah melewati durasi kerja minimal tapi belum CO → Web Push sekali per hari.
    Aktif/nonaktif lewat Kelola Notifikasi (tipe Reminder Absen Pulang).
    """
    RUN_EVERY_MINS = 1
    schedule = Schedule(run_every_mins=RUN_EVERY_MINS)
    code = 'notifikasi.checkout_reminder'

    def do(self):
        sent, failed = execute_checkout_reminder()
        if sent or failed:
            logger.info(f"Checkout reminder: {sent} sent, {failed} failed")
            print(f"Checkout reminder: {sent} sent, {failed} failed")
