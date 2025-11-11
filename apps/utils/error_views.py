from django.shortcuts import render

def custom_403(request, exception=None):
    return render(request, 'home/page-403.html', status=403)

def custom_404(request, exception=None):
    return render(request, 'home/page-404.html', status=404)

def custom_500(request):
    return render(request, 'home/page-500.html', status=500)