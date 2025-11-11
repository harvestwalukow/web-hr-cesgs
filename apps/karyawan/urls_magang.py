from django.urls import path
from .views import magang_views

urlpatterns = [
    # Dashboard
    path('', magang_views.magang_dashboard, name='magang_dashboard'),
    
    # Calendar
    path('calendar-events-magang/', magang_views.calendar_events_magang, name='calendar_events_magang'),
    
    # Profile Management - menggunakan template yang sudah ada
    path('edit-profil/', magang_views.edit_profile_magang, name='edit_profile_magang'),
    path('ubah-password/', magang_views.ubah_password_magang, name='ubah_password_magang'),
]
