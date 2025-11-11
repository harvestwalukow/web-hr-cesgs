from django.core.management.base import BaseCommand
from apps.hrd.models import TidakAmbilCuti, JatahCuti
from django.utils import timezone
from django.db import transaction


class Command(BaseCommand):
    help = 'Process claim back scenario untuk tidak ambil cuti yang sudah disetujui'

    def handle(self, *args, **options):
        # Cari pengajuan claim_back yang disetujui tapi belum diproses
        pengajuan_claim = TidakAmbilCuti.objects.filter(
            status='disetujui',
            scenario='claim_back',
            is_processed=False
        )
        
        processed_count = 0
        
        for pengajuan in pengajuan_claim:
            karyawan = pengajuan.id_karyawan
            jumlah_hari = pengajuan.tanggal.count()
            tahun_sekarang = timezone.now().year
            
            with transaction.atomic():
                # Ambil atau buat jatah cuti untuk tahun ini
                jatah_cuti, created = JatahCuti.objects.get_or_create(
                    karyawan=karyawan,
                    tahun=tahun_sekarang,
                    defaults={'total_cuti': 12, 'sisa_cuti': 12}
                )
                
                # Tambahkan jatah cuti
                jatah_cuti.sisa_cuti += jumlah_hari
                jatah_cuti.save()
                
                # Tandai sudah diproses
                pengajuan.is_processed = True
                pengajuan.save()
                
                self.stdout.write(
                    self.style.SUCCESS(
                        f'✓ Claimed back {jumlah_hari} days for {karyawan.nama} '
                        f'(Total now: {jatah_cuti.sisa_cuti})'
                    )
                )
                
                processed_count += 1
        
        if processed_count > 0:
            self.stdout.write(
                self.style.SUCCESS(f'Total claim back processed: {processed_count}')
            )
        else:
            self.stdout.write('No claim back requests to process')