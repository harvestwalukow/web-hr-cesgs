from django.urls import path
from . import views

urlpatterns = [
    path('', views.profil_saya, name='profil_saya'),
    path('ubah-password/', views.ubah_password, name='ubah_password'),
]
