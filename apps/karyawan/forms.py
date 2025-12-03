from django import forms
from apps.hrd.models import TidakAmbilCuti, CutiBersama, Cuti, Izin, JatahCuti
from apps.utils.validators import validate_file_size, validate_file_extension
from django.core.exceptions import ValidationError
from datetime import datetime

class TidakAmbilCutiForm(forms.ModelForm):
    tanggal = forms.ModelMultipleChoiceField(
        queryset=CutiBersama.objects.none(),  # Diubah menjadi none() agar bisa diisi di __init__
        widget=forms.CheckboxSelectMultiple(attrs={
            'class': 'custom-checkbox-group'
        }),
        required=True,
        label='Tanggal Tidak Ambil Cuti'
    )

    class Meta:
        model = TidakAmbilCuti
        fields = ['tanggal', 'alasan', 'file_pengajuan']
        widgets = {
            'alasan': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'file_pengajuan': forms.ClearableFileInput(attrs={
                'class': 'form-control',
                'accept': '.pdf,.doc,.docx,.jpg,.jpeg,.png'
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Set queryset untuk tanggal berdasarkan tahun saat ini
        from datetime import datetime
        tahun_sekarang = datetime.now().year
        self.fields['tanggal'].queryset = CutiBersama.objects.filter(tanggal__year=tahun_sekarang)
        self.fields['file_pengajuan'].required = True
        self.fields['alasan'].label = 'Job Desc'
        self.fields['file_pengajuan'].label = 'Upload Bukti SS Ke Atasan Langsung'
        self.fields['file_pengajuan'].help_text = 'Maksimal 5MB. Format: PDF, DOC, DOCX, JPG, PNG'
    
    def clean_file_pengajuan(self):
        file = self.cleaned_data.get('file_pengajuan')
        if file:
            validate_file_size(file)
            validate_file_extension(file)
        return file

class CutiForm(forms.ModelForm):
    class Meta:
        model = Cuti
        fields = ['jenis_cuti', 'tanggal_mulai', 'tanggal_selesai', 'file_pengajuan', 'file_dokumen_formal']
        widgets = {
            'jenis_cuti': forms.Select(attrs={'class': 'form-control'}),
            'tanggal_mulai': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'tanggal_selesai': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'file_pengajuan': forms.ClearableFileInput(attrs={
                'class': 'form-control',
                'accept': '.pdf,.doc,.docx,.jpg,.jpeg,.png'
            }), 
            'file_dokumen_formal': forms.ClearableFileInput(attrs={
                'class': 'form-control',
                'accept': '.pdf,.doc,.docx'
            }),
            'jenis_pengajuan': forms.Select(attrs={'class': 'form-control'}),  # Tambahkan widget
        }
        
    def __init__(self, *args, **kwargs):
        self.karyawan = kwargs.pop('karyawan', None)
        super(CutiForm, self).__init__(*args, **kwargs)
        for field in self.fields.values():
            field.required = True
        self.fields['file_pengajuan'].label = 'Upload Bukti Capture Approval Cuti/Izin dari Atasan'
        self.fields['file_dokumen_formal'].label = 'Upload File Cuti/Izin yang Telah Ditandatangani (docx)'
        self.fields['file_pengajuan'].help_text = 'Maksimal 5MB. Format: PDF, DOC, DOCX, JPG, PNG'
        self.fields['file_dokumen_formal'].help_text = 'Maksimal 5MB. Format: PDF, DOC, DOCX'
    
    def clean_file_pengajuan(self):
        file = self.cleaned_data.get('file_pengajuan')
        if file:
            validate_file_size(file)
            validate_file_extension(file)
        return file
    
    def clean_file_dokumen_formal(self):
        file = self.cleaned_data.get('file_dokumen_formal')
        if file:
            validate_file_size(file)
            validate_file_extension(file)
        return file
        
    def clean(self):
        cleaned_data = super().clean()
        tanggal_mulai = cleaned_data.get('tanggal_mulai')
        tanggal_selesai = cleaned_data.get('tanggal_selesai')
        
        if tanggal_mulai and tanggal_selesai:
            # Validasi tanggal mulai tidak lebih besar dari tanggal selesai
            if tanggal_mulai > tanggal_selesai:
                raise ValidationError('Tanggal mulai tidak boleh lebih besar dari tanggal selesai.')
            
            # Validasi tanggal tidak boleh di masa lalu
            from datetime import date
            today = date.today()
            if tanggal_mulai < today:
                raise ValidationError('Tidak dapat mengajukan cuti untuk tanggal yang sudah lewat.')
            
            # Validasi tanggal tidak boleh bentrok dengan pengajuan cuti yang sudah ada
            if self.karyawan:
                from apps.hrd.models import Cuti
                from django.db.models import Q
                
                # Cek apakah ada cuti yang sudah diajukan pada rentang tanggal yang sama
                existing_cuti = Cuti.objects.filter(
                    id_karyawan=self.karyawan,
                    status__in=['menunggu', 'disetujui'],
                ).filter(
                    # Cek apakah ada overlap dengan cuti yang sudah ada
                    Q(tanggal_mulai__lte=tanggal_selesai, tanggal_selesai__gte=tanggal_mulai)
                )
                
                # Jika ini adalah edit form, exclude instance saat ini
                if self.instance.pk:
                    existing_cuti = existing_cuti.exclude(pk=self.instance.pk)
                
                if existing_cuti.exists():
                    conflicting_cuti = existing_cuti.first()
                    raise ValidationError(
                        f'Anda sudah mengajukan cuti pada tanggal {conflicting_cuti.tanggal_mulai} sampai {conflicting_cuti.tanggal_selesai} dengan status {conflicting_cuti.get_status_display()}.'
                    )
            
            # Hitung jumlah hari cuti
            jumlah_hari = (tanggal_selesai - tanggal_mulai).days + 1
            
            # Cek jatah cuti yang tersedia untuk cuti tahunan
            if self.karyawan and cleaned_data.get('jenis_cuti') == 'tahunan':
                # Import yang diperlukan
                from apps.hrd.models import JatahCuti
                from datetime import datetime
                
                # Ambil jatah cuti dari tahun sekarang dan tahun sebelumnya saja
                tahun_sekarang = datetime.now().year
                tahun_sebelumnya = tahun_sekarang - 1
                
                jatah_cuti_list = JatahCuti.objects.filter(
                    karyawan=self.karyawan, 
                    tahun__in=[tahun_sebelumnya, tahun_sekarang]
                ).order_by('tahun')
                
                # Hitung total sisa cuti dari 2 tahun (sebelumnya + sekarang)
                total_sisa_cuti = sum(jc.sisa_cuti for jc in jatah_cuti_list if jc.sisa_cuti > 0)
                
                if total_sisa_cuti < jumlah_hari:
                    # Buat pesan error yang detail per tahun
                    detail_sisa = []
                    for jc in jatah_cuti_list:
                        if jc.sisa_cuti > 0:
                            detail_sisa.append(f"{jc.tahun} tersisa {jc.sisa_cuti} hari")
                    
                    detail_text = ", ".join(detail_sisa) if detail_sisa else "tidak ada sisa cuti"
                    raise ValidationError(
                        f'Pengajuan melebihi jatah cuti: {detail_text}. Total dibutuhkan: {jumlah_hari} hari.'
                    )
        
        return cleaned_data

class IzinForm(forms.ModelForm):
    class Meta:
        model = Izin
        fields = ['jenis_izin', 'tanggal_izin', 'alasan', 'file_pengajuan', 'kompensasi_lembur']
        widgets = {
            'jenis_izin': forms.Select(attrs={'class': 'form-control'}),
            'tanggal_izin': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'alasan': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'file_pengajuan': forms.ClearableFileInput(attrs={
                'class': 'form-control',
                'accept': '.pdf,.doc,.docx,.jpg,.jpeg,.png',
                'required': True
            }),
            'kompensasi_lembur': forms.RadioSelect(
                choices=Izin.KOMPENSASI_LEMBUR_CHOICES,
                attrs={'class': 'custom-radio-group'}
            ),
        }
        
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['file_pengajuan'].label = 'Upload Bukti SS Ke Atasan Langsung'
        self.fields['file_pengajuan'].help_text = 'Maksimal 5MB. Format: PDF, DOC, DOCX, JPG, PNG'
        # Membuat field file_pengajuan menjadi wajib diisi
        self.fields['file_pengajuan'].required = True
    
    def clean_file_pengajuan(self):
        file = self.cleaned_data.get('file_pengajuan')
        # Validasi bahwa file harus ada
        if not file:
            raise forms.ValidationError('Bukti SS ke atasan langsung wajib diupload.')
        
        # Validasi ukuran dan ekstensi file
        validate_file_size(file)
        validate_file_extension(file)
        return file
        
