from random import choices
from django.db import models
from apps.hrd.models import Karyawan
from apps.absensi.validators import validate_wfh_document_extension, validate_file_size_wfh

class Rules(models.Model):
    id_rules = models.AutoField(primary_key=True)
    nama_rule = models.CharField(max_length=100, unique=True)  # Contoh: "Jam Kerja Standar"
    jam_masuk = models.TimeField()
    jam_keluar = models.TimeField()
    toleransi_telat = models.IntegerField(default=15, help_text="Toleransi keterlambatan dalam menit")
    maksimal_izin = models.IntegerField(default=3, help_text="Jumlah maksimal izin dalam sebulan")
    
    # 8.5 hour system configuration fields
    min_jam_masuk = models.TimeField(default='06:00:00', help_text='Waktu minimum check-in (default: 06:00)')
    batas_checkin_reminder = models.TimeField(default='10:00:00', help_text='Waktu untuk mengirim reminder check-in (default: 10:00)')
    batas_deadline_checkin = models.TimeField(default='11:00:00', help_text='Batas akhir check-in (default: 11:00)')
    durasi_kerja_jam = models.DecimalField(max_digits=3, decimal_places=1, default=8.5, help_text='Durasi kerja dalam jam (contoh: 8.5 untuk 8 jam 30 menit)')
    batas_overtime = models.TimeField(default='18:30:00', help_text='Batas waktu untuk alert overtime (default: 18:30)')
    
    created_at = models.DateTimeField(auto_now_add=True)  # Waktu dibuat
    updated_at = models.DateTimeField(auto_now=True)  # Waktu terakhir diperbarui

    def __str__(self):
        return self.nama_rule


class Absensi(models.Model):
    id_absensi = models.AutoField(primary_key=True)
    id_karyawan = models.ForeignKey(Karyawan, on_delete=models.CASCADE)
    rules = models.ForeignKey(Rules, on_delete=models.SET_NULL, null=True, blank=True)
    tanggal = models.DateField()
    bulan = models.IntegerField()
    tahun = models.IntegerField()
    
    status_absensi = models.CharField(
        max_length=25, 
        choices=[
            ('Tepat Waktu', 'Tepat Waktu'),
            ('Terlambat', 'Terlambat'),
            ('Izin', 'Izin'),
            ('Sakit', 'Sakit'),
            ('Cuti', 'Cuti'),
            ('Libur', 'Libur'),
            ('Research and Innovation', 'Research and Innovation'),
            ('CPEBR', 'CPEBR')
        ]
    )
    jam_masuk = models.TimeField(null=True, blank=True)
    jam_keluar = models.TimeField(null=True, blank=True)
    is_libur = models.BooleanField(default=False)

    #  Kolom tambahan untuk menyimpan informasi file upload
    nama_file = models.CharField(max_length=255, null=True, blank=True)  # Nama file yang diunggah
    file_url = models.CharField(max_length=500, null=True, blank=True)  # URL file di media storage
    created_at = models.DateTimeField(auto_now_add=True)  # Waktu upload pertama kali

    def __str__(self):
        return f"Absensi {self.id_karyawan.nama} - {self.tanggal} ({self.status_absensi})"


class AbsensiMagang(models.Model):
    id_absensi = models.AutoField(primary_key=True)
    id_karyawan = models.ForeignKey(Karyawan, on_delete=models.CASCADE)
    tanggal = models.DateField()

    jam_masuk = models.TimeField(null=True, blank=True)
    jam_pulang = models.TimeField(null=True, blank=True)

    lokasi_masuk = models.CharField(max_length=255, null=True, blank=True)
    lokasi_pulang = models.CharField(max_length=255, null=True, blank=True)

    screenshot_masuk = models.ImageField(upload_to='absensi/screenshots/masuk/%Y/%m/%d/', null=True, blank=True)
    screenshot_pulang = models.ImageField(upload_to='absensi/screenshots/pulang/%Y/%m/%d/', null=True, blank=True)

    alamat_masuk = models.CharField(max_length=500, null=True, blank=True)
    alamat_pulang = models.CharField(max_length=500, null=True, blank=True)
    
    keterangan = models.CharField(
        max_length=25,
        choices=[
            ('WFO', 'WFO'),
            ('WFH', 'WFH'),
            ('Izin Telat', 'Izin Telat'),
            ('Izin Sakit', 'Izin Sakit')
        ],
        null=True,
        blank=False
    )

    status = models.CharField(
        max_length=25,
        choices=[
            ('Tepat Waktu', 'Tepat Waktu'),
            ('Terlambat', 'Terlambat')
        ],
        default='Tepat Waktu'
    )

    # Alert tracking fields (from 8.5 hour system)
    reminder_sent = models.BooleanField(
        default=False,
        help_text='Flag untuk tracking apakah reminder 10 AM sudah dikirim'
    )
    
    overtime_alert_sent = models.BooleanField(
        default=False,
        help_text='Flag untuk tracking apakah alert overtime sudah dikirim'
    )
    
    # Advanced attendance fields
    hr_keterangan = models.TextField(
        null=True, 
        blank=True,
        help_text="Keterangan bebas dari HR untuk karyawan yang tidak hadir atau tidak ada aktivitas"
    )
    
    aktivitas_wfh = models.TextField(
        null=True, 
        blank=True,
        help_text="Deskripsi aktivitas yang dikerjakan saat WFH"
    )
    
    dokumen_persetujuan = models.FileField(
        upload_to='absensi/wfh_approval/%Y/%m/%d/',
        null=True, 
        blank=True,
        validators=[validate_file_size_wfh, validate_wfh_document_extension],
        help_text="Dokumen persetujuan atasan untuk WFH (.png, .jpg, .pdf, max 5MB)"
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['id_karyawan', 'tanggal']
        verbose_name = 'Absensi Magang'
        verbose_name_plural = 'Absensi Magang'


    def __str__(self):
        return f"Absensi {self.id_karyawan.nama} - {self.tanggal} ({self.status})"




class LokasiKantor(models.Model):
    """Model untuk menyimpan lokasi kantor untuk validasi geofencing absensi"""
    nama = models.CharField(max_length=100, unique=True, help_text="Nama lokasi (contoh: ASEEC)")
    latitude = models.DecimalField(max_digits=10, decimal_places=8, help_text="Koordinat lintang")
    longitude = models.DecimalField(max_digits=11, decimal_places=8, help_text="Koordinat bujur")
    radius = models.IntegerField(default=150, help_text="Radius toleransi dalam meter")
    is_active = models.BooleanField(default=True, help_text="Apakah lokasi ini aktif digunakan")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Lokasi Kantor'
        verbose_name_plural = 'Lokasi Kantor'

    def __str__(self):
        return f"{self.nama} ({self.latitude}, {self.longitude}) - Radius: {self.radius}m"
