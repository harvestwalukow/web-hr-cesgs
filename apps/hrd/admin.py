from django.contrib import admin
from .models import RuangRapat, BookingRuangRapat

@admin.register(RuangRapat)
class RuangRapatAdmin(admin.ModelAdmin):
    list_display = ['nama', 'kapasitas', 'aktif', 'created_at']
    list_filter = ['aktif', 'created_at']
    search_fields = ['nama', 'deskripsi']
    list_editable = ['aktif']
    ordering = ['nama']
    
    fieldsets = (
        ('Informasi Dasar', {
            'fields': ('nama', 'deskripsi', 'kapasitas')
        }),
        ('Fasilitas & Tampilan', {
            'fields': ('fasilitas', 'warna_kalender')
        }),
        ('Status', {
            'fields': ('aktif',)
        })
    )

@admin.register(BookingRuangRapat)
class BookingRuangRapatAdmin(admin.ModelAdmin):
    list_display = ['judul', 'ruang_rapat', 'user', 'tanggal', 'waktu_mulai', 'waktu_selesai', 'created_at']
    list_filter = ['ruang_rapat', 'tanggal', 'created_at']
    search_fields = ['judul', 'user__username', 'user__first_name', 'user__last_name']
    date_hierarchy = 'tanggal'
    ordering = ['-tanggal', '-waktu_mulai']
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = (
        ('Informasi Booking', {
            'fields': ('user', 'ruang_rapat', 'judul', 'deskripsi')
        }),
        ('Jadwal', {
            'fields': ('tanggal', 'waktu_mulai', 'waktu_selesai')
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user', 'ruang_rapat')