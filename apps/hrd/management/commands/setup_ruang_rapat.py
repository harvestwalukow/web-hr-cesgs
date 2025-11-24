from django.core.management.base import BaseCommand
from apps.hrd.models import RuangRapat

class Command(BaseCommand):
    help = 'Setup initial ruang rapat data'
    
    def handle(self, *args, **options):
        # Create default meeting rooms
        ruang_rapat_data = [
            {
                'nama': 'Ruang Rapat Lama',
                'deskripsi': 'Ruang rapat lama dekat consulting',
                'kapasitas': 12,
                'fasilitas': 'Desk, Chair, Smart TV, AC, Whiteboard',
                'warna_kalender': '#007bff',
                'aktif': True
            },
            {
                'nama': 'Ruang Rapat Baru',
                'deskripsi': 'Ruang rapat baru dekat mushola',
                'kapasitas': 8,
                'fasilitas': 'Desk, Chair, Smart TV, AC, Whiteboard',
                'warna_kalender': '#28a745',  # Green
                'aktif': True
            },
            {
                'nama': 'Ruang Rapat Tengah',
                'deskripsi': 'Ruang rapat lainnya dekat ruang prof Iman',
                'kapasitas': 8,
                'fasilitas': 'Desk, Chair',
                'warna_kalender': '#ffc107',  # Yellow
                'aktif': True
            }
        ]
        
        for data in ruang_rapat_data:
            ruang, created = RuangRapat.objects.get_or_create(
                nama=data['nama'],
                defaults=data
            )
            
            if created:
                self.stdout.write(
                    self.style.SUCCESS(f'Successfully created ruang rapat: {ruang.nama}')
                )
            else:
                self.stdout.write(
                    self.style.WARNING(f'Ruang rapat already exists: {ruang.nama}')
                )
        
        self.stdout.write(
            self.style.SUCCESS('Setup ruang rapat completed!')
        )