"""
PWA manifest view - untuk Safari iOS Web Push (Add to Home Screen).
"""
from django.http import JsonResponse
from django.views.decorators.http import require_GET
from django.conf import settings


@require_GET
def manifest_json(request):
    """Serve web app manifest for PWA / Add to Home Screen."""
    base_url = request.build_absolute_uri("/").rstrip("/")
    static_base = request.build_absolute_uri(settings.STATIC_URL)

    manifest = {
        "name": "SmartHR CESGS",
        "short_name": "SmartHR",
        "description": "Human Resource Management System",
        "start_url": "/",
        "display": "standalone",
        "background_color": "#ffffff",
        "theme_color": "#5e72e4",
        "orientation": "portrait-primary",
        "icons": [
            {
                "src": f"{static_base}assets/img/brand/Logo.ico",
                "sizes": "48x48",
                "type": "image/x-icon",
                "purpose": "any",
            },
            {
                "src": f"{static_base}assets/img/brand/Logo.ico",
                "sizes": "192x192",
                "type": "image/x-icon",
                "purpose": "any maskable",
            },
            {
                "src": f"{static_base}assets/img/brand/Logo.ico",
                "sizes": "512x512",
                "type": "image/x-icon",
                "purpose": "any maskable",
            },
        ],
    }
    return JsonResponse(manifest, json_dumps_params={"indent": 2})
