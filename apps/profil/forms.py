from django import forms
from apps.hrd.models import Karyawan
from apps.authentication.models import User
import re

class ProfilForm(forms.ModelForm):
    email = forms.EmailField(
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'pattern': r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$',
            'title': 'Format email tidak valid (contoh: nama@email.com)'
        })
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-control'}),
        required=False
    )
    role = forms.CharField(
        disabled=True,
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    
    # Tambahkan field jabatan dan divisi dengan pola yang sama seperti role
    jabatan = forms.CharField(
        disabled=True,
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    
    divisi = forms.CharField(
        disabled=True,
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )

    class Meta:
        model = Karyawan
        fields = ['nama', 'jabatan', 'divisi', 'provinsi', 'kabupaten_kota', 'alamat', 'status', 'mulai_kontrak', 'batas_kontrak', 'no_telepon']

        widgets = {
            'nama': forms.TextInput(attrs={
                'class': 'form-control',
                'pattern': r'^[A-Za-z\s]+$',
                'title': 'Nama hanya boleh berisi huruf dan spasi.'
            }),
            'provinsi': forms.Select(attrs={'class': 'form-control', 'id': 'id_provinsi'}),
            'kabupaten_kota': forms.Select(attrs={'class': 'form-control', 'id': 'id_kabupaten_kota'}),
            'alamat': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'status': forms.Select(attrs={'class': 'form-control'}),
            'mulai_kontrak': forms.DateInput(attrs={'class': 'form-control', 'readonly': 'readonly'}),
            'batas_kontrak': forms.DateInput(attrs={'class': 'form-control', 'readonly': 'readonly'}),
            'no_telepon': forms.TextInput(attrs={
                'class': 'form-control',
                'pattern': r'^08[0-9]{8,11}$',
                'title': 'Nomor telepon harus format Indonesia, mulai 08 dan 10-13 digit.'
            }),
        }

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)

        if user:
            self.fields['email'].initial = user.email
            self.fields['role'].initial = user.role
            
        # Set initial values untuk jabatan dan divisi dari instance
        if self.instance and self.instance.pk:
            self.fields['jabatan'].initial = self.instance.jabatan
            self.fields['divisi'].initial = self.instance.divisi


    # Validasi tambahan untuk nama
    def clean_nama(self):
        nama = self.cleaned_data.get('nama')
        if not re.match(r'^[A-Za-z\s]+$', nama):
            raise forms.ValidationError('Nama hanya boleh berisi huruf dan spasi.')
        
        nama_bersih = ' '.join(word.capitalize() for word in nama.split())
        return nama_bersih

    # Validasi tambahan untuk nomor telepon
    def clean_no_telepon(self):
        no_telepon = self.cleaned_data.get('no_telepon')
        if not re.match(r'^08[0-9]{8,11}$', no_telepon):
            raise forms.ValidationError('Nomor telepon harus mulai dari 08 dan terdiri dari 10-13 digit angka.')
        return no_telepon

    # Validasi tambahan untuk email (optional kalau mau lebih strict)
    def clean_email(self):
        email = self.cleaned_data.get('email')
        if not re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', email):
            raise forms.ValidationError('Format email tidak valid (contoh: nama@email.com).')
        return email
