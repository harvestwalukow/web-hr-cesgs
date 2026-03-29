# Migration: Rename WhatsAppSchedule to ReminderSchedule, delete WhatsAppLog

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('notifikasi', '0002_add_whatsapp_schedule'),
    ]

    operations = [
        migrations.RenameModel(
            old_name='WhatsAppSchedule',
            new_name='ReminderSchedule',
        ),
        migrations.AlterModelTable(
            name='reminderschedule',
            table='reminder_schedule',
        ),
        migrations.DeleteModel(
            name='WhatsAppLog',
        ),
    ]
