from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.contrib.auth import authenticate, update_session_auth_hash
from apps.hrd.models import Karyawan
from apps.authentication.models import User
from .forms import ProfilForm
import json
import os

@login_required
def profil_saya(request):
    user = request.user

    try:
        karyawan = Karyawan.objects.get(user=user)
    except Karyawan.DoesNotExist:
        messages.error(request, "Profil karyawan belum dibuat. Silakan hubungi HRD.")
        return redirect('home')

    if request.method == 'POST':
        form = ProfilForm(request.POST, instance=karyawan, user=user)

        if form.is_valid():
            try:
                # Simpan data ke Karyawan
                updated_karyawan = form.save(commit=False)
                
                # Pastikan user tetap sama (tidak berubah)
                updated_karyawan.user = user
                
                # Simpan ke database
                updated_karyawan.save()

                messages.success(request, 'Profil berhasil diperbarui.')
                return redirect('profil_saya')
            except Exception as e:
                messages.error(request, f'Terjadi kesalahan saat menyimpan profil: {str(e)}')
        else:
            # Tampilkan error spesifik dari form
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f'{field}: {error}')
    else:
        form = ProfilForm(instance=karyawan, user=user)

    return render(request, 'profil/profil.html', {
        'form': form,
        'karyawan': karyawan,
        'user': user,
    })

@login_required
def ubah_password(request):
    if request.method == 'POST':
        old_password = request.POST.get('old_password')
        new_password1 = request.POST.get('new_password1')
        new_password2 = request.POST.get('new_password2')
        
        # Validasi password lama
        if not authenticate(username=request.user.email, password=old_password):
            messages.error(request, 'Password lama yang Anda masukkan salah.')
            return redirect('profil_saya')
        
        # Validasi password baru
        if new_password1 != new_password2:
            messages.error(request, 'Password baru dan konfirmasi password tidak cocok.')
            return redirect('profil_saya')
        
        if len(new_password1) < 8:
            messages.error(request, 'Password baru harus minimal 8 karakter.')
            return redirect('profil_saya')
        
        # Update password
        user = request.user
        user.set_password(new_password1)
        user.save()
        
        # Update session agar user tidak logout
        update_session_auth_hash(request, user)
        
        messages.success(request, 'Password berhasil diubah!')
        return redirect('profil_saya')
    
    return redirect('profil_saya')
