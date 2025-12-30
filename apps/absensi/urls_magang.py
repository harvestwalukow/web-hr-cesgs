from django.urls import path
from .views import views_magang

urlpatterns = [
    # URL untuk absensi
    path('absen/', views_magang.absen_view, name='absen_magang'),
    path('absen-pulang/', views_magang.absen_pulang_view, name='absen_pulang_magang'),
    
    # URL untuk validasi lokasi (geofencing)
    path('check-location/', views_magang.check_location, name='check_location'),
    
    # URL untuk riwayat absensi
    path('riwayat/', views_magang.riwayat_absensi, name='riwayat_absensi'),
]