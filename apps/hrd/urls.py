from django.urls import path
from .views.dashboard import hrd_dashboard, calendar_events
from apps.hrd.views.hrd_cuti import approval_cuti_view, export_riwayat_cuti_excel
from apps.hrd.views.hrd_izin import approval_izin_view, export_riwayat_izin_excel
from .views.cuti_bersama import input_cuti_bersama_view
from .views.manajemen_karyawan import list_karyawan, tambah_karyawan, edit_karyawan, hapus_karyawan, reset_password_karyawan, download_karyawan_excel
from .views.laporan_jatah_cuti import (
    laporan_jatah_cuti_view, 
    export_laporan_jatah_cuti_excel, 
    update_jatah_cuti_ajax, 
    get_detail_jatah_cuti_ajax
)

from .views.booking_ruang_rapat import (
    booking_ruang_rapat_view,
    create_booking,
    edit_booking,
    delete_booking,
    get_booking_detail,
    check_availability,
    booking_calendar_events
)


urlpatterns = [
    path('', hrd_dashboard, name='hrd_dashboard'),
    path('kalender/events/', calendar_events, name='calendar_events'),
    path('approval-cuti/', approval_cuti_view, name='approval_cuti'),
    path('approval-izin/', approval_izin_view, name='approval_izin'),
    path('manajemen-karyawan/', list_karyawan, name='list_karyawan'),
    path('manajemen-karyawan/tambah/', tambah_karyawan, name='tambah_karyawan'),
    path('manajemen-karyawan/edit/<int:id>/', edit_karyawan, name='edit_karyawan'),
    path('manajemen-karyawan/reset-password/<int:id>/', reset_password_karyawan, name='reset_password_karyawan'),
    path('manajemen-karyawan/hapus/<int:id>/', hapus_karyawan, name='hapus_karyawan'),
    path('download-karyawan/', download_karyawan_excel, name='download_karyawan'),
    path('cuti-bersama/', input_cuti_bersama_view, name='input_cuti_bersama'),
    path('approval-cuti/export/', export_riwayat_cuti_excel, name='export_riwayat_cuti_excel'),
    path('approval-izin/export/', export_riwayat_izin_excel, name='export_riwayat_izin_excel'),
    path('laporan-jatah-cuti/', laporan_jatah_cuti_view, name='laporan_jatah_cuti'),
    path('laporan-jatah-cuti/export/', export_laporan_jatah_cuti_excel, name='export_laporan_jatah_cuti_excel'),
    path('ajax/update-jatah-cuti/', update_jatah_cuti_ajax, name='update_jatah_cuti_ajax'),
    path('ajax/get-detail-jatah-cuti/', get_detail_jatah_cuti_ajax, name='get_detail_jatah_cuti_ajax'),
    
    # Booking Ruang Rapat URLs
    path('booking-ruang-rapat/', booking_ruang_rapat_view, name='booking_ruang_rapat'),
    path('booking-ruang-rapat/create/', create_booking, name='create_booking'),
    path('booking-ruang-rapat/edit/<int:booking_id>/', edit_booking, name='edit_booking'),
    path('booking-ruang-rapat/delete/<int:booking_id>/', delete_booking, name='delete_booking'),
    path('booking-ruang-rapat/detail/<int:booking_id>/', get_booking_detail, name='get_booking_detail'),
    path('booking-ruang-rapat/check-availability/', check_availability, name='check_availability'),
    # JSON feed FullCalendar
    path('booking-ruang-rapat/events/', booking_calendar_events, name='booking_calendar_events'),
]
