from django import forms
from apps.hrd.models import Karyawan, Cuti, Izin, CutiBersama, TidakAmbilCuti
from apps.authentication.models import User
from datetime import time, datetime, date
from .models import BookingRuangRapat, RuangRapat


class KaryawanForm(forms.ModelForm):
    email = forms.EmailField(widget=forms.EmailInput(attrs={
        'class': 'form-control',
        'pattern': r'^[\w\.-]+@[\w\.-]+\.\w{2,4}$',
        'title': 'Gunakan format email yang valid, contoh: nama@email.com'
    }))
    role = forms.ChoiceField(choices=User.ROLE_CHOICES, widget=forms.Select(attrs={'class': 'form-control'}))

    class Meta:
        model = Karyawan
        fields = ['nama', 'nama_catatan_kehadiran', 'jenis_kelamin', 'jabatan', 'divisi', 'provinsi', 'kabupaten_kota', 'alamat', 'status', 'mulai_kontrak', 'batas_kontrak', 'status_keaktifan', 'no_telepon', 'tanggal_lahir']

        widgets = {
            'nama': forms.TextInput(attrs={
                'class': 'form-control',
                'pattern': r'^[A-Za-z\s]+$',  # Hanya huruf dan spasi
                'title': 'Nama hanya boleh mengandung huruf dan spasi.'
            }),
            'nama_catatan_kehadiran': forms.TextInput(attrs={ 
                'class': 'form-control',
                'placeholder': 'Masukkan nama yang sesuai di catatan kehadiran'
            }),
            'jenis_kelamin': forms.Select(attrs={'class': 'form-control'}),
            'jabatan': forms.TextInput(attrs={'class': 'form-control'}),
            'divisi': forms.TextInput(attrs={'class': 'form-control'}),
            'provinsi': forms.Select(attrs={'class': 'form-control', 'id': 'id_provinsi'}),
            'kabupaten_kota': forms.Select(attrs={'class': 'form-control', 'id': 'id_kabupaten_kota'}),
            'alamat': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'status': forms.Select(attrs={'class': 'form-control'}),
            'mulai_kontrak': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'batas_kontrak': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'status_keaktifan': forms.Select(attrs={'class': 'form-control'}),
            'no_telepon': forms.TextInput(attrs={
                'class': 'form-control',
                'pattern': r'^(\+62|0)[0-9]{9,13}$',
                'title': 'Masukkan nomor telepon yang valid, contoh: +6281234567890 atau 081234567890'
            }),
            'tanggal_lahir': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
        }
    
    def clean_nama(self):
        nama = self.cleaned_data.get('nama')
        if not nama:
            raise forms.ValidationError("Nama tidak boleh kosong.")
        
        # Preprocessing: Capitalize setiap kata
        nama_bersih = ' '.join(word.capitalize() for word in nama.split())
        return nama_bersih

class CutiBersamaForm(forms.ModelForm):
    class Meta:
        model = CutiBersama
        fields = ['tanggal', 'keterangan']
        widgets = {
            'tanggal': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'keterangan': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Opsional'}),
        }

class BookingRuangRapatForm(forms.ModelForm):
    class Meta:
        model = BookingRuangRapat
        fields = ['ruang_rapat', 'judul', 'deskripsi', 'tanggal', 'waktu_mulai', 'waktu_selesai']
        widgets = {
            'tanggal': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'waktu_mulai': forms.TimeInput(attrs={'type': 'time', 'class': 'form-control', 'step': '3600'}),
            'waktu_selesai': forms.TimeInput(attrs={'type': 'time', 'class': 'form-control', 'step': '3600'}),
            'judul': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Contoh: Meeting Tim Marketing'}),
            'deskripsi': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Deskripsi opsional...'}),
            'ruang_rapat': forms.Select(attrs={'class': 'form-control'})
        }
        labels = {
            'ruang_rapat': 'Ruang Rapat',
            'judul': 'Judul Meeting',
            'deskripsi': 'Deskripsi (Opsional)',
            'tanggal': 'Tanggal',
            'waktu_mulai': 'Waktu Mulai',
            'waktu_selesai': 'Waktu Selesai'
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Filter hanya ruang rapat yang aktif
        self.fields['ruang_rapat'].queryset = RuangRapat.objects.filter(aktif=True)
        
        # Set minimum date ke hari ini
        self.fields['tanggal'].widget.attrs['min'] = date.today().strftime('%Y-%m-%d')
    
    def clean_tanggal(self):
        tanggal = self.cleaned_data.get('tanggal')
        if tanggal and tanggal < date.today():
            raise forms.ValidationError('Tidak dapat booking untuk tanggal yang sudah lewat')
        return tanggal
    
    def clean_waktu_mulai(self):
        waktu_mulai = self.cleaned_data.get('waktu_mulai')
        if waktu_mulai and waktu_mulai < time(9, 0):
            raise forms.ValidationError('Waktu mulai tidak boleh sebelum 09:00')
        return waktu_mulai
    
    def clean_waktu_selesai(self):
        waktu_selesai = self.cleaned_data.get('waktu_selesai')
        if waktu_selesai and waktu_selesai > time(18, 0):
            raise forms.ValidationError('Waktu selesai tidak boleh setelah 18:00')
        return waktu_selesai
    
    def clean(self):
        cleaned_data = super().clean()
        waktu_mulai = cleaned_data.get('waktu_mulai')
        waktu_selesai = cleaned_data.get('waktu_selesai')
        tanggal = cleaned_data.get('tanggal')
        ruang_rapat = cleaned_data.get('ruang_rapat')
        
        if waktu_mulai and waktu_selesai:
            if waktu_selesai <= waktu_mulai:
                raise forms.ValidationError('Waktu selesai harus setelah waktu mulai')
        
        # Validasi overlap jika semua field terisi
        if all([tanggal, waktu_mulai, waktu_selesai, ruang_rapat]):
            overlapping_bookings = BookingRuangRapat.objects.filter(
                ruang_rapat=ruang_rapat,
                tanggal=tanggal,
                waktu_mulai__lt=waktu_selesai,
                waktu_selesai__gt=waktu_mulai
            )
            
            # Exclude current instance jika sedang edit
            if self.instance.pk:
                overlapping_bookings = overlapping_bookings.exclude(pk=self.instance.pk)
            
            if overlapping_bookings.exists():
                booking = overlapping_bookings.first()
                raise forms.ValidationError(
                    f'Waktu bertabrakan dengan booking "{booking.judul}" '
                    f'({booking.waktu_mulai.strftime("%H:%M")} - {booking.waktu_selesai.strftime("%H:%M")})'
                )
        
        return cleaned_data


class IzinHRForm(forms.ModelForm):
    """Form untuk HR membuat / mengedit izin karyawan tertentu."""

    class Meta:
        model = Izin
        fields = ['id_karyawan', 'jenis_izin', 'tanggal_izin', 'alasan', 'file_pengajuan', 'kompensasi_lembur']
        widgets = {
            'id_karyawan': forms.Select(attrs={'class': 'form-control'}),
            'jenis_izin': forms.Select(attrs={'class': 'form-control'}),
            'tanggal_izin': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'alasan': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'file_pengajuan': forms.FileInput(attrs={
                'class': 'form-control',
                'accept': '.pdf,.doc,.docx,.jpg,.jpeg,.png',
            }),
            'kompensasi_lembur': forms.RadioSelect(
                choices=Izin.KOMPENSASI_LEMBUR_CHOICES,
                attrs={'class': 'custom-radio-group'}
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['id_karyawan'].label = 'Karyawan'
        self.fields['id_karyawan'].queryset = Karyawan.objects.filter(status_keaktifan='Aktif').order_by('nama')
        self.fields['file_pengajuan'].label = 'Upload Bukti (opsional)'
        self.fields['file_pengajuan'].required = False


class CutiHRForm(forms.ModelForm):
    """Form untuk HR mengedit data cuti karyawan."""

    class Meta:
        model = Cuti
        fields = [
            'id_karyawan',
            'jenis_cuti',
            'tanggal_mulai',
            'tanggal_selesai',
            'file_pengajuan',
            'file_dokumen_formal',
        ]
        widgets = {
            'id_karyawan': forms.Select(attrs={'class': 'form-control'}),
            'jenis_cuti': forms.Select(attrs={'class': 'form-control'}),
            'tanggal_mulai': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'tanggal_selesai': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'file_pengajuan': forms.FileInput(attrs={
                'class': 'form-control',
                'accept': '.pdf,.doc,.docx,.jpg,.jpeg,.png',
            }),
            'file_dokumen_formal': forms.FileInput(attrs={
                'class': 'form-control',
                'accept': '.doc,.docx,.pdf',
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['id_karyawan'].label = 'Karyawan'
        self.fields['id_karyawan'].queryset = Karyawan.objects.filter(status_keaktifan='Aktif').order_by('nama')
        self.fields['file_pengajuan'].label = 'Upload Bukti Pengajuan (opsional)'
        self.fields['file_pengajuan'].required = False
        self.fields['file_dokumen_formal'].label = 'File Cuti Resmi (opsional)'
        self.fields['file_dokumen_formal'].required = False