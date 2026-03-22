"""
Management command untuk menguji Web Push.
Kirim notifikasi uji ke user yang sudah subscribe.

Usage:
  python manage.py test_webpush user@email.com
  python manage.py test_webpush  # kirim ke semua user yang punya subscription
"""
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from webpush import send_user_notification

User = get_user_model()


class Command(BaseCommand):
    help = 'Kirim notifikasi Web Push uji ke user yang sudah subscribe.'

    def add_arguments(self, parser):
        parser.add_argument(
            'email',
            nargs='?',
            help='Email user (opsional). Jika tidak ada, kirim ke semua yang punya subscription.',
        )

    def handle(self, *args, **options):
        email = options.get('email')

        if email:
            try:
                user = User.objects.get(email=email)
                users = [user]
            except User.DoesNotExist:
                self.stderr.write(self.style.ERROR(f'User tidak ditemukan: {email}'))
                return
        else:
            users = list(User.objects.all())

        sent = 0
        skipped = 0
        failed = 0

        payload = {
            "head": "Test Web Push - SmartHR",
            "body": "Ini notifikasi uji. Jika Anda melihat ini, Web Push berfungsi dengan baik.",
            "url": "/",
        }

        for user in users:
            if not hasattr(user, 'webpush_info') or not user.webpush_info.exists():
                skipped += 1
                continue
            try:
                send_user_notification(user=user, payload=payload, ttl=1000)
                sent += 1
                self.stdout.write(self.style.SUCCESS(f'  Terkirim ke {user.email}'))
            except Exception as e:
                failed += 1
                self.stderr.write(self.style.ERROR(f'  Gagal ke {user.email}: {e}'))

        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS(f'Selesai: {sent} terkirim, {skipped} tidak punya subscription, {failed} gagal'))
        if skipped and not email:
            self.stdout.write(
                self.style.WARNING(
                    'Tip: User harus subscribe dulu di Profil → Notifikasi Reminder → klik Subscribe'
                )
            )
