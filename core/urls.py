from django.contrib import admin
from django.urls import include, path
from django.conf import settings
from django.conf.urls.static import static
from apps.authentication import views as auth_views
from apps.utils import error_views

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", auth_views.login_view, name="home"),
    path("auth/", include("apps.authentication.urls")),
    path("hrd/", include("apps.hrd.urls")),
    path("karyawan/", include("apps.karyawan.urls_karyawan")),
    path("magang/", include("apps.karyawan.urls_magang")),
    path("profil/", include("apps.profil.urls")),
    path("absensi/", include("apps.absensi.urls")),
    path('notifikasi/', include('apps.notifikasi.urls')), 
    path('inbox/notifications/', include('notifications.urls', namespace='notifications')), 
]

# Error handlers
handler403 = 'apps.utils.error_views.custom_403'
handler404 = 'apps.utils.error_views.custom_404'
handler500 = 'apps.utils.error_views.custom_500'

if settings.DEBUG:
    urlpatterns += [
        path('dev/errors/403/', error_views.custom_403, name='dev_403'),
        path('dev/errors/404/', error_views.custom_404, name='dev_404'),
        path('dev/errors/500/', error_views.custom_500, name='dev_500'),
    ]
    # Serve static and media files in development
    from django.contrib.staticfiles.urls import staticfiles_urlpatterns
    urlpatterns += staticfiles_urlpatterns()
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
