from django.urls import path
from .views import views_magang

urlpatterns = [
    # URL untuk pengambilan data wajah
    path('ambil-wajah/', views_magang.ambil_wajah_view, name='ambil_wajah'),
    path('save-face-data/', views_magang.save_face_data, name='save_face_data'),
    
    
    # URL untuk absensi
    path('absen/', views_magang.absen_view, name='absen_magang'),
    path('absen-pulang/', views_magang.absen_pulang_view, name='absen_pulang_magang'),
    path('verify-face/', views_magang.verify_face, name='verify_face'),
    
    # URL untuk validasi lokasi (geofencing)
    path('check-location/', views_magang.check_location, name='check_location'),
    
    # URL untuk riwayat absensi
    path('riwayat/', views_magang.riwayat_absensi, name='riwayat_absensi'),
]