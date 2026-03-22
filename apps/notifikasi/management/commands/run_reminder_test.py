"""
Management command untuk menguji pengiriman reminder (check-in & overtime).
Mengabaikan cek waktu jadwal - berguna untuk testing lokal.

Usage:
  python manage.py run_reminder_test checkin     # kirim reminder absen masuk
  python manage.py run_reminder_test overtime    # kirim reminder klaim lembur
  python manage.py run_reminder_test             # jalankan kedua-duanya
"""
from django.core.management.base import BaseCommand
from apps.notifikasi.cron import execute_checkin_reminder, execute_overtime_alert


class Command(BaseCommand):
    help = 'Jalankan logic reminder untuk testing (abaikan jadwal run_time).'

    def add_arguments(self, parser):
        parser.add_argument(
            'type',
            nargs='?',
            choices=['checkin', 'overtime', 'all'],
            default='all',
            help='Jenis reminder: checkin, overtime, atau all (default).',
        )

    def handle(self, *args, **options):
        reminder_type = options.get('type', 'all')

        if reminder_type in ['checkin', 'all']:
            sent, failed = execute_checkin_reminder()
            self.stdout.write(
                self.style.SUCCESS(f'Check-in reminder: {sent} terkirim, {failed} gagal')
            )

        if reminder_type in ['overtime', 'all']:
            sent, failed = execute_overtime_alert()
            self.stdout.write(
                self.style.SUCCESS(f'Overtime alert: {sent} terkirim, {failed} gagal')
            )

        self.stdout.write('')
        self.stdout.write(
            self.style.WARNING(
                'Tip: Pastikan (1) jadwal di Kelola Notifikasi aktif, '
                '(2) user sudah subscribe Web Push, (3) memenuhi kondisi reminder.'
            )
        )
