from django.urls import path
from .views.dashboard_karyawan import karyawan_dashboard, calendar_events, data_dashboard_karyawan
from .views.cuti import cuti_view, hapus_cuti_view
from .views.izin import izin_view, hapus_izin_view
from .views.tidak_ambil_cuti import tidak_ambil_cuti_view, hapus_tidak_ambil_cuti_view
from .views.karyawan_views import edit_profil
from .views.riwayat_cuti_detail import riwayat_cuti_detail_view, export_riwayat_cuti_excel

urlpatterns = [
    path('', karyawan_dashboard, name='karyawan_dashboard'),
    path('kalender/events/', calendar_events, name='calendar_events'),
    path('data-dashboard/', data_dashboard_karyawan, name='data_dashboard_karyawan'),

    # Pengajuan dan hapus
    path('pengajuan-cuti/', cuti_view, name='pengajuan_cuti'),
    path('hapus-cuti/<int:id>/', hapus_cuti_view, name='hapus_cuti'),
    path('pengajuan-izin/', izin_view, name='pengajuan_izin'),
    path('hapus-izin/<int:id>/', hapus_izin_view, name='hapus_izin'),
    path('tidak-ambil-cuti/', tidak_ambil_cuti_view, name='tidak_ambil_cuti'),
    path('hapus-tidak-ambil-cuti/<int:id>/', hapus_tidak_ambil_cuti_view, name='hapus_tidak_ambil_cuti'),
    
    # Riwayat cuti detail
    path('riwayat-cuti-detail/', riwayat_cuti_detail_view, name='riwayat_cuti_detail'),
    path('export-riwayat-cuti-excel/', export_riwayat_cuti_excel, name='export_riwayat_cuti_excel'),

    # Profil
    path('edit-profil/', edit_profil, name='edit_profil'),
]
