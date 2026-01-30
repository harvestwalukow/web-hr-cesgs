from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.core.exceptions import PermissionDenied
from django.db.models import Q
from datetime import datetime, date, timedelta
import json

from apps.hrd.models import BookingRuangRapat, RuangRapat, Karyawan
from apps.hrd.forms import BookingRuangRapatForm

def role_required(allowed_roles):
    """Decorator untuk membatasi akses berdasarkan role"""
    def decorator(view_func):
        def wrapper(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect('login')
            if request.user.role not in allowed_roles:
                raise PermissionDenied("Anda tidak memiliki akses ke halaman ini")
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator

@login_required
@role_required(['HRD', 'Karyawan Tetap'])
def booking_ruang_rapat_view(request):
    """Halaman utama booking ruang rapat dengan kalender"""
    # Get filter parameters
    selected_date = request.GET.get('date', date.today().strftime('%Y-%m-%d'))
    selected_room = request.GET.get('room', '')
    
    try:
        selected_date_obj = datetime.strptime(selected_date, '%Y-%m-%d').date()
    except ValueError:
        selected_date_obj = date.today()
        selected_date = selected_date_obj.strftime('%Y-%m-%d')
    
    # Get all active rooms
    ruang_rapat_list = RuangRapat.objects.filter(aktif=True)
    
    # Get bookings for the week
    start_of_week = selected_date_obj - timedelta(days=selected_date_obj.weekday())
    end_of_week = start_of_week + timedelta(days=6)
    
    bookings_query = BookingRuangRapat.objects.filter(
        tanggal__range=[start_of_week, end_of_week]
    ).select_related('user', 'ruang_rapat', 'user__karyawan')
    
    if selected_room:
        bookings_query = bookings_query.filter(ruang_rapat_id=selected_room)
    
    bookings = bookings_query.order_by('tanggal', 'waktu_mulai')
    
    # Format bookings for calendar
    calendar_events = []
    for booking in bookings:
        # Get user name from Karyawan model if exists, otherwise fallback to User
        try:
            user_name = booking.user.karyawan.nama
        except Karyawan.DoesNotExist:
            user_name = booking.user.get_full_name() or booking.user.username
            
        calendar_events.append({
            'id': booking.id,
            'title': booking.judul,
            'start': f"{booking.tanggal}T{booking.waktu_mulai}+07:00",
            'end': f"{booking.tanggal}T{booking.waktu_selesai}+07:00",
            'backgroundColor': booking.ruang_rapat.warna_kalender,
            'borderColor': booking.ruang_rapat.warna_kalender,
            'extendedProps': {
                'room': booking.ruang_rapat.nama,
                'description': booking.deskripsi or '',
                'user': user_name,
                'canEdit': booking.user == request.user
            }
        })
    
    context = {
        'ruang_rapat_list': ruang_rapat_list,
        'selected_date': selected_date,
        'selected_room': selected_room,
        'calendar_events': json.dumps(calendar_events),
        'user_bookings': BookingRuangRapat.objects.filter(user=request.user).order_by('-tanggal', '-waktu_mulai')[:10],
        # Tambahan agar template tidak error
        'today_bookings': BookingRuangRapat.objects.filter(tanggal=date.today()),
        'today': date.today(),
    }
    return render(request, 'hrd/booking_ruang_rapat.html', context)

@login_required
@role_required(['HRD', 'Karyawan Tetap'])
def booking_calendar_events(request):
    """JSON feed untuk FullCalendar: muat events pada rentang tanggal."""
    start = request.GET.get('start')
    end = request.GET.get('end')
    room = request.GET.get('room')

    try:
        start_date = datetime.fromisoformat(start).date()
        end_date = datetime.fromisoformat(end).date()
    except (TypeError, ValueError):
        start_date = date.today() - timedelta(days=30)
        end_date = date.today() + timedelta(days=90)

    qs = BookingRuangRapat.objects.filter(
        tanggal__range=[start_date, end_date]
    ).select_related('user', 'ruang_rapat', 'user__karyawan')

    if room:
        qs = qs.filter(ruang_rapat_id=room)

    events = []
    for booking in qs.order_by('tanggal', 'waktu_mulai'):
        try:
            user_name = booking.user.karyawan.nama
        except Karyawan.DoesNotExist:
            user_name = booking.user.get_full_name() or booking.user.username

        events.append({
            'id': booking.id,
            'title': booking.judul,
            'start': f"{booking.tanggal}T{booking.waktu_mulai}+07:00",
            'end': f"{booking.tanggal}T{booking.waktu_selesai}+07:00",
            'backgroundColor': booking.ruang_rapat.warna_kalender,
            'borderColor': booking.ruang_rapat.warna_kalender,
            'extendedProps': {
                'room': booking.ruang_rapat.nama,
                'description': booking.deskripsi or '',
                'user': user_name,
                'canEdit': booking.user == request.user
            }
        })
    return JsonResponse(events, safe=False)

@login_required
@role_required(['HRD', 'Karyawan Tetap'])
def create_booking(request):
    """Create new booking"""
    if request.method == 'POST':
        form = BookingRuangRapatForm(request.POST)
        if form.is_valid():
            booking = form.save(commit=False)
            booking.user = request.user
            booking.save()
            messages.success(request, f'Booking "{booking.judul}" berhasil dibuat!')
            return redirect('booking_ruang_rapat')
        else:
            messages.error(request, 'Terjadi kesalahan dalam form. Silakan periksa kembali.')
    else:
        form = BookingRuangRapatForm()
        
        # Pre-fill form jika ada parameter
        if request.GET.get('date'):
            form.fields['tanggal'].initial = request.GET.get('date')
        if request.GET.get('room'):
            form.fields['ruang_rapat'].initial = request.GET.get('room')
        if request.GET.get('time'):
            form.fields['waktu_mulai'].initial = request.GET.get('time')
    
    return render(request, 'hrd/booking_form.html', {
        'form': form,
        'title': 'Buat Booking Baru',
        'action': 'create'
    })

@login_required
@role_required(['HRD', 'Karyawan Tetap'])
def edit_booking(request, booking_id):
    """Edit existing booking - only owner can edit"""
    booking = get_object_or_404(BookingRuangRapat, id=booking_id)
    
    # Check ownership
    if booking.user != request.user:
        messages.error(request, 'Anda hanya dapat mengedit booking milik sendiri.')
        return redirect('booking_ruang_rapat')
    
    if request.method == 'POST':
        form = BookingRuangRapatForm(request.POST, instance=booking)
        if form.is_valid():
            form.save()
            messages.success(request, f'Booking "{booking.judul}" berhasil diupdate!')
            return redirect('booking_ruang_rapat')
        else:
            messages.error(request, 'Terjadi kesalahan dalam form. Silakan periksa kembali.')
    else:
        form = BookingRuangRapatForm(instance=booking)
    
    return render(request, 'hrd/booking_form.html', {
        'form': form,
        'booking': booking,
        'title': f'Edit Booking: {booking.judul}',
        'action': 'edit'
    })

@login_required
@role_required(['HRD', 'Karyawan Tetap'])
@require_POST
def delete_booking(request, booking_id):
    """Delete booking - only owner can delete"""
    booking = get_object_or_404(BookingRuangRapat, id=booking_id)
    
    # Check ownership
    if booking.user != request.user:
        return JsonResponse({
            'success': False,
            'message': 'Anda hanya dapat menghapus booking milik sendiri.'
        })
    
    booking_title = booking.judul
    booking.delete()
    
    return JsonResponse({
        'success': True,
        'message': f'Booking "{booking_title}" berhasil dihapus!'
    })

@login_required
@role_required(['HRD', 'Karyawan Tetap'])
def get_booking_detail(request, booking_id):
    """Get booking detail for modal"""
    booking = get_object_or_404(BookingRuangRapat.objects.select_related('user', 'user__karyawan', 'ruang_rapat'), id=booking_id)
    
    # Get user name from Karyawan model if exists, otherwise fallback to User
    try:
        user_name = booking.user.karyawan.nama
    except Karyawan.DoesNotExist:
        user_name = booking.user.get_full_name() or booking.user.username
    
    return JsonResponse({
        'id': booking.id,
        'judul': booking.judul,
        'deskripsi': booking.deskripsi or '',
        'ruang_rapat': booking.ruang_rapat.nama,
        'tanggal': booking.tanggal.strftime('%d %B %Y'),
        'waktu_mulai': booking.waktu_mulai.strftime('%H:%M'),
        'waktu_selesai': booking.waktu_selesai.strftime('%H:%M'),
        'user': user_name,
        'durasi': f'{booking.durasi_jam:.1f} jam',
        'can_edit': booking.user == request.user,
        'created_at': booking.created_at.strftime('%d %B %Y %H:%M')
    })

@login_required
@role_required(['HRD', 'Karyawan Tetap'])
def check_availability(request):
    """Check room availability for given time slot"""
    room_id = request.GET.get('room_id')
    tanggal = request.GET.get('tanggal')
    waktu_mulai = request.GET.get('waktu_mulai')
    waktu_selesai = request.GET.get('waktu_selesai')
    exclude_id = request.GET.get('exclude_id')  # For edit mode
    
    if not all([room_id, tanggal, waktu_mulai, waktu_selesai]):
        return JsonResponse({'available': False, 'message': 'Parameter tidak lengkap'})
    
    try:
        from datetime import datetime
        tanggal_obj = datetime.strptime(tanggal, '%Y-%m-%d').date()
        waktu_mulai_obj = datetime.strptime(waktu_mulai, '%H:%M').time()
        waktu_selesai_obj = datetime.strptime(waktu_selesai, '%H:%M').time()
    except ValueError:
        return JsonResponse({'available': False, 'message': 'Format tanggal/waktu tidak valid'})
    
    # Check for overlapping bookings
    overlapping_bookings = BookingRuangRapat.objects.filter(
        ruang_rapat_id=room_id,
        tanggal=tanggal_obj,
        waktu_mulai__lt=waktu_selesai_obj,
        waktu_selesai__gt=waktu_mulai_obj
    )
    
    if exclude_id:
        overlapping_bookings = overlapping_bookings.exclude(id=exclude_id)
    
    if overlapping_bookings.exists():
        booking = overlapping_bookings.first()
        return JsonResponse({
            'available': False,
            'message': f'Bertabrakan dengan "{booking.judul}" ({booking.waktu_mulai.strftime("%H:%M")} - {booking.waktu_selesai.strftime("%H:%M")})'
        })
    
    return JsonResponse({'available': True, 'message': 'Waktu tersedia'})