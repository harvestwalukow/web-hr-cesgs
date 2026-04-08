import json
import random
from datetime import date

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Count
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from apps.absensi.models import AbsensiMagang
from apps.authentication.decorators import role_required
from apps.hrd.models import CatatanPengambilanGalon, Karyawan


def _parse_tanggal(s):
    if not s:
        return date.today()
    from datetime import datetime

    try:
        return datetime.strptime(s, '%Y-%m-%d').date()
    except ValueError:
        return date.today()


def _wfo_rows_for_date(tanggal):
    qs = (
        AbsensiMagang.objects.filter(
            tanggal=tanggal,
            keterangan='WFO',
            jam_masuk__isnull=False,
            id_karyawan__status_keaktifan='Aktif',
        )
        .select_related('id_karyawan')
        .order_by('id_karyawan__nama')
    )
    karyawan_ids = [a.id_karyawan_id for a in qs]
    if not karyawan_ids:
        return [], {}

    count_qs = (
        CatatanPengambilanGalon.objects.filter(id_karyawan_id__in=karyawan_ids)
        .values('id_karyawan_id')
        .annotate(total=Count('id'))
    )
    count_map = {row['id_karyawan_id']: row['total'] for row in count_qs}

    rows = []
    for a in qs:
        k = a.id_karyawan
        c = count_map.get(k.id, 0)
        rows.append(
            {
                'absensi': a,
                'karyawan': k,
                'frekuensi_galon': c,
                'pernah_ambil': c > 0,
            }
        )
    return rows, count_map


def _weighted_random_choice(rows):
    """Bobot ~ 1/(n+1): yang belum pernah ambil punya peluang lebih besar."""
    if not rows:
        return None
    weights = [1.0 / (r['frekuensi_galon'] + 1) for r in rows]
    chosen = random.choices(rows, weights=weights, k=1)[0]
    return chosen


@login_required
@role_required(['HRD'])
def pengambilan_galon_view(request):
    tanggal = _parse_tanggal(request.GET.get('tanggal'))
    rows, _ = _wfo_rows_for_date(tanggal)

    recent = (
        CatatanPengambilanGalon.objects.select_related('id_karyawan')
        .order_by('-tanggal', '-created_at')[:15]
    )

    if request.method == 'POST':
        karyawan_id = request.POST.get('karyawan_id')
        tanggal_catat = _parse_tanggal(request.POST.get('tanggal') or str(tanggal))
        if not karyawan_id:
            messages.error(request, 'Data tidak lengkap.')
            return redirect('pengambilan_galon')
        try:
            k = Karyawan.objects.get(pk=int(karyawan_id), status_keaktifan='Aktif')
        except (Karyawan.DoesNotExist, ValueError):
            messages.error(request, 'Karyawan tidak valid.')
            return redirect('pengambilan_galon')

        wfo_ids = {
            a.id_karyawan_id
            for a in AbsensiMagang.objects.filter(
                tanggal=tanggal_catat,
                keterangan='WFO',
                jam_masuk__isnull=False,
            )
        }
        if k.id not in wfo_ids:
            messages.error(
                request,
                'Karyawan ini tidak tercatat WFO pada tanggal tersebut.',
            )
            return redirect(
                f"{reverse('pengambilan_galon')}?tanggal={tanggal_catat.isoformat()}"
            )

        _, created = CatatanPengambilanGalon.objects.get_or_create(
            id_karyawan=k,
            tanggal=tanggal_catat,
            defaults={'dicatat_oleh': request.user},
        )
        if not created:
            messages.warning(
                request,
                f'Pengambilan galon untuk {k.nama} pada {tanggal_catat} sudah tercatat.',
            )
        else:
            messages.success(
                request,
                f'Pengambilan galon oleh {k.nama} pada {tanggal_catat} berhasil dicatat.',
            )
        return redirect(
            f"{reverse('pengambilan_galon')}?tanggal={tanggal_catat.isoformat()}"
        )

    return render(
        request,
        'hrd/pengambilan_galon.html',
        {
            'tanggal': tanggal,
            'rows': rows,
            'recent': recent,
        },
    )


@login_required
@role_required(['HRD'])
@require_POST
def pengambilan_galon_randomize(request):
    try:
        body = json.loads(request.body.decode() or '{}')
    except json.JSONDecodeError:
        body = {}
    tanggal = _parse_tanggal(body.get('tanggal'))
    rows, _ = _wfo_rows_for_date(tanggal)
    if not rows:
        return JsonResponse(
            {
                'ok': False,
                'message': 'Tidak ada karyawan WFO dengan absen masuk pada tanggal ini.',
            }
        )
    chosen = _weighted_random_choice(rows)
    k = chosen['karyawan']
    return JsonResponse(
        {
            'ok': True,
            'karyawan_id': k.id,
            'nama': k.nama,
            'divisi': k.divisi,
            'frekuensi_sebelumnya': chosen['frekuensi_galon'],
            'pernah_ambil': chosen['pernah_ambil'],
            'tanggal': tanggal.isoformat(),
        }
    )
