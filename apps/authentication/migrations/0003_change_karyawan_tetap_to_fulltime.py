from django.db import migrations, models


def migrate_role_karyawan_tetap_to_fulltime(apps, schema_editor):
    User = apps.get_model('authentication', 'User')
    User.objects.filter(role='Karyawan Tetap').update(role='Fulltime')


class Migration(migrations.Migration):

    dependencies = [
        ('authentication', '0002_alter_user_role'),
    ]

    operations = [
        migrations.AlterField(
            model_name='user',
            name='role',
            field=models.CharField(
                choices=[
                    ('HRD', 'HRD'),
                    ('Fulltime', 'Fulltime'),
                    ('Magang', 'Magang'),
                    ('Part Time', 'Part Time'),
                    ('Freelance', 'Freelance'),
                    ('Project', 'Project'),
                ],
                max_length=20,
            ),
        ),
        migrations.RunPython(migrate_role_karyawan_tetap_to_fulltime, migrations.RunPython.noop),
    ]


