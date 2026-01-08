from django.db import models
from django.utils.timezone import now
from apps.authentication.models import User
import calendar
from apps.utils.validators import validate_file_size, validate_file_extension

class Karyawan(models.Model):
    STATUS_CHOICES = [
        ('Belum kawin', 'Belum kawin'),
        ('Kawin', 'Kawin'),
        ('Cerai hidup', 'Cerai hidup'),
        ('Cerai mati', 'Cerai mati'),
    ]

    STATUS_KEAKTIFAN_CHOICES = [
        ('Aktif', 'Aktif'),
        ('Tidak Aktif', 'Tidak Aktif')
    ]
    
    DIVISI_CHOICES = [
        ('General', 'General'),
        ('DART', 'DART'),
        ('Annotation', 'Annotation'),
        ('Research and Innovation', 'Research and Innovation'),
        ('CPEBR', 'CPEBR'),
        ('Dataset', 'Dataset'),
        ('Media Dataset', 'Media Dataset'),
        ('Media Non Dataset', 'Media Non Dataset'),
        ('Consulting', 'Consulting'),
    ]
    
    JENIS_KELAMIN_CHOICES = [
        ('L', 'Laki-laki'),
        ('P', 'Perempuan'),
    ]
    
    # Pilihan provinsi dari data wilayah Indonesia
    PROVINSI_CHOICES = [
        ('11', 'ACEH'),
        ('12', 'SUMATERA UTARA'),
        ('13', 'SUMATERA BARAT'),
        ('14', 'RIAU'),
        ('15', 'JAMBI'),
        ('16', 'SUMATERA SELATAN'),
        ('17', 'BENGKULU'),
        ('18', 'LAMPUNG'),
        ('19', 'KEPULAUAN BANGKA BELITUNG'),
        ('21', 'KEPULAUAN RIAU'),
        ('31', 'DKI JAKARTA'),
        ('32', 'JAWA BARAT'),
        ('33', 'JAWA TENGAH'),
        ('34', 'DI YOGYAKARTA'),
        ('35', 'JAWA TIMUR'),
        ('36', 'BANTEN'),
        ('51', 'BALI'),
        ('52', 'NUSA TENGGARA BARAT'),
        ('53', 'NUSA TENGGARA TIMUR'),
        ('61', 'KALIMANTAN BARAT'),
        ('62', 'KALIMANTAN TENGAH'),
        ('63', 'KALIMANTAN SELATAN'),
        ('64', 'KALIMANTAN TIMUR'),
        ('65', 'KALIMANTAN UTARA'),
        ('71', 'SULAWESI UTARA'),
        ('72', 'SULAWESI TENGAH'),
        ('73', 'SULAWESI SELATAN'),
        ('74', 'SULAWESI TENGGARA'),
        ('75', 'GORONTALO'),
        ('76', 'SULAWESI BARAT'),
        ('81', 'MALUKU'),
        ('82', 'MALUKU UTARA'),
        ('91', 'PAPUA BARAT'),
        ('92', 'PAPUA BARAT DAYA'),
        ('94', 'PAPUA'),
        ('95', 'PAPUA SELATAN'),
        ('96', 'PAPUA TENGAH'),
        ('97', 'PAPUA PEGUNUNGAN'),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="karyawan")
    created_at = models.DateTimeField(auto_now_add=True)
    nama = models.CharField(max_length=100)
    nama_catatan_kehadiran = models.CharField(
        max_length=100, 
        blank=True, 
        null=True, 
        help_text="Nama yang digunakan dalam catatan kehadiran"
    )
    jenis_kelamin = models.CharField(max_length=1, choices=JENIS_KELAMIN_CHOICES, default='L')
    jabatan = models.CharField(max_length=50)
    divisi = models.CharField(max_length=50, choices=DIVISI_CHOICES)
    provinsi = models.CharField(max_length=2, choices=PROVINSI_CHOICES, null=True, blank=True)
    kabupaten_kota = models.CharField(max_length=4, null=True, blank=True)
    alamat = models.TextField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES)
    mulai_kontrak = models.DateField(null=True, blank=True)
    batas_kontrak = models.DateField(null=True, blank=True)
    status_keaktifan = models.CharField(max_length=15, choices=STATUS_KEAKTIFAN_CHOICES, default='Aktif')
    no_telepon = models.CharField(max_length=15, null=True, blank=True)
    tanggal_lahir = models.DateField(null=True, blank=True)

    class Meta:
        db_table = 'karyawan'

    def cek_status_kontrak(self):
        """Cek apakah batas kontrak sudah lewat, jika iya ubah status_keaktifan menjadi 'Tidak Aktif'."""
        if self.batas_kontrak and self.batas_kontrak < now().date():
            self.status_keaktifan = 'Tidak Aktif'
            self.save()

    def __str__(self):
        return self.nama

class Cuti(models.Model):
    STATUS_CHOICES = [
        ('menunggu', 'Menunggu'),
        ('disetujui', 'Disetujui'),
        ('ditolak', 'Ditolak'),
    ]

    JENIS_CUTI_CHOICES = [
        ('tahunan', 'Cuti Tahunan'),
        ('melahirkan', 'Cuti Melahirkan (max: 90 hari)'),
        ('menikah', 'Cuti Menikah (max: 3 hari)'),
        ('menikahkan_anak', 'Cuti Menikahkan Anak (max: 2 hari)'),
        ('berkabung_sedarah', 'Cuti Berkabung: suami/istri, ortu, anak (max: 2 hari)'),
        ('berkabung_serumah', 'Cuti Berkabung: anggota serumah (max: 1 hari)'),
        ('khitan_anak', 'Cuti Khitan Anak (max: 2 hari)'),
        ('baptis_anak', 'Cuti Baptis Anak (max: 2 hari)'),
        ('istri_melahirkan', 'Cuti Istri Melahirkan/Keguguran (max: 2 hari)'),
        ('sakit', 'Cuti Sakit (lampirkan surat dokter)'),
    ]

    id_karyawan = models.ForeignKey('hrd.Karyawan', on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    approval = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='approval_cuti')
    absensi = models.ForeignKey('absensi.Absensi', on_delete=models.SET_NULL, null=True, blank=True)
    tanggal_pengajuan = models.DateField(auto_now_add=True)
    tanggal_mulai = models.DateField()
    tanggal_selesai = models.DateField()
    jenis_cuti = models.CharField(max_length=50, choices=JENIS_CUTI_CHOICES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='menunggu')
    file_pengajuan = models.FileField(
        upload_to='cuti/file_pengajuan/', 
        null=True, 
        blank=True,
        validators=[validate_file_size, validate_file_extension]
    )
    file_dokumen_formal = models.FileField(
        upload_to='cuti/file_dokumen_formal/', 
        null=True, 
        blank=True,
        help_text='File .docx cuti yang ditandatangani',
        validators=[validate_file_size, validate_file_extension]
    )
    file_persetujuan = models.FileField(
        upload_to='cuti/file_persetujuan/', 
        null=True, 
        blank=True,
        validators=[validate_file_size, validate_file_extension]
    )
    feedback_hr = models.TextField(null=True, blank=True)

    class Meta:
        db_table = 'cuti'

    def __str__(self):
        return f"{self.id_karyawan.nama} - {self.jenis_cuti} ({self.status})"

class Izin(models.Model):
    STATUS_CHOICES = [
        ('menunggu', 'Menunggu'),
        ('disetujui', 'Disetujui'),
        ('ditolak', 'Ditolak'),
    ]

    JENIS_IZIN_CHOICES = [
        ('telat', 'Izin Telat'),
        ('wfh', 'Izin WFH'),
        ('klaim_lembur', 'Izin Lembur'),
        ('business_trip', 'Izin Business Trip'),
    ]

    KOMPENSASI_LEMBUR_CHOICES = [
        ('makan', 'Uang Makan (Max 35rb)'),
        ('masuk_siang', 'Masuk Siang (Esok Hari)'),
    ]

    id_karyawan = models.ForeignKey('hrd.Karyawan', on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    approval = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='approval_izin')
    absensi = models.ForeignKey('absensi.Absensi', on_delete=models.SET_NULL, null=True, blank=True)
    tanggal_pengajuan = models.DateField(auto_now_add=True)
    tanggal_izin = models.DateField()
    jenis_izin = models.CharField(max_length=50, choices=JENIS_IZIN_CHOICES)
    alasan = models.TextField()
    kompensasi_lembur = models.CharField(
        max_length=20,
        choices=KOMPENSASI_LEMBUR_CHOICES,
        null=True,
        blank=True,
        help_text="Kompensasi untuk pengajuan Izin Lembur",
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='menunggu')
    file_pengajuan = models.FileField(
        upload_to='izin/file_pengajuan/', 
        null=True, 
        blank=True,
        validators=[validate_file_size, validate_file_extension]
    )
    file_persetujuan = models.FileField(
        upload_to='izin/file_persetujuan/', 
        null=True, 
        blank=True,
        validators=[validate_file_size, validate_file_extension]
    )
    feedback_hr = models.TextField(null=True, blank=True)

    class Meta:
        db_table = 'izin'

    def __str__(self):
        return f"{self.id_karyawan.nama} - {self.jenis_izin} ({self.status})"

class JatahCuti(models.Model):
    karyawan = models.ForeignKey('Karyawan', on_delete=models.CASCADE)
    tahun = models.IntegerField()
    total_cuti = models.IntegerField(default=12)
    sisa_cuti = models.IntegerField(default=12)

    class Meta:
        unique_together = ('karyawan', 'tahun')
        db_table = 'jatah_cuti'

    def __str__(self):
        return f"{self.karyawan.nama} - {self.tahun} (Sisa: {self.sisa_cuti})"

class DetailJatahCuti(models.Model):
    jatah_cuti = models.ForeignKey(
        'JatahCuti',
        related_name='detail',
        on_delete=models.CASCADE
    )
    tahun = models.IntegerField()
    bulan = models.IntegerField()
    dipakai = models.BooleanField(default=False)
    jumlah_hari = models.IntegerField(default=0) 
    keterangan = models.TextField(blank=True)
    tanggal_terpakai = models.DateField(null=True, blank=True)
    tersedia = models.BooleanField(default=True, help_text="False jika bulan ini sebelum karyawan masuk kerja")

    class Meta:
        unique_together = ('jatah_cuti', 'tahun', 'bulan')
        db_table = 'detail_jatah_cuti'
        ordering = ['tahun', 'bulan']

    def __str__(self):
        tanggal_info = f" ({self.tanggal_terpakai.strftime('%d-%m-%Y')})" if self.tanggal_terpakai else ""
        status = "Tidak Tersedia" if not self.tersedia else ("Terpakai" if self.dipakai else "Kosong")
        return f'{self.jatah_cuti.karyawan.nama} - {calendar.month_name[self.bulan]} {self.tahun}{tanggal_info} - {status}'

class CutiBersama(models.Model):
    JENIS_CHOICES = [
        ('Cuti Bersama', 'Cuti Bersama'),
        ('WFH', 'WFH'),
    ]
    tanggal = models.DateField()
    jenis = models.CharField(max_length=20, choices=JENIS_CHOICES, default='Cuti Bersama')
    keterangan = models.CharField(max_length=100, blank=True, null=True)

    class Meta:
        db_table = 'cuti_bersama'
        unique_together = ['tanggal']

    def __str__(self):
        return f"{self.tanggal} - {self.keterangan or self.jenis}"

class TidakAmbilCuti(models.Model):
    STATUS_CHOICES = [
        ('menunggu', 'Menunggu'),
        ('disetujui', 'Disetujui'),
        ('ditolak', 'Ditolak'),
    ]

    
    SCENARIO_CHOICES = [
        ('claim_back', 'Claim Kembali - Cuti sudah terpotong'),
        ('prevent_cut', 'Pencegahan Pemotongan - Cuti belum terpotong'),
    ]

    scenario = models.CharField(max_length=20, choices=SCENARIO_CHOICES, null=True, blank=True, help_text="jenis scenario tidak ambil cuti")
    jenis_pengajuan = models.CharField(
        max_length=30,
        default='tidak_ambil_cuti',
        help_text="Jenis pengajuan, default: tidak_ambil_cuti"
    )
    is_processed = models.BooleanField(
        default=False,
        help_text="Apakah sudah diproses untuk adjustment jatah cuti"
    )
    id_karyawan = models.ForeignKey(Karyawan, on_delete=models.CASCADE)
    tanggal = models.ManyToManyField('CutiBersama', blank=True)
    alasan = models.TextField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='menunggu')
    file_pengajuan = models.FileField(
        upload_to='tidak_ambil_cuti/file_pengajuan/', 
        null=True, 
        blank=True,
        validators=[validate_file_size, validate_file_extension]
    )
    file_persetujuan = models.FileField(
        upload_to='tidak_ambil_cuti/file_persetujuan/', 
        null=True, 
        blank=True,
        validators=[validate_file_size, validate_file_extension]
    )
    approval = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='approval_tidak_ambil_cuti')
    tanggal_pengajuan = models.DateField(auto_now_add=True)
    feedback_hr = models.TextField(null=True, blank=True)

    class Meta:
        db_table = 'tidak_ambil_cuti'

    def __str__(self):
        return f"{self.id_karyawan.nama} - Tidak Ambil Cuti ({self.status})"

class RuangRapat(models.Model):
    nama = models.CharField(max_length=100, unique=True)
    deskripsi = models.TextField(blank=True, null=True)
    kapasitas = models.IntegerField(default=10)
    fasilitas = models.TextField(blank=True, null=True, help_text="Contoh: Proyektor, AC, Whiteboard")
    warna_kalender = models.CharField(max_length=7, default='#007bff', help_text="Hex color untuk kalender")
    aktif = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'ruang_rapat'
        verbose_name = 'Ruang Rapat'
        verbose_name_plural = 'Ruang Rapat'
    
    def __str__(self):
        return self.nama


class BookingRuangRapat(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='booking_ruang_rapat')
    ruang_rapat = models.ForeignKey(RuangRapat, on_delete=models.CASCADE, related_name='bookings')
    judul = models.CharField(max_length=200)
    deskripsi = models.TextField(blank=True, null=True)
    tanggal = models.DateField()
    waktu_mulai = models.TimeField()
    waktu_selesai = models.TimeField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'booking_ruang_rapat'
        verbose_name = 'Booking Ruang Rapat'
        verbose_name_plural = 'Booking Ruang Rapat'
        ordering = ['tanggal', 'waktu_mulai']
        
        # Constraint untuk mencegah overlap
        constraints = [
            models.CheckConstraint(
                check=models.Q(waktu_selesai__gt=models.F('waktu_mulai')),
                name='waktu_selesai_after_waktu_mulai'
            )
        ]
    
    def __str__(self):
        return f"{self.judul} - {self.ruang_rapat.nama} ({self.tanggal})"
    
    def clean(self):
        from django.core.exceptions import ValidationError
        from datetime import time
        
        # Validasi jam operasional 09:00-18:00
        if self.waktu_mulai < time(9, 0):
            raise ValidationError('Waktu mulai tidak boleh sebelum 09:00')
        if self.waktu_selesai > time(18, 0):
            raise ValidationError('Waktu selesai tidak boleh setelah 18:00')
        if self.waktu_selesai <= self.waktu_mulai:
            raise ValidationError('Waktu selesai harus setelah waktu mulai')
        
        # Validasi overlap
        overlapping_bookings = BookingRuangRapat.objects.filter(
            ruang_rapat=self.ruang_rapat,
            tanggal=self.tanggal,
            waktu_mulai__lt=self.waktu_selesai,
            waktu_selesai__gt=self.waktu_mulai
        ).exclude(pk=self.pk)
        
        if overlapping_bookings.exists():
            raise ValidationError('Terdapat booking yang bertabrakan pada waktu tersebut')
    
    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)
    
    @property
    def durasi_jam(self):
        """Menghitung durasi booking dalam jam"""
        from datetime import datetime, timedelta
        start = datetime.combine(self.tanggal, self.waktu_mulai)
        end = datetime.combine(self.tanggal, self.waktu_selesai)
        duration = end - start
        return duration.total_seconds() / 3600
