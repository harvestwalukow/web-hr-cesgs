# Migration: Remove message_template - pesan reminder sekarang hardcoded

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('notifikasi', '0003_rename_to_reminder_and_remove_whatsapp_log'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='reminderschedule',
            name='message_template',
        ),
    ]
