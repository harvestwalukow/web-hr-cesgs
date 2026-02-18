from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.shortcuts import render, redirect
from apps.hrd.models import CutiBersama, Karyawan, TidakAmbilCuti, DetailJatahCuti
from apps.hrd.forms import CutiBersamaForm
from apps.hrd.utils.jatah_cuti import hitung_jatah_cuti, potong_jatah_cuti_h_minus_1, backfill_potong_cuti_bersama
from datetime import datetime, timedelta
from django.http import JsonResponse, HttpResponseForbidden
from django.utils.dateparse import parse_date
from django.views.decorators.http import require_http_methods

@login_required
def input_cuti_bersama_view(request):
    if request.GET.get("hapus_id"):
        try:
            cuti_dihapus = CutiBersama.objects.get(id=request.GET.get("hapus_id"))
            tahun = cuti_dihapus.tanggal.year
            
            # Simpan referensi sebelum menghapus
            tanggal_dihapus = cuti_dihapus.tanggal
            keterangan_dihapus = cuti_dihapus.keterangan
            
            # Hapus cuti bersama
            cuti_dihapus.delete()

            # Proses jatah cuti hanya jika yang dihapus adalah jenis 'Cuti Bersama'
            if cuti_dihapus.jenis != 'Cuti Bersama':
                messages.success(request, f"{cuti_dihapus.jenis} tanggal {tanggal_dihapus} berhasil dihapus.")
                return redirect('input_cuti_bersama')
            semua_karyawan = Karyawan.objects.all()
            for karyawan in semua_karyawan:
                if karyawan.user.role in ['HRD', 'Karyawan Tetap']:
                    sudah_ajukan = TidakAmbilCuti.objects.filter(
                        id_karyawan=karyawan,
                        status='disetujui',
                        tanggal__tanggal=tanggal_dihapus
                    ).exists()

                    if not sudah_ajukan:
                        # Cari detail jatah cuti yang terkait dengan cuti bersama ini
                        detail_list = DetailJatahCuti.objects.filter(
                            jatah_cuti__karyawan=karyawan,
                            jatah_cuti__tahun=tahun,
                            dipakai=True,
                            keterangan__contains=f'Cuti Bersama: {keterangan_dihapus or tanggal_dihapus}'
                        )
                        
                        # Jika ditemukan, tandai sebagai tidak dipakai
                        if detail_list.exists():
                            for detail in detail_list:
                                detail.dipakai = False
                                detail.jumlah_hari = 0
                                detail.keterangan = f'Dikembalikan: {keterangan_dihapus or tanggal_dihapus} (dihapus)'
                                detail.save()
                                
                                # Tambah sisa cuti
                                jatah_cuti = detail.jatah_cuti
                                jatah_cuti.sisa_cuti += 1
                                jatah_cuti.save()
                        else:
                            hitung_jatah_cuti(karyawan, tahun, isi_detail_cuti_bersama=False)

            messages.success(request, f"Cuti bersama {tanggal_dihapus} berhasil dihapus dan jatah cuti dikembalikan.")
            return redirect('input_cuti_bersama')
        except CutiBersama.DoesNotExist:
            messages.error(request, "Data tidak ditemukan.")

    # Tambah cuti bersama
    if request.method == 'POST':
        form = CutiBersamaForm(request.POST)
        if form.is_valid():
            cuti_bersama = form.save()
            
            # Cek apakah tanggal cuti bersama adalah besok
            besok = datetime.now().date() + timedelta(days=1)
            
            if cuti_bersama.jenis == 'Cuti Bersama':
                if cuti_bersama.tanggal == besok:
                    # Jika cuti bersama adalah besok, langsung potong jatah cuti
                    potong_jatah_cuti_h_minus_1()
                    messages.success(request, f"Cuti bersama tanggal {cuti_bersama.tanggal} berhasil ditambahkan dan jatah cuti langsung dipotong (H-1).")
                else:
                    # Jika bukan besok, jatah cuti akan dipotong otomatis oleh cron job H-1
                    messages.success(request, f"Cuti bersama tanggal {cuti_bersama.tanggal} berhasil ditambahkan. Jatah cuti akan dipotong otomatis H-1.")
            else:
                # Untuk WFA, tidak ada pemotongan cuti
                messages.success(request, f"{cuti_bersama.jenis} tanggal {cuti_bersama.tanggal} berhasil ditambahkan.")
            
            return redirect('input_cuti_bersama')
    else:
        form = CutiBersamaForm()

    # Urutkan berdasarkan tanggal dari yang paling awal (ascending)
    daftar_cuti_bersama = CutiBersama.objects.all().order_by('tanggal')
    return render(request, 'hrd/input_cuti_bersama.html', {
        'form': form,
        'daftar_cuti_bersama': daftar_cuti_bersama
    })


@login_required
@require_http_methods(["GET", "POST"])
def backfill_cuti_bersama_view(request):
    """
    Endpoint web untuk menjalankan backfill cuti bersama tanpa akses terminal.
    
    GET:
      - tanpa action: mengembalikan instruksi singkat
      - action=dry-run: menjalankan simulasi backfill dan mengembalikan JSON summary
    POST:
      - action=run: menjalankan backfill (menulis DB) dan mengembalikan JSON summary
        (wajib confirm=RUN untuk safety)
    """
    # Batasi hanya HRD / superuser
    if not getattr(request.user, "is_superuser", False) and getattr(request.user, "role", None) != "HRD":
        return HttpResponseForbidden("Forbidden")

    action = (request.POST.get("action") or request.GET.get("action") or "").strip().lower()
    tahun_raw = request.POST.get("tahun") or request.GET.get("tahun") or str(datetime.now().year)
    sampai_raw = request.POST.get("sampai") or request.GET.get("sampai")
    karyawan_ids_raw = request.POST.get("karyawan_ids") or request.GET.get("karyawan_ids")  # comma-separated

    try:
        tahun = int(tahun_raw)
    except ValueError:
        return JsonResponse({"error": f"Invalid tahun: {tahun_raw}"}, status=400)

    sampai_tanggal = None
    if sampai_raw:
        sampai_tanggal = parse_date(sampai_raw)
        if not sampai_tanggal:
            return JsonResponse({"error": f"Invalid sampai date: {sampai_raw} (use YYYY-MM-DD)"}, status=400)

    karyawan_ids = None
    if karyawan_ids_raw:
        try:
            karyawan_ids = [int(x.strip()) for x in karyawan_ids_raw.split(",") if x.strip()]
        except ValueError:
            return JsonResponse({"error": f"Invalid karyawan_ids: {karyawan_ids_raw} (use comma-separated ints)"}, status=400)

    if request.method == "GET" and action not in ("dry-run", "dryrun"):
        return JsonResponse(
            {
                "ok": True,
                "message": "Use ?action=dry-run&tahun=2026[&sampai=YYYY-MM-DD][&karyawan_ids=1,2] to simulate. Use POST action=run&tahun=...&confirm=RUN to execute.",
                "examples": {
                    "dry_run": "/hrd/backfill-cuti-bersama/?action=dry-run&tahun=2026",
                },
            }
        )

    if request.method == "GET":
        dry_run = True
    else:
        # POST
        if action != "run":
            return JsonResponse({"error": "POST requires action=run"}, status=400)
        if (request.POST.get("confirm") or "").strip().upper() != "RUN":
            return JsonResponse({"error": "Missing/invalid confirm. Send confirm=RUN to execute."}, status=400)
        dry_run = False

    summary = backfill_potong_cuti_bersama(
        tahun=tahun,
        sampai_tanggal=sampai_tanggal,
        dry_run=dry_run,
        karyawan_ids=karyawan_ids,
        collect_details=True,
        detail_limit=500,
    )
    return JsonResponse(summary, json_dumps_params={"ensure_ascii": False})
