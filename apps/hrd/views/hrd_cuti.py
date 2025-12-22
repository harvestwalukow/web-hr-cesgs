from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.contrib import messages
from django.http import HttpResponse
from apps.hrd.models import Cuti, TidakAmbilCuti, JatahCuti, DetailJatahCuti
from apps.hrd.utils.jatah_cuti import (
    isi_cuti_tahunan,
    kembalikan_jatah_tidak_ambil_cuti,
    rapikan_cuti_tahunan,
    validasi_cuti_dua_tahun,
    isi_cuti_tahunan_dua_tahun,
)
from apps.hrd.forms import CutiHRForm
from notifications.signals import notify
import openpyxl
from collections import defaultdict

@login_required
def approval_cuti_view(request):
    if request.user.role != 'HRD':
        messages.error(request, "Anda tidak memiliki akses ke halaman ini.")
        return redirect('karyawan_dashboard')

    daftar_cuti = Cuti.objects.filter(status='menunggu').order_by('-created_at')
    daftar_tidak_ambil = TidakAmbilCuti.objects.filter(status='menunggu').order_by('-tanggal_pengajuan')

    if request.method == 'POST':
        jenis = request.POST.get('jenis')
        aksi = request.POST.get('aksi')
        alasan_ditolak = request.POST.get('alasan_ditolak', '').strip()

        if jenis == 'cuti':
            cuti_id = request.POST.get('cuti_id')
            cuti = get_object_or_404(Cuti, id=cuti_id)

            if aksi in ['disetujui', 'ditolak']:
                cuti.status = aksi
                cuti.approval = request.user

                # Variabel untuk menyimpan informasi notifikasi
                notification_description = f"Pengajuan cuti Anda untuk tanggal {cuti.tanggal_mulai} sampai {cuti.tanggal_selesai} telah {aksi}"
                
                if aksi == 'disetujui' and cuti.jenis_cuti == 'tahunan':
                    # Tambahkan informasi detail tentang sisa cuti dan cuti yang dipotong
                    tahun_sekarang = cuti.tanggal_mulai.year
                    tahun_sebelumnya = tahun_sekarang - 1
                    
                    # Dapatkan informasi sisa cuti per tahun setelah cuti disetujui
                    jatah_cuti_list = JatahCuti.objects.filter(
                        karyawan=cuti.id_karyawan, 
                        tahun__in=[tahun_sebelumnya, tahun_sekarang]
                    ).order_by('tahun')
                    
                    # Hitung jumlah cuti yang dipotong per tahun
                    cuti_dipotong = defaultdict(int)
                    detail_cuti = DetailJatahCuti.objects.filter(
                        jatah_cuti__karyawan=cuti.id_karyawan,
                        dipakai=True,
                        keterangan__icontains=f'Cuti Tahunan: {cuti.tanggal_mulai} - {cuti.tanggal_selesai}'
                    )
                    
                    for detail in detail_cuti:
                        cuti_dipotong[detail.tahun] += 1
                    
                    # Tambahkan informasi sisa cuti per tahun
                    notification_description += "\n\n✔️ Pengajuan cuti disetujui!\n"
                    
                    # Tambahkan informasi sisa cuti per tahun
                    for jc in jatah_cuti_list:
                        notification_description += f"- Sisa cuti tahun {jc.tahun}: {jc.sisa_cuti} hari\n"
                    
                    # Tambahkan informasi cuti yang dipotong per tahun
                    if cuti_dipotong:
                        notification_description += "- Cuti dipotong:\n"
                        for tahun, jumlah in cuti_dipotong.items():
                            notification_description += f"   • Tahun {tahun}: {jumlah} hari\n"

                # Kirim notifikasi ke karyawan
                notify.send(
                    sender=request.user,
                    recipient=cuti.id_karyawan.user,
                    verb=f"cuti {aksi}",
                    description=notification_description,
                    target=cuti,
                    data={"url": "/karyawan/pengajuan-cuti/"}
                )

                if aksi == 'ditolak':
                    cuti.feedback_hr = alasan_ditolak or "Tidak ada alasan diberikan."

                file_persetujuan = request.FILES.get('file_persetujuan')
                if file_persetujuan:
                    cuti.file_persetujuan = file_persetujuan

                if aksi == 'disetujui' and cuti.jenis_cuti == 'tahunan':
                    tahun = cuti.tanggal_mulai.year
                    jumlah_hari = (cuti.tanggal_selesai - cuti.tanggal_mulai).days + 1
                    
                    # Flag untuk mencegah pengisian slot ganda
                    slot_sudah_diisi = False

                    if cuti.id_karyawan.user.role in ['HRD', 'Karyawan Tetap']:
                        # Validasi cuti dengan sistem 2 tahun (sekarang + sebelumnya)
                        is_valid, error_message, detail_sisa = validasi_cuti_dua_tahun(
                            cuti.id_karyawan, jumlah_hari, tahun
                        )
                        
                        # Hapus validasi yang menolak cuti jika saldo tidak mencukupi
                        # Hanya tampilkan pesan informasi tentang saldo cuti
                        if not is_valid:
                            messages.info(request, f"Info: Saldo cuti {cuti.id_karyawan.nama} tidak mencukupi. {error_message} Namun pengajuan tetap diproses.")
                        
                        # Isi cuti tahunan dengan sistem 2 tahun dan cek hasilnya
                        # Tambahkan parameter allow_minus=True untuk memperbolehkan saldo minus
                        if not isi_cuti_tahunan_dua_tahun(cuti.id_karyawan, cuti.tanggal_mulai, cuti.tanggal_selesai, allow_minus=True):
                            messages.info(request, f"Info: Saldo cuti {cuti.id_karyawan.nama} tidak mencukupi, namun pengajuan tetap diproses.")
                        
                        # Set flag bahwa slot sudah diisi
                        slot_sudah_diisi = True
                        
                    jatah_cuti = JatahCuti.objects.filter(karyawan=cuti.id_karyawan, tahun=tahun).first()
                    
                    # Hapus validasi yang menolak cuti jika saldo tidak mencukupi
                    # Hanya tampilkan pesan informasi tentang saldo cuti
                    if jatah_cuti and jatah_cuti.sisa_cuti < jumlah_hari:
                        messages.info(request, f"Info: Saldo cuti {cuti.id_karyawan.nama} tidak mencukupi. Sisa cuti: {jatah_cuti.sisa_cuti} hari, yang diajukan: {jumlah_hari} hari. Namun pengajuan tetap diproses.")
                    
                    # Isi cuti tahunan hanya jika belum diisi sebelumnya
                    if not slot_sudah_diisi:
                        # Tambahkan parameter allow_minus=True untuk memperbolehkan saldo minus
                        if not isi_cuti_tahunan(cuti.id_karyawan, cuti.tanggal_mulai, cuti.tanggal_selesai, allow_minus=True):
                            messages.info(request, f"Info: Saldo cuti {cuti.id_karyawan.nama} tidak mencukupi, namun pengajuan tetap diproses.")
                            return redirect('approval_cuti')

                cuti.save()
                messages.success(request, f"Pengajuan cuti berhasil {aksi}.")

        elif jenis == 'tidak_ambil':
            tidak_ambil_id = request.POST.get('tidak_ambil_id')
            data = get_object_or_404(TidakAmbilCuti, id=tidak_ambil_id)

            if aksi in ['disetujui', 'ditolak']:
                data.status = aksi
                data.approval = request.user
                
                # kirim notifikasi ke karyawan
                notify.send(
                    sender=request.user,
                    recipient=data.id_karyawan.user,
                    verb=f"tidak ambil cuti {aksi}",
                    description=f"Pengajuan tidak ambil cuti Anda untuk tanggal {data.tanggal_pengajuan} telah {aksi}",
                    target=data,
                    data={"url": "/karyawan/pengajuan-tidak-ambil-cuti/"}
                )

                if aksi == 'ditolak':
                    data.feedback_hr = alasan_ditolak or "Tidak ada alasan diberikan."

                file_persetujuan = request.FILES.get('file_persetujuan')
                if file_persetujuan:
                    data.file_persetujuan = file_persetujuan

                if aksi == 'disetujui' and data.id_karyawan.user.role in ['HRD', 'Karyawan Tetap']:
                    daftar_tanggal = data.tanggal.all()
                    # Kembalikan jatah cuti
                    kembalikan_jatah_tidak_ambil_cuti(data.id_karyawan, daftar_tanggal)
                    
                    rapikan_cuti_tahunan(data.id_karyawan, tahun=daftar_tanggal.first().tanggal.year)

                data.save()
                messages.success(request, f"Pengajuan tidak ambil cuti berhasil {aksi}.")

        return redirect('approval_cuti')

    # Filter parameters
    keyword = request.GET.get('nama')
    tahun = request.GET.get('tahun')
    status = request.GET.get('status')
    tanggal_mulai = request.GET.get('tanggal_mulai')
    tanggal_selesai = request.GET.get('tanggal_selesai')
    
    # Filter riwayat cuti
    riwayat_cuti_list = Cuti.objects.exclude(status='menunggu')
    
    if keyword:
        riwayat_cuti_list = riwayat_cuti_list.filter(id_karyawan__nama__icontains=keyword)
    if tahun:
        riwayat_cuti_list = riwayat_cuti_list.filter(tanggal_mulai__year=tahun)
    if status:
        riwayat_cuti_list = riwayat_cuti_list.filter(status=status)
    if tanggal_mulai:
        riwayat_cuti_list = riwayat_cuti_list.filter(tanggal_mulai__gte=tanggal_mulai)
    if tanggal_selesai:
        riwayat_cuti_list = riwayat_cuti_list.filter(tanggal_selesai__lte=tanggal_selesai)
    
    riwayat_cuti_list = riwayat_cuti_list.order_by('-created_at')
    
    # Filter riwayat tidak ambil cuti
    riwayat_tidak_ambil_list = TidakAmbilCuti.objects.exclude(status='menunggu')
    
    if keyword:
        riwayat_tidak_ambil_list = riwayat_tidak_ambil_list.filter(id_karyawan__nama__icontains=keyword)
    if tahun:
        riwayat_tidak_ambil_list = riwayat_tidak_ambil_list.filter(tanggal_pengajuan__year=tahun)
    if status:
        riwayat_tidak_ambil_list = riwayat_tidak_ambil_list.filter(status=status)
    if tanggal_mulai:
        riwayat_tidak_ambil_list = riwayat_tidak_ambil_list.filter(tanggal_pengajuan__gte=tanggal_mulai)
    if tanggal_selesai:
        riwayat_tidak_ambil_list = riwayat_tidak_ambil_list.filter(tanggal_pengajuan__lte=tanggal_selesai)
    
    riwayat_tidak_ambil_list = riwayat_tidak_ambil_list.order_by('-tanggal_pengajuan')
    
    # Implementasi paginasi
    paginator_cuti = Paginator(riwayat_cuti_list, 10)
    paginator_tidak_ambil = Paginator(riwayat_tidak_ambil_list, 10)
    
    page_number = request.GET.get('page')
    riwayat_cuti = paginator_cuti.get_page(page_number)
    riwayat_tidak_ambil = paginator_tidak_ambil.get_page(page_number)

    return render(request, 'hrd/approval_cuti.html', {
        'daftar_cuti': daftar_cuti,
        'daftar_tidak_ambil': daftar_tidak_ambil,
        'riwayat_cuti': riwayat_cuti,
        'riwayat_tidak_ambil': riwayat_tidak_ambil,
    })


@login_required
def tambah_cuti_hr(request):
    """HR membuat cuti baru untuk karyawan tertentu."""
    if request.user.role != 'HRD':
        messages.error(request, "Anda tidak memiliki akses ke halaman ini.")
        return redirect('karyawan_dashboard')

    # Bisa pre-select karyawan lewat querystring ?karyawan_id=...
    initial = {}
    karyawan_id = request.GET.get('karyawan_id')
    if karyawan_id:
        initial['id_karyawan'] = karyawan_id

    if request.method == 'POST':
        form = CutiHRForm(request.POST, request.FILES)
        if form.is_valid():
            cuti = form.save(commit=False)
            # Karena dibuat oleh HR, langsung dianggap disetujui
            cuti.status = 'disetujui'
            cuti.approval = request.user
            cuti.save()
            
            # Jika cuti tahunan, potong jatah cuti
            if cuti.jenis_cuti == 'tahunan':
                tahun = cuti.tanggal_mulai.year
                jumlah_hari = (cuti.tanggal_selesai - cuti.tanggal_mulai).days + 1
                
                # Check role for quota system
                if cuti.id_karyawan.user.role in ['HRD', 'Karyawan Tetap']:
                    # Use two-year quota system
                    is_valid, error_message, detail_sisa = validasi_cuti_dua_tahun(
                        cuti.id_karyawan, jumlah_hari, tahun
                    )
                    
                    if not is_valid:
                        messages.info(request, f"Info: Saldo cuti {cuti.id_karyawan.nama} tidak mencukupi. {error_message} Namun cuti tetap dibuat.")
                    
                    # Deduct quota using two-year system (allow_minus=True)
                    if not isi_cuti_tahunan_dua_tahun(cuti.id_karyawan, cuti.tanggal_mulai, cuti.tanggal_selesai, allow_minus=True):
                        messages.info(request, f"Info: Saldo cuti {cuti.id_karyawan.nama} tidak mencukupi, namun cuti tetap dibuat.")
                else:
                    # Use single-year quota system
                    jatah_cuti = JatahCuti.objects.filter(karyawan=cuti.id_karyawan, tahun=tahun).first()
                    
                    if jatah_cuti and jatah_cuti.sisa_cuti < jumlah_hari:
                        messages.info(request, f"Info: Saldo cuti {cuti.id_karyawan.nama} tidak mencukupi. Sisa cuti: {jatah_cuti.sisa_cuti} hari, yang dibuat: {jumlah_hari} hari. Namun cuti tetap dibuat.")
                    
                    # Deduct quota (allow_minus=True)
                    if not isi_cuti_tahunan(cuti.id_karyawan, cuti.tanggal_mulai, cuti.tanggal_selesai, allow_minus=True):
                        messages.info(request, f"Info: Saldo cuti {cuti.id_karyawan.nama} tidak mencukupi, namun cuti tetap dibuat.")
            
            messages.success(request, "Cuti karyawan berhasil dibuat dan disetujui.")
            return redirect('approval_cuti')
    else:
        form = CutiHRForm(initial=initial)

    return render(request, 'hrd/cuti_hr_form.html', {
        'form': form,
        'mode': 'tambah',
    })


@login_required
def edit_cuti_hr(request, cuti_id):
    """HR mengedit data cuti karyawan tertentu dari halaman approval/riwayat."""
    if request.user.role != 'HRD':
        messages.error(request, "Anda tidak memiliki akses ke halaman ini.")
        return redirect('karyawan_dashboard')

    cuti = get_object_or_404(Cuti, id=cuti_id)

    if request.method == 'POST':
        form = CutiHRForm(request.POST, request.FILES, instance=cuti)
        if form.is_valid():
            form.save()
            messages.success(request, "Data cuti karyawan berhasil diperbarui.")
            return redirect('approval_cuti')
    else:
        form = CutiHRForm(instance=cuti)

    return render(request, 'hrd/cuti_hr_form.html', {
        'form': form,
        'mode': 'edit',
        'cuti': cuti,
    })

@login_required
def export_riwayat_cuti_excel(request):
    if request.user.role != 'HRD':
        return HttpResponse("Forbidden", status=403)

    # Ambil parameter tab untuk menentukan jenis export
    tab = request.GET.get('tab', 'cuti')  # default ke cuti
    
    # Filter parameters
    keyword = request.GET.get('nama')
    tahun = request.GET.get('tahun')
    status = request.GET.get('status')
    tanggal_mulai = request.GET.get('tanggal_mulai')
    tanggal_selesai = request.GET.get('tanggal_selesai')

    wb = openpyxl.Workbook()
    ws = wb.active
    
    if tab == 'tidak_ambil':
        # Export riwayat tidak ambil cuti
        ws.title = "Riwayat Tidak Ambil Cuti"
        
        riwayat = TidakAmbilCuti.objects.exclude(status='menunggu').order_by('-tanggal_pengajuan')
        
        if keyword:
            riwayat = riwayat.filter(id_karyawan__nama__icontains=keyword)
        if tahun:
            riwayat = riwayat.filter(tanggal_pengajuan__year=tahun)
        if status:
            riwayat = riwayat.filter(status=status)
        if tanggal_mulai:
            riwayat = riwayat.filter(tanggal_pengajuan__gte=tanggal_mulai)
        if tanggal_selesai:
            riwayat = riwayat.filter(tanggal_pengajuan__lte=tanggal_selesai)

        ws.append(["Nama", "Tanggal Pengajuan", "Tanggal Cuti Bersama", "Alasan", "Scenario", "Status", "Disetujui Oleh"])

        for r in riwayat:
            tanggal_cuti_str = ", ".join([f"{t.tanggal.strftime('%Y-%m-%d')} ({t.keterangan})" for t in r.tanggal.all()])
            ws.append([
                r.id_karyawan.nama,
                r.tanggal_pengajuan.strftime('%Y-%m-%d'),
                tanggal_cuti_str,
                r.alasan,
                r.get_scenario_display() if r.scenario else '-',
                r.status,
                r.approval.get_full_name() if r.approval else '-'
            ])
        
        filename = 'riwayat_tidak_ambil_cuti.xlsx'
    else:
        # Export riwayat cuti (default)
        ws.title = "Riwayat Cuti"
        
        riwayat = Cuti.objects.exclude(status='menunggu').order_by('-created_at')

        if keyword:
            riwayat = riwayat.filter(id_karyawan__nama__icontains=keyword)
        if tahun:
            riwayat = riwayat.filter(tanggal_mulai__year=tahun)
        if status:
            riwayat = riwayat.filter(status=status)
        if tanggal_mulai:
            riwayat = riwayat.filter(tanggal_mulai__gte=tanggal_mulai)
        if tanggal_selesai:
            riwayat = riwayat.filter(tanggal_selesai__lte=tanggal_selesai)

        ws.append(["Nama", "Jenis Cuti", "Tanggal Mulai", "Tanggal Selesai", "Status", "Disetujui Oleh"])

        for r in riwayat:
            ws.append([
                r.id_karyawan.nama,
                r.get_jenis_cuti_display(),
                r.tanggal_mulai.strftime('%Y-%m-%d'),
                r.tanggal_selesai.strftime('%Y-%m-%d'),
                r.status,
                r.approval.get_full_name() if r.approval else '-'
            ])
        
        filename = 'riwayat_cuti.xlsx'

    response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = f'attachment; filename={filename}'
    wb.save(response)
    return response


@login_required
def hapus_cuti(request, cuti_id):
    """HR menghapus data cuti karyawan."""
    if request.user.role != 'HRD':
        messages.error(request, "Anda tidak memiliki akses ke halaman ini.")
        return redirect('karyawan_dashboard')
    
    cuti = get_object_or_404(Cuti, id=cuti_id)
    nama_karyawan = cuti.id_karyawan.nama
    tanggal_cuti = f"{cuti.tanggal_mulai} s.d. {cuti.tanggal_selesai}"
    
    # Hapus file terkait jika ada
    if cuti.file_pengajuan:
        cuti.file_pengajuan.delete()
    if cuti.file_persetujuan:
        cuti.file_persetujuan.delete()
    if cuti.file_dokumen_formal:
        cuti.file_dokumen_formal.delete()
    
    cuti.delete()
    messages.success(request, f"Data cuti {nama_karyawan} ({tanggal_cuti}) berhasil dihapus.")
    return redirect('approval_cuti')


@login_required
def hapus_tidak_ambil_cuti(request, tidak_ambil_id):
    """HR menghapus data tidak ambil cuti bersama."""
    if request.user.role != 'HRD':
        messages.error(request, "Anda tidak memiliki akses ke halaman ini.")
        return redirect('karyawan_dashboard')
    
    tidak_ambil = get_object_or_404(TidakAmbilCuti, id=tidak_ambil_id)
    nama_karyawan = tidak_ambil.id_karyawan.nama
    
    # Hapus file terkait jika ada
    if tidak_ambil.file_pengajuan:
        tidak_ambil.file_pengajuan.delete()
    if tidak_ambil.file_persetujuan:
        tidak_ambil.file_persetujuan.delete()
    
    tidak_ambil.delete()
    messages.success(request, f"Data tidak ambil cuti {nama_karyawan} berhasil dihapus.")
    return redirect('approval_cuti')
