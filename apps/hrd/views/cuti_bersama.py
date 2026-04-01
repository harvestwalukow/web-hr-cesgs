from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.shortcuts import render, redirect
import logging

from collections import Counter, defaultdict

from django.db import transaction

from apps.hrd.models import CutiBersama, Karyawan, TidakAmbilCuti, DetailJatahCuti, JatahCuti
from apps.hrd.forms import CutiBersamaForm
from apps.hrd.utils.jatah_cuti import (
    hitung_jatah_cuti,
    potong_jatah_cuti_h_minus_1,
    backfill_potong_cuti_bersama,
    reconcile_cuti_tahunan_for_dates,
    rapikan_cuti_tahunan,
    pindahkan_cuti_tahunan_ke_tahun_sebelumnya,
)
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
            
            tanggal_dihapus = cuti_dihapus.tanggal
            keterangan_dihapus = cuti_dihapus.keterangan
            jenis_dihapus = cuti_dihapus.jenis
            
            cuti_dihapus.delete()

            if cuti_dihapus.jenis != 'Cuti Bersama':
                if jenis_dihapus == "WFA":
                    reconcile_cuti_tahunan_for_dates([tanggal_dihapus], dry_run=False)
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
                        detail_list = DetailJatahCuti.objects.filter(
                            jatah_cuti__karyawan=karyawan,
                            jatah_cuti__tahun=tahun,
                            dipakai=True,
                            keterangan__contains=f'Cuti Bersama: {keterangan_dihapus or tanggal_dihapus}'
                        )
                        
                        if detail_list.exists():
                            for detail in detail_list:
                                detail.dipakai = False
                                detail.jumlah_hari = 0
                                detail.keterangan = f'Dikembalikan: {keterangan_dihapus or tanggal_dihapus} (dihapus)'
                                detail.save()
                                
                                jatah_cuti = detail.jatah_cuti
                                jatah_cuti.sisa_cuti += 1
                                jatah_cuti.save()
                        else:
                            hitung_jatah_cuti(karyawan, tahun, isi_detail_cuti_bersama=False)

            messages.success(request, f"Cuti bersama {tanggal_dihapus} berhasil dihapus dan jatah cuti dikembalikan.")
            reconcile_cuti_tahunan_for_dates([tanggal_dihapus], dry_run=False)
            return redirect('input_cuti_bersama')
        except CutiBersama.DoesNotExist:
            messages.error(request, "Data tidak ditemukan.")

    if request.method == 'POST':
        form = CutiBersamaForm(request.POST)
        if form.is_valid():
            cuti_bersama = form.save()
            
            besok = datetime.now().date() + timedelta(days=1)
            
            if cuti_bersama.jenis == 'Cuti Bersama':
                if cuti_bersama.tanggal == besok:
                    potong_jatah_cuti_h_minus_1()
                    messages.success(request, f"Cuti bersama tanggal {cuti_bersama.tanggal} berhasil ditambahkan dan jatah cuti langsung dipotong (H-1).")
                else:
                    messages.success(request, f"Cuti bersama tanggal {cuti_bersama.tanggal} berhasil ditambahkan. Jatah cuti akan dipotong otomatis H-1.")
            else:
                messages.success(request, f"{cuti_bersama.jenis} tanggal {cuti_bersama.tanggal} berhasil ditambahkan.")

            if cuti_bersama.jenis in ["WFA", "Cuti Bersama"]:
                reconcile_cuti_tahunan_for_dates([cuti_bersama.tanggal], dry_run=False)
            
            return redirect('input_cuti_bersama')
    else:
        form = CutiBersamaForm()

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


@login_required
@require_http_methods(["GET", "POST"])
def reconcile_cuti_tahunan_view(request):
    """
    Endpoint web untuk reconcile data cuti tahunan tanpa akses terminal.

    GET:
      - tanpa action: mengembalikan instruksi singkat
      - action=dry-run: simulasi reconcile (tanpa menulis DB)
      - action=run&confirm=RUN: jalankan reconcile via URL (menulis DB)
    POST:
      - action=run: jalankan reconcile dan tulis DB (wajib confirm=RUN)
    """
    if not getattr(request.user, "is_superuser", False) and getattr(request.user, "role", None) != "HRD":
        return HttpResponseForbidden("Forbidden")

    action = (request.POST.get("action") or request.GET.get("action") or "").strip().lower()
    tanggal_dari_raw = request.POST.get("tanggal_dari") or request.GET.get("tanggal_dari")
    tanggal_sampai_raw = request.POST.get("tanggal_sampai") or request.GET.get("tanggal_sampai")
    tanggal_raw = request.POST.get("tanggal") or request.GET.get("tanggal")
    karyawan_ids_raw = request.POST.get("karyawan_ids") or request.GET.get("karyawan_ids")  # comma-separated
    max_cuti_raw = request.POST.get("max_cuti") or request.GET.get("max_cuti") or "2000"
    include_details_raw = request.POST.get("include_details") or request.GET.get("include_details") or "1"
    detail_limit_raw = request.POST.get("detail_limit") or request.GET.get("detail_limit") or "200"

    if request.method == "GET" and action not in ("dry-run", "dryrun", "run"):
        return JsonResponse(
            {
                "ok": True,
                "message": (
                    "Use ?action=dry-run&tanggal_dari=YYYY-MM-DD&tanggal_sampai=YYYY-MM-DD "
                    "[&karyawan_ids=1,2][&max_cuti=2000][&include_details=1][&detail_limit=200] to simulate. "
                    "Use action=run&confirm=RUN (GET or POST) with same params to execute."
                ),
                "examples": {
                    "dry_run_range": "/hrd/reconcile-cuti-tahunan/?action=dry-run&tanggal_dari=2026-03-20&tanggal_sampai=2026-03-25",
                    "dry_run_single_day": "/hrd/reconcile-cuti-tahunan/?action=dry-run&tanggal=2026-03-25",
                    "run_range_get": "/hrd/reconcile-cuti-tahunan/?action=run&confirm=RUN&tanggal_dari=2026-03-20&tanggal_sampai=2026-03-25",
                },
            }
        )

    def parse_date_flexible(s):
        if not s:
            return None
        # Prefer Django helper first (covers standard YYYY-MM-DD).
        d = parse_date(s)
        if d:
            return d
        # Fallback: allow non-zero-padded day (e.g. 2026-03-1).
        try:
            return datetime.strptime(s, "%Y-%m-%d").date()
        except Exception:
            return None

    if tanggal_raw:
        t = parse_date_flexible(tanggal_raw)
        if not t:
            return JsonResponse({"error": f"Invalid tanggal: {tanggal_raw} (use YYYY-MM-DD)"}, status=400)
        dates = [t]
    else:
        if not tanggal_dari_raw or not tanggal_sampai_raw:
            return JsonResponse(
                {"error": "tanggal_dari dan tanggal_sampai wajib diisi (atau gunakan param tanggal)"},
                status=400,
            )

        tanggal_dari = parse_date_flexible(tanggal_dari_raw)
        tanggal_sampai = parse_date_flexible(tanggal_sampai_raw)
        if not tanggal_dari:
            return JsonResponse({"error": f"Invalid tanggal_dari: {tanggal_dari_raw} (use YYYY-MM-DD)"}, status=400)
        if not tanggal_sampai:
            return JsonResponse({"error": f"Invalid tanggal_sampai: {tanggal_sampai_raw} (use YYYY-MM-DD)"}, status=400)
        if tanggal_dari > tanggal_sampai:
            return JsonResponse({"error": "tanggal_dari tidak boleh lebih besar dari tanggal_sampai"}, status=400)

        delta = (tanggal_sampai - tanggal_dari).days
        if delta > 366:
            return JsonResponse({"error": "Rentang tanggal terlalu besar (maksimal 367 hari)"}, status=400)

        dates = [tanggal_dari + timedelta(days=i) for i in range(delta + 1)]

    karyawan_ids = None
    if karyawan_ids_raw:
        try:
            karyawan_ids = [int(x.strip()) for x in karyawan_ids_raw.split(",") if x.strip()]
        except ValueError:
            return JsonResponse({"error": f"Invalid karyawan_ids: {karyawan_ids_raw} (use comma-separated ints)"}, status=400)

    try:
        max_cuti = int(max_cuti_raw)
    except ValueError:
        return JsonResponse({"error": f"Invalid max_cuti: {max_cuti_raw}"}, status=400)
    if max_cuti < 1:
        return JsonResponse({"error": "max_cuti minimal 1"}, status=400)

    include_details = str(include_details_raw).strip().lower() not in ("0", "false", "no", "off")
    try:
        detail_limit = int(detail_limit_raw)
    except ValueError:
        return JsonResponse({"error": f"Invalid detail_limit: {detail_limit_raw}"}, status=400)
    if detail_limit < 1:
        return JsonResponse({"error": "detail_limit minimal 1"}, status=400)

    confirm_value = (
        request.POST.get("confirm")
        if request.method == "POST"
        else request.GET.get("confirm")
    ) or ""
    confirm_ok = confirm_value.strip().upper() == "RUN"

    if action == "run":
        if not confirm_ok:
            return JsonResponse(
                {"error": "Missing/invalid confirm. Send confirm=RUN to execute."},
                status=400,
            )
        dry_run = False
    else:
        # Default semua selain action=run adalah dry-run (termasuk GET biasa).
        dry_run = True

    summary = reconcile_cuti_tahunan_for_dates(
        dates=dates,
        karyawan_ids=karyawan_ids,
        dry_run=dry_run,
        max_cuti=max_cuti,
        collect_details=include_details,
        detail_limit=detail_limit,
    )
    return JsonResponse(summary, json_dumps_params={"ensure_ascii": False})


class _RapikanSemuaDryRunRollback(Exception):
    """Internal: batalkan seluruh transaksi dry-run rapikan semua."""


def _rapikan_detail_snapshot(jc, tahun):
    """Daftar slot terpakai (untuk diff dipasangkan per identitas, bukan urutan global)."""
    return list(
        DetailJatahCuti.objects.filter(
            jatah_cuti=jc, tahun=tahun, dipakai=True
        )
        .order_by("keterangan", "bulan", "id")
        .values("id", "bulan", "keterangan", "tanggal_terpakai")
    )


def _rapikan_identity_key(row):
    """Kunci logis satu pemakaian slot: (keterangan, tanggal_terpakai)."""
    k = (row.get("keterangan") or "").strip()
    return (k, row.get("tanggal_terpakai"))


def _rapikan_include_move_in_response(m):
    """
    Untuk respons `rapikan-semua`, laporkan semua pergerakan slot cuti yang relevan
    dengan data yang terlihat di tabel Jatah Cuti Karyawan.
    """
    if not m:
        return False
    ket = (m.get("keterangan") or "").strip().lower()
    if "hangus" in ket:
        return False
    return True


def _rapikan_one_jc_moves(jc):
    """Snapshot → rapikan → snapshot; kembalikan (moves, mismatches)."""
    before = _rapikan_detail_snapshot(jc, jc.tahun)
    rapikan_cuti_tahunan(jc.karyawan, jc.tahun)
    after = _rapikan_detail_snapshot(jc, jc.tahun)
    return _rapikan_collect_moves(before, after, jc)


def _rapikan_collect_moves(before_rows, after_rows, jc):
    """
    Pasangkan sebelum/sesudah per **identitas** (keterangan + tanggal_terpakai), lalu perbandingan bulan.

    Jika **multiset bulan** (berapa slot di tiap bulan) sama sebelum/sesudah, dianggap tidak ada perubahan
    layout — tidak ada entri `moves` (menghindari artefak pasangan/swap).

    Catatan: karyawan yang masalahnya hanya `tanggal_terpakai` (sudah diperbaiki lewat reconcile) tapi
    pola bulan tidak berubah saat rapikan **tidak** akan muncul di `moves`; itu bukan bug endpoint ini.
    """
    moves = []
    mismatches = []

    if len(before_rows) != len(after_rows):
        return moves, [
            {
                "tipe": "jumlah_slot_tidak_sama",
                "jatah_cuti_id": jc.id,
                "karyawan_id": jc.karyawan_id,
                "nama_karyawan": jc.karyawan.nama,
                "tahun_jatah": jc.tahun,
                "sebelum": len(before_rows),
                "sesudah": len(after_rows),
            }
        ]

    # Pola okupasi bulan (multiset) sama → tidak ada perubahan layout slot; hindari "pergerakan" palsu
    # akibat urutan pasangan atau swap yang net-nya identik.
    if Counter(r["bulan"] for r in before_rows) == Counter(r["bulan"] for r in after_rows):
        return moves, mismatches

    def group_by_identity(rows):
        g = defaultdict(list)
        for r in rows:
            g[_rapikan_identity_key(r)].append(r)
        for key in g:
            g[key].sort(key=lambda x: (x["bulan"], x.get("id") or 0))
        return g

    bg = group_by_identity(before_rows)
    ag = group_by_identity(after_rows)
    all_keys = set(bg.keys()) | set(ag.keys())

    for key in sorted(all_keys, key=lambda k: (k[0] or "", str(k[1]) if k[1] is not None else "")):
        lb = bg.get(key, [])
        la = ag.get(key, [])
        if len(lb) != len(la):
            mismatches.append(
                {
                    "tipe": "jumlah_per_identitas_tidak_sama",
                    "jatah_cuti_id": jc.id,
                    "karyawan_id": jc.karyawan_id,
                    "nama_karyawan": jc.karyawan.nama,
                    "tahun_jatah": jc.tahun,
                    "identitas_keterangan": (key[0] or "")[:400],
                    "identitas_tanggal_terpakai": str(key[1]) if key[1] is not None else None,
                    "sebelum": len(lb),
                    "sesudah": len(la),
                }
            )
            continue
        for b, a in zip(lb, la):
            if b["bulan"] == a["bulan"]:
                continue
            moves.append(
                {
                    "tipe": "geser_dalam_tahun",
                    "jatah_cuti_id": jc.id,
                    "karyawan_id": jc.karyawan_id,
                    "nama_karyawan": jc.karyawan.nama,
                    "tahun_jatah": jc.tahun,
                    "dari_tahun_jatah": jc.tahun,
                    "ke_tahun_jatah": jc.tahun,
                    "dari_bulan": b["bulan"],
                    "ke_bulan": a["bulan"],
                    "keterangan": (b.get("keterangan") or "")[:400],
                    "tanggal_terpakai": str(b["tanggal_terpakai"]) if b.get("tanggal_terpakai") else None,
                }
            )

    return moves, mismatches


def _run_rapikan_semua_with_moves(*, include_moves, move_limit):
    """
    Urutan per karyawan:
      1) Per JatahCuti / tahun: `rapikan_cuti_tahunan` + catat `geser_dalam_tahun` (snapshot diff).
      2) Pasangan tahun berturut: `pindahkan_cuti_tahunan_ke_tahun_sebelumnya` (log lintas tahun).
      3) Rapikan lagi per JatahCuti + catat geser sisa (mis. setelah langkah 2).

    Returns:
      processed_karyawan, processed_jatah_cuti, all_moves (capped), total_move_count,
      mismatches, moves_truncated, errors, error_samples
    """
    logger = logging.getLogger(__name__)
    processed_jc = 0
    all_moves = []
    total_move_count = 0
    mismatches = []
    moves_truncated = False
    errors = 0
    error_samples = []

    kid_list = sorted(set(JatahCuti.objects.values_list("karyawan_id", flat=True)))
    processed_karyawan = len(kid_list)

    for kid in kid_list:
        try:
            karyawan = Karyawan.objects.get(pk=kid)
        except Karyawan.DoesNotExist:
            errors += 1
            if len(error_samples) < 30:
                error_samples.append({"karyawan_id": kid, "error": "Karyawan tidak ada"})
            continue

        years = sorted(
            JatahCuti.objects.filter(karyawan_id=kid).values_list("tahun", flat=True).distinct()
        )
        try:
            # 1) Rapikan dalam setiap tahun dulu + catat geser (jangan hanya rapikan_* tanpa diff:
            #    pass berikutnya akan snapshot state yang sudah sama sehingga 12->9 hilang dari moves).
            for tahun in years:
                jc = (
                    JatahCuti.objects.filter(karyawan_id=kid, tahun=tahun)
                    .select_related("karyawan")
                    .first()
                )
                if not jc:
                    continue
                try:
                    moves, mm = _rapikan_one_jc_moves(jc)
                except Exception as e:
                    errors += 1
                    logger.exception(
                        "rapikan_semua (pass1): gagal jc id=%s karyawan_id=%s tahun=%s",
                        jc.id,
                        kid,
                        tahun,
                    )
                    if len(error_samples) < 30:
                        error_samples.append(
                            {
                                "jatah_cuti_id": jc.id,
                                "karyawan_id": kid,
                                "tahun": tahun,
                                "error": str(e),
                            }
                        )
                    continue
                mismatches.extend(mm)
                filtered = [x for x in moves if _rapikan_include_move_in_response(x)]
                total_move_count += len(filtered)
                if include_moves:
                    for m in filtered:
                        if len(all_moves) >= move_limit:
                            moves_truncated = True
                            break
                        all_moves.append(m)

            # 2) Cuti Tahunan: tahun baru -> slot kosong tahun lalu
            for i in range(len(years) - 1):
                for mv in pindahkan_cuti_tahunan_ke_tahun_sebelumnya(
                    karyawan, years[i], years[i + 1]
                ):
                    total_move_count += 1
                    if include_moves:
                        if len(all_moves) >= move_limit:
                            moves_truncated = True
                        else:
                            all_moves.append(mv)

            # 3) Rapikan lagi + catat pergeseran (snapshot sebelum/sesudah per jc)
            for tahun in years:
                jc = (
                    JatahCuti.objects.filter(karyawan_id=kid, tahun=tahun)
                    .select_related("karyawan")
                    .first()
                )
                if not jc:
                    continue
                try:
                    moves, mm = _rapikan_one_jc_moves(jc)
                except Exception as e:
                    errors += 1
                    logger.exception(
                        "rapikan_semua: gagal jc id=%s karyawan_id=%s tahun=%s",
                        jc.id,
                        kid,
                        tahun,
                    )
                    if len(error_samples) < 30:
                        error_samples.append(
                            {
                                "jatah_cuti_id": jc.id,
                                "karyawan_id": kid,
                                "tahun": tahun,
                                "error": str(e),
                            }
                        )
                    continue
                mismatches.extend(mm)
                filtered = [x for x in moves if _rapikan_include_move_in_response(x)]
                total_move_count += len(filtered)
                if include_moves:
                    for m in filtered:
                        if len(all_moves) >= move_limit:
                            moves_truncated = True
                            break
                        all_moves.append(m)
                processed_jc += 1
        except Exception as e:
            errors += 1
            logger.exception("rapikan_semua: gagal karyawan_id=%s", kid)
            if len(error_samples) < 30:
                error_samples.append({"karyawan_id": kid, "error": str(e)})

    return (
        processed_karyawan,
        processed_jc,
        all_moves,
        total_move_count,
        mismatches,
        moves_truncated,
        errors,
        error_samples,
    )


@login_required
@require_http_methods(["GET", "POST"])
def rapikan_semua_jatah_cuti_view(request):
    """
    Jalankan `rapikan_cuti_tahunan` untuk **semua** baris `JatahCuti` (semua karyawan & tahun).

    GET:
      - tanpa action: instruksi singkat
      - action=dry-run: jalankan rapikan dalam satu transaksi lalu **rollback** (DB tidak berubah)
      - action=run&confirm=RUN: commit per baris (tanpa satu transaksi besar)

    Alur:
      1. **Dalam tahun** dulu: rapikan per `JatahCuti`, lalu
      2. **Lintas tahun** (karyawan Tetap/HRD): `Cuti Tahunan` ke slot kosong tahun sebelumnya,
      3. Rapikan lagi per tahun untuk geser sisa.

    Pergerakan di `moves`:
      - `tipe` = `lintas_tahun_cuti_tahunan`: `dari_tahun_jatah` / `dari_bulan` → `ke_tahun_jatah` / `ke_bulan`
      - `tipe` = `geser_dalam_tahun`: semua pergeseran slot yang terdeteksi.

      `include_moves=1` (default), `move_limit` (default 2000) membatasi panjang array `moves`.
    """
    logger = logging.getLogger(__name__)

    if not getattr(request.user, "is_superuser", False) and getattr(request.user, "role", None) != "HRD":
        return HttpResponseForbidden("Forbidden")

    action = (request.POST.get("action") or request.GET.get("action") or "").strip().lower()
    confirm_value = (
        request.POST.get("confirm") if request.method == "POST" else request.GET.get("confirm")
    ) or ""
    confirm_ok = confirm_value.strip().upper() == "RUN"

    if request.method == "GET" and action not in ("dry-run", "dryrun", "run"):
        return JsonResponse(
            {
                "ok": True,
                "message": (
                    "Use ?action=dry-run to simulate rapikan for all JatahCuti (rollback). "
                    "Use ?action=run&confirm=RUN to execute for real. "
                    "Optional: include_moves=1 (default) & move_limit=2000 for per-slot moves (dari_bulan -> ke_bulan)."
                ),
                "examples": {
                    "dry_run": "/hrd/rapikan-jatah-cuti-semua/?action=dry-run&include_moves=1",
                    "run": "/hrd/rapikan-jatah-cuti-semua/?action=run&confirm=RUN&include_moves=1",
                },
            }
        )

    include_moves_raw = request.POST.get("include_moves") or request.GET.get("include_moves") or "1"
    move_limit_raw = request.POST.get("move_limit") or request.GET.get("move_limit") or "2000"
    include_moves = str(include_moves_raw).strip().lower() not in ("0", "false", "no", "off")
    try:
        move_limit = int(move_limit_raw)
    except ValueError:
        return JsonResponse({"error": f"Invalid move_limit: {move_limit_raw}"}, status=400)
    if move_limit < 1:
        return JsonResponse({"error": "move_limit minimal 1"}, status=400)

    total = JatahCuti.objects.count()

    if action == "run":
        if not confirm_ok:
            return JsonResponse(
                {"error": "Missing/invalid confirm. Send confirm=RUN to execute."},
                status=400,
            )
        (
            processed_karyawan,
            processed,
            all_moves,
            total_move_count,
            mismatches,
            moves_truncated,
            errors,
            error_samples,
        ) = _run_rapikan_semua_with_moves(include_moves=include_moves, move_limit=move_limit)

        payload = {
            "dry_run": False,
            "total_jatah_cuti": total,
            "processed_karyawan": processed_karyawan,
            "processed_jatah_cuti": processed,
            "processed": processed,
            "errors": errors,
            "error_samples": error_samples,
            "total_pergerakan_slot": total_move_count,
            "moves_truncated": moves_truncated,
            "moves_in_response": len(all_moves),
        }
        if include_moves:
            payload["moves"] = all_moves
        if mismatches:
            payload["pairing_mismatches"] = mismatches[:100]

        return JsonResponse(payload, json_dumps_params={"ensure_ascii": False})

    # dry-run: satu transaksi, rollback di akhir
    processed = 0
    processed_karyawan = 0
    try:
        with transaction.atomic():
            (
                processed_karyawan,
                processed,
                all_moves,
                total_move_count,
                mismatches,
                moves_truncated,
                _dry_err,
                _dry_samples,
            ) = _run_rapikan_semua_with_moves(
                include_moves=include_moves, move_limit=move_limit
            )
            raise _RapikanSemuaDryRunRollback()
    except _RapikanSemuaDryRunRollback:
        pass
    except Exception as e:
        logger.exception("rapikan_semua dry-run failed")
        return JsonResponse(
            {
                "dry_run": True,
                "error": str(e),
                "processed_before_failure_jatah": processed,
                "processed_before_failure_karyawan": processed_karyawan,
            },
            status=500,
            json_dumps_params={"ensure_ascii": False},
        )

    payload = {
        "dry_run": True,
        "total_jatah_cuti": total,
        "processed_karyawan": processed_karyawan,
        "processed_jatah_cuti": processed,
        "processed": processed,
        "message": "Simulasi selesai; perubahan di DB dibatalkan (rollback).",
        "total_pergerakan_slot": total_move_count,
        "moves_truncated": moves_truncated,
        "moves_in_response": len(all_moves),
    }
    if include_moves:
        payload["moves"] = all_moves
    if mismatches:
        payload["pairing_mismatches"] = mismatches[:100]

    return JsonResponse(payload, json_dumps_params={"ensure_ascii": False})
