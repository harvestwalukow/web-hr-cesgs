from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.contrib import messages
from django.utils import timezone
from apps.hrd.models import TidakAmbilCuti, Karyawan, CutiBersama, DetailJatahCuti
from apps.karyawan.forms import TidakAmbilCutiForm
from datetime import datetime
from django.db.models import Q
from notifications.signals import notify
from apps.authentication.models import User
from datetime import timedelta
from requests import request

@login_required
def tidak_ambil_cuti_view(request):
    karyawan = get_object_or_404(Karyawan, user=request.user)

    # Ambil tahun saat ini
    tahun_sekarang = datetime.now().year
    today = timezone.now().date()

    # Ambil semua tanggal cuti bersama (hanya jenis 'Cuti Bersama') untuk tahun ini
    semua_cuti_bersama = CutiBersama.objects.filter(tanggal__year=tahun_sekarang, jenis='Cuti Bersama')

    # Ambil semua pengajuan yang sudah ada untuk karyawan ini
    pengajuan_existing = TidakAmbilCuti.objects.filter(
        id_karyawan=karyawan
    ).prefetch_related('tanggal')

    # Buat mapping status pengajuan per tanggal
    status_pengajuan = {}
    for pengajuan in pengajuan_existing:
        for tanggal_cuti in pengajuan.tanggal.all():
            if tanggal_cuti.id not in status_pengajuan:
                status_pengajuan[tanggal_cuti.id] = []
            status_pengajuan[tanggal_cuti.id].append({
                'id': pengajuan.id,
                'status': pengajuan.status,
                'tanggal_pengajuan': pengajuan.tanggal_pengajuan,
                'scenario': pengajuan.scenario,
                'feedback_hr': pengajuan.feedback_hr
            })

    # Semua tanggal tetap ditampilkan (tidak ada filter exclude)
    sisa_tanggal = semua_cuti_bersama
    
    # Kategorikan tanggal berdasarkan scenario dan status existing
    scenario_info = {}
    for tanggal_cuti in sisa_tanggal:
        h_minus_1 = tanggal_cuti.tanggal - timedelta(days=1)
        
        # PERBAIKAN: Cek di database apakah jatah cuti benar-benar sudah dipotong
        # Jangan hanya mengandalkan perbandingan tanggal
        sudah_dipotong_di_db = DetailJatahCuti.objects.filter(
            jatah_cuti__karyawan=karyawan,
            jatah_cuti__tahun=tanggal_cuti.tanggal.year,
            dipakai=True,
        ).filter(
            Q(tanggal_terpakai=tanggal_cuti.tanggal)
            | Q(keterangan__icontains=f'Cuti Bersama: {tanggal_cuti.keterangan or tanggal_cuti.tanggal}')
        ).exists()
        
        # Info dasar scenario berdasarkan status aktual di database
        if sudah_dipotong_di_db:
            base_scenario = 'claim_back'
            base_description = 'Cuti sudah terpotong - bisa di-claim kembali'
        elif today > h_minus_1:
            # Sudah lewat H-1 tapi belum terpotong di DB (mungkin cron tidak jalan atau baru dibuat)
            # Tetap bisa dicegah jika belum terpotong
            base_scenario = 'prevent_cut'
            base_description = 'Cuti belum terpotong - bisa dicegah pemotongan (sudah lewat H-1)'
        else:  # Belum H-1, belum terpotong
            base_scenario = 'prevent_cut'
            base_description = 'Cuti belum terpotong - bisa dicegah pemotongan'
        
        # Cek status pengajuan existing
        existing_status = status_pengajuan.get(tanggal_cuti.id, [])
        can_apply = True
        status_text = ""
        
        if existing_status:
            # Ambil status terbaru (yang terakhir diajukan)
            latest = max(existing_status, key=lambda x: x['tanggal_pengajuan'])
            
            if latest['status'] == 'disetujui':
                status_text = "✅ Sudah Disetujui"
                can_apply = False  # Tidak bisa apply lagi jika sudah disetujui
            elif latest['status'] == 'menunggu':
                status_text = "⏳ Menunggu Persetujuan"
                can_apply = False  # Tidak bisa apply lagi jika masih menunggu
            elif latest['status'] == 'ditolak':
                status_text = "❌ Ditolak - Bisa Ajukan Ulang"
                can_apply = True
        
        scenario_info[tanggal_cuti.id] = {
            'scenario': base_scenario,
            'description': base_description,
            'status_text': status_text,
            'can_apply': can_apply,
            'existing_status': existing_status
        }
    
    # paginasi tabel pengajuan - gunakan semua tanggal
    paginator = Paginator(sisa_tanggal, 10)
    page_number = request.GET.get('page')
    riwayat = paginator.get_page(page_number) 
    
    # Form khusus untuk pilihan tanggal - hanya tampilkan yang bisa diapply
    available_dates = []
    for t in sisa_tanggal:
        if scenario_info[t.id]['can_apply']:
            available_dates.append(t)
    
    if request.method == 'POST':
        form = TidakAmbilCutiForm(request.POST, request.FILES)
        # Set queryset untuk form dengan available dates
        form.fields['tanggal'].queryset = CutiBersama.objects.filter(
            id__in=[d.id for d in available_dates]
        )
        if form.is_valid():
            tidak_ambil = form.save(commit=False)
            tidak_ambil.id_karyawan = karyawan

            if hasattr(tidak_ambil, 'jenis_pengajuan'):
                tidak_ambil.jenis_pengajuan = 'tidak_ambil_cuti'
            
            # Tentukan scenario berdasarkan tanggal yang dipilih
            selected_dates = form.cleaned_data['tanggal']
            scenarios = [scenario_info[t.id]['scenario'] for t in selected_dates]
            
            # Jika semua tanggal memiliki scenario yang sama
            if len(set(scenarios)) == 1:
                tidak_ambil.scenario = scenarios[0]
            else:
                # Jika mixed, prioritaskan claim_back
                tidak_ambil.scenario = 'claim_back' if 'claim_back' in scenarios else 'prevent_cut'
            
            tidak_ambil.save()
            form.save_m2m()
            
            # Process jatah cuti adjustment jika disetujui langsung atau perlu approval
            if tidak_ambil.scenario == 'claim_back':
                # Untuk scenario claim back, bisa langsung proses atau tunggu approval
                process_cuti_adjustment(tidak_ambil, karyawan)
            
            # Kirim notifikasi ke HRD
            hr_users = User.objects.filter(role='HRD')
            notify.send(
                sender=request.user,
                recipient=hr_users,
                verb="mengajukan tidak ambil cuti",
                description=f"{karyawan.nama} mengajukan tidak ambil cuti bersama ({tidak_ambil.get_scenario_display()})",
                target=tidak_ambil,
                data={"url": "/hrd/approval-cuti/"}
            )
            
            messages.success(request, "Pengajuan berhasil dikirim.")
            return redirect('tidak_ambil_cuti')
    else:
        form = TidakAmbilCutiForm()
        # Set queryset untuk form dengan available dates
        form.fields['tanggal'].queryset = CutiBersama.objects.filter(
            id__in=[d.id for d in available_dates]
        )

    riwayat_pengajuan = TidakAmbilCuti.objects.filter(id_karyawan=karyawan).order_by('-tanggal_pengajuan')
    return render(request, 'karyawan/tidak_ambil_cuti.html', {
        'form': form,
        'riwayat': riwayat_pengajuan,
        'semua_tanggal': sisa_tanggal,
        'available_dates': available_dates,
        'tahun_sekarang': tahun_sekarang,
        'scenario_info': scenario_info,
    })

def process_cuti_adjustment(tidak_ambil_cuti, karyawan):
    """
    Process adjustment jatah cuti berdasarkan scenario
    """
    if tidak_ambil_cuti.scenario == 'claim_back' and tidak_ambil_cuti.status == 'disetujui':
        # Scenario 1: Kembalikan jatah cuti yang sudah terpotong
        from django.core.management import call_command
        
        # Panggil command untuk process claim back
        call_command('process_claim_back')
        
        messages.success(
            request if 'request' in locals() else None,
            f"Jatah cuti berhasil dikembalikan untuk {karyawan.nama}"
        )
        
    elif tidak_ambil_cuti.scenario == 'prevent_cut':
        # Scenario 2: Akan dihandle oleh scheduled task
        print(f"⏳ Prevention scheduled for {karyawan.nama}")
        pass

@login_required
def hapus_tidak_ambil_cuti_view(request, id):
    karyawan = get_object_or_404(Karyawan, user=request.user)
    pengajuan = get_object_or_404(TidakAmbilCuti, id=id, id_karyawan=karyawan)

    if pengajuan.status == 'menunggu':
        pengajuan.delete()
        messages.success(request, "Pengajuan berhasil dihapus.")
    else:
        messages.warning(request, "Pengajuan yang sudah diproses tidak dapat dihapus.")

    return redirect('tidak_ambil_cuti')
