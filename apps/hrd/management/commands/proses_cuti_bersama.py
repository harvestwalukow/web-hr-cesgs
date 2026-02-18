from django.core.management.base import BaseCommand
from apps.hrd.utils.jatah_cuti import isi_cuti_bersama_h_minus_1, potong_jatah_cuti_h_minus_1, backfill_potong_cuti_bersama
from apps.hrd.models import TidakAmbilCuti, CutiBersama, JatahCuti, Karyawan
from django.utils import timezone
from datetime import datetime, timedelta
from django.db import transaction
import logging
from django.utils.dateparse import parse_date


class Command(BaseCommand):
    help = 'Proses cuti bersama sesuai aturan H-1 dari AGENTS.md dengan prevention check'

    def add_arguments(self, parser):
        parser.add_argument(
            '--tahun',
            type=int,
            help='Tahun untuk memproses cuti bersama (default: tahun sekarang)',
            default=datetime.now().year
        )
        parser.add_argument(
            '--mode',
            type=str,
            choices=['h-minus-1', 'manual', 'backfill'],
            help='Mode pemrosesan: h-minus-1 (otomatis setiap hari), manual (proses semua), atau backfill (potong yang sudah lewat & belum kepotong)',
            default='h-minus-1'
        )
        parser.add_argument(
            '--sampai',
            type=str,
            help='Batas tanggal cuti bersama yang diproses (YYYY-MM-DD). Default: hari ini.',
            default=None
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Simulasi saja (tidak menulis ke DB). Disarankan dijalankan dulu.',
        )
        parser.add_argument(
            '--karyawan-id',
            action='append',
            type=int,
            help='Batasi ke karyawan tertentu (boleh diulang beberapa kali).',
            default=[]
        )

    def handle(self, *args, **options):
        tahun = options['tahun']
        mode = options['mode']
        sampai_raw = options.get('sampai')
        dry_run = bool(options.get('dry_run'))
        karyawan_ids = options.get('karyawan_id') or []
        sampai_tanggal = None
        if sampai_raw:
            sampai_tanggal = parse_date(sampai_raw)
            if not sampai_tanggal:
                raise ValueError(f"Format --sampai tidak valid: {sampai_raw}. Gunakan YYYY-MM-DD.")
        
        # Setup logging
        logging.basicConfig(level=logging.INFO)
        
        self.stdout.write(f'Memproses cuti bersama untuk tahun {tahun} dengan mode {mode}')
        
        try:
            if mode == 'h-minus-1':
                # Mode H-1: Proses prevention dulu, baru pemotongan
                self.stdout.write('=== STEP 1: Processing Prevention ===')
                self.process_prevention()
                
                self.stdout.write('=== STEP 2: Processing Cuti Cut ===')
                self.potong_jatah_cuti_dengan_prevention()
                
            elif mode == 'manual':
                # Mode manual: Proses semua cuti bersama di tahun tersebut
                self.stdout.write(f'Menjalankan proses cuti bersama manual untuk tahun {tahun}...')
                isi_cuti_bersama_h_minus_1(tahun)
                self.stdout.write(
                    self.style.SUCCESS(f'Berhasil memproses cuti bersama untuk tahun {tahun}')
                )
            elif mode == 'backfill':
                self.stdout.write('=== BACKFILL: memotong cuti bersama yang sudah lewat & belum kepotong ===')
                self.stdout.write(f'- dry_run: {dry_run}')
                if sampai_tanggal:
                    self.stdout.write(f'- sampai: {sampai_tanggal}')
                if karyawan_ids:
                    self.stdout.write(f'- karyawan_id: {karyawan_ids}')

                summary = backfill_potong_cuti_bersama(
                    tahun=tahun,
                    sampai_tanggal=sampai_tanggal,
                    dry_run=dry_run,
                    karyawan_ids=karyawan_ids if karyawan_ids else None,
                )
                self.stdout.write(self.style.SUCCESS(f'Backfill done. Summary: {summary}'))
                
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Error dalam memproses cuti bersama: {str(e)}')
            )
            raise e
    
    def process_prevention(self):
        """Process prevention scenario untuk tidak ambil cuti"""
        today = timezone.now().date()
        
        # Cari pengajuan yang disetujui dengan scenario prevent_cut
        pengajuan_prevent = TidakAmbilCuti.objects.filter(
            status='disetujui',
            scenario='prevent_cut',
            is_processed=False
        )
        
        processed_count = 0
        
        for pengajuan in pengajuan_prevent:
            tanggal_to_process = []
            
            # Cek setiap tanggal dalam pengajuan
            for tanggal_cuti in pengajuan.tanggal.all():
                h_minus_1 = tanggal_cuti.tanggal - timedelta(days=1)
                
                # Jika sudah H-1 atau lewat, maka proses pencegahan
                if today >= h_minus_1:
                    tanggal_to_process.append(tanggal_cuti)
            
            # Jika ada tanggal yang perlu diproses
            if tanggal_to_process:
                with transaction.atomic():
                    # Tandai sebagai sudah diproses
                    pengajuan.is_processed = True
                    pengajuan.save()
                    
                    # Log setiap tanggal yang diproses
                    for tanggal_cuti in tanggal_to_process:
                        self.stdout.write(
                            self.style.SUCCESS(
                                f'✓ Prevention processed: {pengajuan.id_karyawan.nama} - {tanggal_cuti.tanggal}'
                            )
                        )
                    
                    processed_count += 1
        
        if processed_count > 0:
            self.stdout.write(
                self.style.SUCCESS(f'Total prevention processed: {processed_count}')
            )
        else:
            self.stdout.write('No prevention to process today')
    
    def potong_jatah_cuti_dengan_prevention(self):
        """Potong jatah cuti dengan mengecek prevention terlebih dahulu"""
        today = timezone.now().date()
        tomorrow = today + timedelta(days=1)
        
        # Cari cuti bersama yang besok (H-1) (hanya jenis 'Cuti Bersama')
        cuti_besok = CutiBersama.objects.filter(tanggal=tomorrow, jenis='Cuti Bersama')
        
        if not cuti_besok.exists():
            self.stdout.write('No cuti bersama tomorrow to process')
            return
        
        # Ambil semua karyawan aktif
        karyawan_aktif = Karyawan.objects.filter(status_keaktifan='Aktif')
        
        processed_count = 0
        prevented_count = 0
        
        for karyawan in karyawan_aktif:
            for cuti in cuti_besok:
                # Cek apakah karyawan ini ada pengajuan tidak ambil cuti yang disetujui
                ada_pencegahan = TidakAmbilCuti.objects.filter(
                    id_karyawan=karyawan,
                    tanggal=cuti,
                    status='disetujui',
                    scenario='prevent_cut',
                    is_processed=True  # Sudah diproses oleh prevention
                ).exists()
                
                if ada_pencegahan:
                    self.stdout.write(
                        self.style.WARNING(
                            f'⚠ Skip cutting: {karyawan.nama} - {cuti.tanggal} (Prevention approved)'
                        )
                    )
                    prevented_count += 1
                    continue
                
                # Jika tidak ada pencegahan, potong jatah cuti
                with transaction.atomic():
                    jatah_cuti, created = JatahCuti.objects.get_or_create(
                        karyawan=karyawan,
                        tahun=cuti.tanggal.year,
                        defaults={'total_cuti': 12, 'sisa_cuti': 12}
                    )
                    
                    if jatah_cuti.sisa_cuti > 0:
                        jatah_cuti.sisa_cuti -= 1
                        jatah_cuti.save()
                        
                        self.stdout.write(
                            f'✂ Cut 1 day: {karyawan.nama} for {cuti.tanggal} (Remaining: {jatah_cuti.sisa_cuti})'
                        )
                        processed_count += 1
                    else:
                        self.stdout.write(
                            self.style.ERROR(
                                f'❌ Cannot cut: {karyawan.nama} - No remaining cuti'
                            )
                        )
        
        self.stdout.write(
            self.style.SUCCESS(
                f'=== CUTTING SUMMARY ===\n'
                f'Cuts processed: {processed_count}\n'
                f'Cuts prevented: {prevented_count}'
            )
        )