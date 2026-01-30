from django.urls import path
from .views import views_fleksibel

urlpatterns = [
    # URL untuk absensi fleksibel (8.5 jam)
    path('absen/', views_fleksibel.absen_view, name='absen_fleksibel'),
    path('absen-pulang/', views_fleksibel.absen_pulang_view, name='absen_pulang_fleksibel'),
    
    # URL untuk validasi lokasi (geofencing)
    path('check-location/', views_fleksibel.check_location, name='check_location'),
    
    # URL untuk riwayat absensi
    path('riwayat/', views_fleksibel.riwayat_absensi, name='riwayat_absensi'),
    
    # API untuk notifikasi overtime
    path('api/check-overtime-status/', views_fleksibel.check_overtime_status, name='check_overtime_status'),
]

