from django import forms
from .models import Rules, AbsensiMagang
from datetime import datetime
from apps.utils.validators import validate_file_size
from django.core.exceptions import ValidationError
from apps.hrd.models import Karyawan

BULAN_CHOICES = [(str(i), datetime(2024, i, 1).strftime('%B')) for i in range(1, 13)]

class UploadAbsensiForm(forms.Form):
    bulan = forms.ChoiceField(
        choices=BULAN_CHOICES,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    tahun = forms.ChoiceField(
        choices=[(str(i), str(i)) for i in range(2020, 2031)],
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    file = forms.FileField(
        widget=forms.FileInput(attrs={
            'class': 'form-control',
            'accept': '.xls,.xlsx'
        }),
        help_text='Maksimal 5MB. Format: XLS, XLSX'
    )
    rules = forms.ModelChoiceField(
        queryset=Rules.objects.all(),
        widget=forms.Select(attrs={'class': 'form-control'}),
        required=True
    )
    
    def clean_file(self):
        file = self.cleaned_data.get('file')
        if file:
            # Validasi ukuran file
            validate_file_size(file)
            
            # Validasi ekstensi file untuk absensi
            allowed_extensions = ['.xls', '.xlsx']
            file_extension = file.name.lower().split('.')[-1]
            if f'.{file_extension}' not in allowed_extensions:
                raise ValidationError(
                    f'Tipe file tidak diizinkan untuk absensi. Hanya diperbolehkan: {", ".join(allowed_extensions)}'
                )
        return file

class RulesForm(forms.ModelForm):
    class Meta:
        model = Rules
        fields = ['nama_rule', 'jam_masuk', 'jam_keluar', 'toleransi_telat', 'maksimal_izin']
        
        widgets = {
            'nama_rule': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nama Aturan'}),
            'jam_masuk': forms.TimeInput(attrs={'type': 'time', 'class': 'form-control'}),
            'jam_keluar': forms.TimeInput(attrs={'type': 'time', 'class': 'form-control'}),
            'toleransi_telat': forms.NumberInput(attrs={'class': 'form-control'}),
            'maksimal_izin': forms.NumberInput(attrs={'class': 'form-control'}),
        }


class AbsensiMagangForm(forms.ModelForm):
    lokasi = forms.CharField(widget=forms.HiddenInput())
    screenshot_data = forms.CharField(widget=forms.HiddenInput(), required=False)
    
    class Meta:
        model = AbsensiMagang
        fields = ['id_karyawan', 'lokasi', 'keterangan']
        widgets = {
            'id_karyawan': forms.HiddenInput(),
            'keterangan': forms.Select(attrs={'class': 'form-control', 'required': 'required'}),
        }

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super(AbsensiMagangForm, self).__init__(*args, **kwargs)
        
        if user:
            try:
                karyawan = Karyawan.objects.get(user=user)
                self.fields['id_karyawan'].initial = karyawan.id
            except Karyawan.DoesNotExist:
                pass

class AbsensiPulangForm(forms.ModelForm):
    lokasi = forms.CharField(widget=forms.HiddenInput())
    screenshot_data = forms.CharField(widget=forms.HiddenInput(), required=False)
    
    class Meta:
        model = AbsensiMagang
        fields = ['id_karyawan', 'lokasi']
        widgets = {
            'id_karyawan': forms.HiddenInput(),
        }

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super(AbsensiPulangForm, self).__init__(*args, **kwargs)
        
        if user:
            try:
                karyawan = Karyawan.objects.get(user=user)
                self.fields['id_karyawan'].initial = karyawan.id
            except Karyawan.DoesNotExist:
                pass