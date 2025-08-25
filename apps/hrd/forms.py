from django import forms
from apps.hrd.models import Karyawan, Cuti, Izin, CutiBersama, TidakAmbilCuti
from apps.authentication.models import User

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
