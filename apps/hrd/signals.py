from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from .models import JatahCuti, DetailJatahCuti, Karyawan, CutiBersama
from datetime import datetime
from apps.hrd.utils.jatah_cuti import hitung_jatah_cuti

@receiver(post_save, sender=JatahCuti)
def create_detail_jatah_cuti(sender, instance, created, **kwargs):
    if created:
        for bulan in range(1, 13):
            DetailJatahCuti.objects.create(
                jatah_cuti=instance,
                bulan=bulan,
                tahun=instance.tahun,
                dipakai=False,
                jumlah_hari=0,
                keterangan=''
            )

@receiver(post_save, sender=Karyawan)
def handle_karyawan_jatah_cuti(sender, instance, created, **kwargs):
    """
    Signal untuk menangani jatah cuti ketika karyawan dibuat atau diupdate
    """
    if hasattr(instance, 'user') and instance.user.role in ['HRD', 'Karyawan Tetap']:
        
        if created:
            # Karyawan baru - buat jatah cuti untuk tahun ini
            tahun_ini = datetime.now().year
            result = hitung_jatah_cuti(instance, tahun=tahun_ini, isi_detail_cuti_bersama=False)
            

        else:
            # Karyawan diupdate - perbarui SEMUA jatah cuti yang sudah ada
            existing_jatah_list = JatahCuti.objects.filter(karyawan=instance)
            
            if existing_jatah_list.exists():
                # Update semua jatah cuti yang sudah ada
                for jatah in existing_jatah_list:
                    result = hitung_jatah_cuti(instance, tahun=jatah.tahun, isi_detail_cuti_bersama=False)
                    
            else:
                # Jika belum ada jatah cuti sama sekali, buat untuk tahun ini
                tahun_ini = datetime.now().year
                result = hitung_jatah_cuti(instance, tahun=tahun_ini, isi_detail_cuti_bersama=False)