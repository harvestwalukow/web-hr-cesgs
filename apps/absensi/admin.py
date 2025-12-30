from django.contrib import admin
from .models import LokasiKantor, AbsensiMagang, Absensi, Rules, FaceData, FaceEncoding


@admin.register(LokasiKantor)
class LokasiKantorAdmin(admin.ModelAdmin):
    list_display = ['nama', 'latitude', 'longitude', 'radius', 'is_active', 'updated_at']
    list_filter = ['is_active']
    search_fields = ['nama']


@admin.register(AbsensiMagang)
class AbsensiMagangAdmin(admin.ModelAdmin):
    list_display = ['id_karyawan', 'tanggal', 'jam_masuk', 'jam_pulang', 'status', 'keterangan']
    list_filter = ['status', 'keterangan', 'tanggal']
    search_fields = ['id_karyawan__nama']
    date_hierarchy = 'tanggal'


@admin.register(Absensi)
class AbsensiAdmin(admin.ModelAdmin):
    list_display = ['id_karyawan', 'tanggal', 'status_absensi', 'jam_masuk', 'jam_keluar']
    list_filter = ['status_absensi', 'bulan', 'tahun']
    search_fields = ['id_karyawan__nama']
