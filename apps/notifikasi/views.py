from django.shortcuts import render, redirect, get_object_or_404
from django.views.generic import ListView
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import JsonResponse
from django.contrib import messages
from notifications.models import Notification
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger

@login_required
def mark_as_read(request, notification_id):
    notification = get_object_or_404(Notification, id=notification_id, recipient=request.user)
    notification.mark_as_read()
    
    # Redirect ke URL yang sesuai dengan notifikasi
    if hasattr(notification, 'data') and notification.data and 'url' in notification.data:
        return redirect(notification.data['url'])
    
    # Redirect berdasarkan jenis notifikasi
    if notification.verb and 'cuti disetujui' in notification.verb.lower() and request.user.role != 'HRD':
        return redirect('pengajuan_cuti')
    elif notification.verb and 'cuti ditolak' in notification.verb.lower() and request.user.role != 'HRD':
        return redirect('pengajuan_cuti')
    elif notification.verb and 'izin disetujui' in notification.verb.lower() and request.user.role != 'HRD':
        return redirect('pengajuan_izin')
    elif notification.verb and 'izin ditolak' in notification.verb.lower() and request.user.role != 'HRD':
        return redirect('pengajuan_izin')
    elif notification.verb and 'cuti' in notification.verb.lower() and request.user.role == 'HRD':
        return redirect('approval_cuti')
    elif notification.verb and 'izin' in notification.verb.lower() and request.user.role == 'HRD':
        return redirect('approval_izin')
    
    # Redirect berdasarkan role jika tidak ada URL spesifik
    if request.user.role == 'HRD':
        return redirect('hrd_dashboard')
    elif request.user.role == 'Karyawan Tetap':
        return redirect('karyawan_dashboard')
    elif request.user.role == 'Magang':
        return redirect('magang_dashboard')
    else:
        return redirect('login') 

@login_required
def mark_all_as_read(request):
    request.user.notifications.mark_all_as_read()
    return redirect('all_notifications')

@login_required
def delete_all_notifications(request):
    """Hapus semua notifikasi untuk user yang sedang login"""
    if request.method == 'POST':
        # Hapus semua notifikasi user
        request.user.notifications.all().delete()
        messages.success(request, 'Semua notifikasi berhasil dihapus.')
    
    return redirect('all_notifications')

class AllNotificationsView(LoginRequiredMixin, ListView):
    model = Notification
    template_name = 'notifications/all.html'
    context_object_name = 'notifications'
    paginate_by = 10
    
    def get_queryset(self):
        return self.request.user.notifications.all().order_by('-timestamp')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        notifications = self.get_queryset()
        
        # Konfigurasi paginasi
        paginator = Paginator(notifications, self.paginate_by)
        page = self.request.GET.get('page', 1)
        
        try:
            notifications_page = paginator.page(page)
        except PageNotAnInteger:
            notifications_page = paginator.page(1)
        except EmptyPage:
            notifications_page = paginator.page(paginator.num_pages)
        
        # Tambahkan informasi paginasi ke context
        context['notifications'] = notifications_page
        context['total_notifications'] = notifications.count()
        context['unread_count'] = self.request.user.notifications.unread().count()
        
        # Informasi halaman untuk template
        context['is_paginated'] = True
        context['page_obj'] = notifications_page
        context['paginator'] = paginator
        
        return context

@login_required
def api_unread_count(request):
    count = request.user.notifications.unread().count()
    return JsonResponse({'count': count})