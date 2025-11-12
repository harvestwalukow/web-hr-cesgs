import os
import cv2
import base64
import numpy as np
import json
from datetime import datetime, time
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponse
from django.conf import settings
from django.contrib import messages
from django.views.decorators.csrf import csrf_exempt
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut, GeocoderServiceError
from apps.authentication.decorators import role_required
from apps.hrd.models import Karyawan
from ..models import AbsensiMagang, FaceData, FaceEncoding
from ..forms import FaceDataForm, AbsensiMagangForm, AbsensiPulangForm

# Konstanta untuk path
FACE_DATA_DIR = os.path.join(settings.MEDIA_ROOT, 'face_data')

# Pastikan direktori ada
os.makedirs(FACE_DATA_DIR, exist_ok=True)

# Fungsi untuk mendapatkan alamat dari koordinat
def get_address_from_coordinates(latitude, longitude):
    geolocator = Nominatim(user_agent="cesgs_web_hr_app", timeout=10)
    try:
        location = geolocator.reverse(f"{latitude}, {longitude}", exactly_one=True, language='id')
        if location:
            return location.address
        else:
            print(f"DEBUG: Location found: {location.address}")
        return location.address
    except (GeocoderTimedOut, GeocoderServiceError) as e:
        print(f"DEBUG: Geocoding error for {latitude}, {longitude}: {e}")
        return None
    except Exception as e:
        print(f"DEBUG: An unexpected error occurred during geocoding for {latitude}, {longitude}: {e}")
        return None

# Tambahkan import di bagian atas file
import face_recognition
import pickle

@login_required
@role_required(['Magang', 'Part Time', 'Freelance', 'Project'])
def ambil_wajah_view(request):
    """View untuk halaman pengambilan data wajah"""
    try:
        karyawan = Karyawan.objects.get(user=request.user)
    except Karyawan.DoesNotExist:
        messages.error(request, 'Data karyawan tidak ditemukan')
        return redirect('magang_dashboard')
    
    # Cek apakah sudah pernah mendaftar wajah
    face_encoding = FaceEncoding.objects.filter(user=karyawan).first()
    
    if request.method == 'POST':
        form = FaceDataForm(request.POST, user=request.user)
        if form.is_valid():
            messages.success(request, 'Berhasil menyimpan data wajah')
            return redirect('magang_dashboard')
    else:
        form = FaceDataForm(user=request.user)
    
    context = {
        'form': form,
        'karyawan': karyawan,
        'face_encoding': face_encoding,
        'title': 'Pendaftaran Wajah'
    }
    return render(request, 'absensi/ambil_wajah.html', context)

@csrf_exempt
@login_required
@role_required(['Magang', 'Part Time', 'Freelance', 'Project'])
def save_face_data(request):
    """API untuk menyimpan data wajah dari webcam"""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            karyawan_id = data.get('karyawan_id')
            image_data = data.get('image_data')
            
            # Validasi data
            if not karyawan_id or not image_data:
                return JsonResponse({'status': 'error', 'message': 'Data tidak lengkap'}, status=400)
            
            # Pastikan karyawan ada dan milik user yang login
            try:
                karyawan = Karyawan.objects.get(id=karyawan_id, user=request.user)
            except Karyawan.DoesNotExist:
                return JsonResponse({'status': 'error', 'message': 'Data karyawan tidak valid'}, status=403)
            
            # Decode base64 image
            image_data = image_data.split(',')[1] if ',' in image_data else image_data
            image_bytes = base64.b64decode(image_data)
            
            # Konversi ke numpy array untuk face_recognition
            nparr = np.frombuffer(image_bytes, np.uint8)
            img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            
            # Konversi BGR ke RGB (face_recognition menggunakan RGB)
            rgb_img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
            
            # Deteksi wajah dan ekstrak encoding
            face_locations = face_recognition.face_locations(rgb_img)
            
            if not face_locations:
                return JsonResponse({'status': 'error', 'message': 'Tidak ada wajah terdeteksi'}, status=400)
            
            # Ambil encoding wajah pertama yang terdeteksi
            face_encodings = face_recognition.face_encodings(rgb_img, face_locations)
            
            if not face_encodings:
                return JsonResponse({'status': 'error', 'message': 'Gagal mengekstrak fitur wajah'}, status=400)
            
            # Simpan encoding ke database
            face_encoding_bytes = pickle.dumps(face_encodings[0])
            
            # Update atau buat baru face encoding
            face_encoding, created = FaceEncoding.objects.update_or_create(
                user=karyawan,
                defaults={'encoding': face_encoding_bytes}
            )
            
            # Simpan juga gambar wajah untuk referensi visual
            user_face_dir = os.path.join(FACE_DATA_DIR, str(karyawan.id))
            os.makedirs(user_face_dir, exist_ok=True)
            
            # Ubah format nama file sesuai dengan yang diharapkan oleh fungsi training
            image_path = os.path.join(user_face_dir, f'User.{karyawan.id}.1.jpg')
            with open(image_path, 'wb') as f:
                f.write(image_bytes)
            
            # Buat atau update FaceData untuk karyawan ini
            face_data, created = FaceData.objects.update_or_create(
                id_karyawan=karyawan,
                defaults={
                    'path_dataset': user_face_dir,
                    'is_active': True
                }
            )
            
            return JsonResponse({
                'status': 'success', 
                'message': 'Data wajah berhasil disimpan',
                'path': image_path
            })
            
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=500)
    
    return JsonResponse({'status': 'error', 'message': 'Metode tidak diizinkan'}, status=405)

@login_required
@role_required(['Magang', 'Part Time', 'Freelance', 'Project'])
def absen_view(request):
    """View untuk halaman absensi dengan pengenalan wajah"""
    try:
        karyawan = Karyawan.objects.get(user=request.user)
    except Karyawan.DoesNotExist:
        messages.error(request, 'Data karyawan tidak ditemukan')
        return redirect('magang_dashboard')
    
    # Cek apakah sudah absen hari ini
    today = datetime.now().date()
    absensi_hari_ini = AbsensiMagang.objects.filter(
        id_karyawan=karyawan,
        tanggal=today
    ).first()
    
    # Cek apakah sudah mendaftarkan wajah
    face_data = FaceData.objects.filter(id_karyawan=karyawan).first()
    if not face_data:
        messages.warning(request, 'Anda belum mendaftarkan data wajah. Silakan daftar terlebih dahulu.')
        return redirect('ambil_wajah')
    
    # Di dalam fungsi absen_view, sebelum menyimpan absensi
    # Tambahkan validasi untuk keterangan
    if request.method == 'POST':
        form = AbsensiMagangForm(request.POST, user=request.user)
        if form.is_valid():
            if absensi_hari_ini:
                messages.info(request, 'Anda sudah melakukan absensi hari ini')
                return redirect('magang_dashboard')
            
            # Validasi keterangan
            keterangan = form.cleaned_data.get('keterangan')
            if not keterangan:
                messages.error(request, 'Keterangan wajib diisi')
                return redirect('absen_magang')
                
            print(f'keterangan: {keterangan}')
            # VALIDASI WAJAH SEBELUM PROSES ABSENSI
            screenshot_data = request.POST.get('screenshot_data')
            if screenshot_data:
                try:
                    # Decode base64 image untuk validasi
                    image_data = screenshot_data.split(',')[1] if ',' in screenshot_data else screenshot_data
                    image_bytes = base64.b64decode(image_data)
                    nparr = np.frombuffer(image_bytes, np.uint8)
                    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
                    
                    # Konversi BGR ke RGB (face_recognition menggunakan RGB)
                    rgb_img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
                    
                    # Deteksi wajah menggunakan face_recognition
                    face_locations = face_recognition.face_locations(rgb_img)
                    
                    if len(face_locations) == 0:
                        messages.error(request, 'Wajah tidak terdeteksi dalam screenshot. Silakan coba lagi dengan posisi wajah yang jelas.')
                        return redirect('absen_magang')
                    
                    # Ambil wajah terbesar (diasumsikan paling dekat dengan kamera)
                    face_location = max(face_locations, key=lambda rect: (rect[2] - rect[0]) * (rect[3] - rect[1]))
                    top, right, bottom, left = face_location
                    
                    # Ekstrak encoding wajah
                    face_encodings = face_recognition.face_encodings(rgb_img, [face_location])
                    
                    if not face_encodings:
                        messages.error(request, 'Gagal mengekstrak fitur wajah. Silakan coba lagi dengan pencahayaan yang lebih baik.')
                        return redirect('absen_magang')
                    
                    current_encoding = face_encodings[0]
                    
                    # Dapatkan encoding wajah karyawan yang login dari database
                    try:
                        face_encoding_obj = FaceEncoding.objects.get(user=karyawan, is_active=True)
                        stored_encoding = pickle.loads(face_encoding_obj.encoding)
                        
                        # Hitung jarak (semakin kecil semakin mirip)
                        face_distance = face_recognition.face_distance([stored_encoding], current_encoding)[0]
                        
                        # Konversi jarak ke persentase kecocokan (0 = identik, 1 = sangat berbeda)
                        confidence = (1 - face_distance) * 100
                        
                        print(f"DEBUG: ID login: {karyawan.id}, ID wajah: {face_encoding_obj.user.id}, confidence: {confidence:.2f}%")
                        
                        # Validasi apakah wajah sesuai dengan user yang login
                        if confidence < 50:  # Threshold 50%
                            messages.error(request, f'Validasi wajah gagal. Tingkat kecocokan terlalu rendah ({confidence:.2f}%). Silakan coba lagi dengan pencahayaan yang lebih baik.')
                            return redirect('absen_magang')
                        
                        print(f"DEBUG: Face validation successful - User: {karyawan.nama}, Confidence: {confidence:.2f}%")
                        
                    except FaceEncoding.DoesNotExist:
                        messages.error(request, 'Data encoding wajah tidak ditemukan. Silakan daftar ulang wajah Anda terlebih dahulu.')
                        return redirect('ambil_wajah')
                    
                except Exception as e:
                    print(f"ERROR: Face validation failed - {str(e)}")
                    messages.error(request, f'Terjadi kesalahan saat validasi wajah: {str(e)}. Silakan coba lagi.')
                    return redirect('absen_magang')
            else:
                messages.error(request, 'Screenshot wajah diperlukan untuk absensi. Silakan aktifkan kamera dan ambil foto wajah Anda.')
                return redirect('absen_magang')

            # Proses absensi jika validasi wajah berhasil
            absensi = form.save(commit=False)
            absensi.id_karyawan = karyawan
            absensi.tanggal = today
            current_time = datetime.now().time()
            absensi.jam_masuk = current_time
            # Simpan keterangan
            absensi.keterangan = keterangan
            
            # Kode lainnya tetap sama
            # Tentukan waktu batas bawah dan atas
            start_time = time(6, 0)     # 06:00
            cutoff_time = time(9, 15)   # 09:15

            # Tentukan status
            if start_time <= current_time <= cutoff_time:
                absensi.status = 'Tepat waktu'
            else:
                absensi.status = 'Terlambat'

            # Ambil latitude dan longitude dari form
            latitude = request.POST.get('latitude')
            longitude = request.POST.get('longitude')

            if latitude and longitude:
                absensi.lokasi_masuk = f"{latitude}, {longitude}"
                # Dapatkan alamat dari koordinat
                address = get_address_from_coordinates(latitude, longitude)
                print(f"DEBUG: Retrieved address for {latitude}, {longitude}: {address}")
                if address:
                    absensi.alamat_masuk = address
                else:
                    absensi.alamat_masuk = "Alamat tidak ditemukan"
            else:
                absensi.lokasi_masuk = "Koordinat tidak tersedia"
                absensi.alamat_masuk = "Alamat tidak tersedia"
            
            # Simpan screenshot jika ada (sudah divalidasi di atas)
            if screenshot_data:
                # Decode base64 image
                screenshot_data = screenshot_data.split(',')[1] if ',' in screenshot_data else screenshot_data
                image_data = base64.b64decode(screenshot_data)
                
                # Buat path untuk screenshot
                screenshot_path = f'absensi_screenshots/masuk/{karyawan.id}_{today.strftime("%Y%m%d")}_{datetime.now().strftime("%H%M%S")}.jpg'
                
                # Simpan file menggunakan default_storage
                screenshot_file = ContentFile(image_data)
                path = default_storage.save(screenshot_path, screenshot_file)
                
                absensi.screenshot_masuk = path
            
            absensi.save()
            print(f"DEBUG: Absensi saved with lokasi_masuk: {absensi.lokasi_masuk} and alamat_masuk: {absensi.alamat_masuk}")
            messages.success(request, f'Absensi berhasil disimpan untuk {karyawan.nama}')
            return redirect('magang_dashboard')
    else:
        form = AbsensiMagangForm(user=request.user)
    
    context = {
        'form': form,
        'karyawan': karyawan,
        'absensi_hari_ini': absensi_hari_ini,
        'title': 'Absensi Masuk'
    }
    return render(request, 'absensi/absen.html', context)

@login_required
@role_required(['Magang', 'Part Time', 'Freelance', 'Project'])
def absen_pulang_view(request):
    """View untuk halaman absensi pulang dengan pengenalan wajah"""
    try:
        karyawan = Karyawan.objects.get(user=request.user)
    except Karyawan.DoesNotExist:
        messages.error(request, 'Data karyawan tidak ditemukan')
        return redirect('magang_dashboard')
    
    # Cek waktu saat ini, hanya boleh absen pulang setelah jam 16:00 WIB
    current_time = datetime.now().time()
    min_checkout_time = time(16, 0)  # 16:00 WIB
    
    if current_time < min_checkout_time:
        messages.warning(request, f'Absen pulang hanya dapat dilakukan setelah jam 16:00 WIB. Sekarang jam {current_time.strftime("%H:%M")} WIB')
        return redirect('magang_dashboard')
    
    # Cek apakah sudah absen masuk hari ini
    today = datetime.now().date()
    absensi_hari_ini = AbsensiMagang.objects.filter(
        id_karyawan=karyawan,
        tanggal=today
    ).first()
    
    if not absensi_hari_ini:
        messages.error(request, 'Anda belum melakukan absen masuk hari ini. Absen pulang tidak dapat dilakukan.')
        return redirect('magang_dashboard')
    
    # Cek apakah sudah mendaftarkan wajah
    face_data = FaceData.objects.filter(id_karyawan=karyawan).first()
    if not face_data:
        messages.warning(request, 'Anda belum mendaftarkan data wajah. Silakan daftar terlebih dahulu.')
        return redirect('ambil_wajah')
    
    if request.method == 'POST':
        form = AbsensiPulangForm(request.POST, user=request.user)
        if form.is_valid():
            # VALIDASI WAJAH SEBELUM PROSES ABSENSI PULANG
            screenshot_data = request.POST.get('screenshot_data')
            if screenshot_data:
                try:
                    # Decode base64 image untuk validasi
                    image_data = screenshot_data.split(',')[1] if ',' in screenshot_data else screenshot_data
                    image_bytes = base64.b64decode(image_data)
                    nparr = np.frombuffer(image_bytes, np.uint8)
                    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
                    
                    # Konversi BGR ke RGB (face_recognition menggunakan RGB)
                    rgb_img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
                    
                    # Deteksi wajah menggunakan face_recognition
                    face_locations = face_recognition.face_locations(rgb_img)
                    
                    if len(face_locations) == 0:
                        messages.error(request, 'Wajah tidak terdeteksi dalam screenshot. Silakan coba lagi dengan posisi wajah yang jelas.')
                        return redirect('absen_pulang_magang')
                    
                    # Ambil wajah terbesar (diasumsikan paling dekat dengan kamera)
                    face_location = max(face_locations, key=lambda rect: (rect[2] - rect[0]) * (rect[3] - rect[1]))
                    top, right, bottom, left = face_location
                    
                    # Ekstrak encoding wajah
                    face_encodings = face_recognition.face_encodings(rgb_img, [face_location])
                    
                    if not face_encodings:
                        messages.error(request, 'Gagal mengekstrak fitur wajah. Silakan coba lagi dengan pencahayaan yang lebih baik.')
                        return redirect('absen_pulang_magang')
                    
                    current_encoding = face_encodings[0]
                    
                    # Dapatkan encoding wajah karyawan yang login dari database
                    try:
                        face_encoding_obj = FaceEncoding.objects.get(user=karyawan, is_active=True)
                        stored_encoding = pickle.loads(face_encoding_obj.encoding)
                        
                        # Hitung jarak (semakin kecil semakin mirip)
                        face_distance = face_recognition.face_distance([stored_encoding], current_encoding)[0]
                        
                        # Konversi jarak ke persentase kecocokan (0 = identik, 1 = sangat berbeda)
                        confidence = (1 - face_distance) * 100
                        
                        print(f"DEBUG: ID login: {karyawan.id}, ID wajah: {face_encoding_obj.user.id}, confidence: {confidence:.2f}%")
                        
                        # Validasi apakah wajah sesuai dengan user yang login
                        if confidence < 50:  # Threshold 50%
                            messages.error(request, f'Validasi wajah gagal. Tingkat kecocokan terlalu rendah ({confidence:.2f}%). Silakan coba lagi dengan pencahayaan yang lebih baik.')
                            return redirect('absen_pulang_magang')
                        
                        print(f"DEBUG: Face validation successful - User: {karyawan.nama}, Confidence: {confidence:.2f}%")
                        
                    except FaceEncoding.DoesNotExist:
                        messages.error(request, 'Data encoding wajah tidak ditemukan. Silakan daftar ulang wajah Anda terlebih dahulu.')
                        return redirect('ambil_wajah')
                    
                except Exception as e:
                    print(f"ERROR: Face validation failed - {str(e)}")
                    messages.error(request, f'Terjadi kesalahan saat validasi wajah: {str(e)}. Silakan coba lagi.')
                    return redirect('absen_pulang_magang')
            else:
                messages.error(request, 'Screenshot wajah diperlukan untuk absensi. Silakan aktifkan kamera dan ambil foto wajah Anda.')
                return redirect('absen_pulang_magang')

            # Proses absensi pulang jika validasi wajah berhasil
            # Update data absensi yang sudah ada
            current_time = datetime.now().time()
            absensi_hari_ini.jam_pulang = current_time

            # Ambil latitude dan longitude dari form
            latitude = request.POST.get('latitude')
            longitude = request.POST.get('longitude')

            if latitude and longitude:
                absensi_hari_ini.lokasi_pulang = f"{latitude}, {longitude}"
                # Dapatkan alamat dari koordinat
                address = get_address_from_coordinates(latitude, longitude)
                print(f"DEBUG: Retrieved address for {latitude}, {longitude}: {address}")
                if address:
                    absensi_hari_ini.alamat_pulang = address
                else:
                    absensi_hari_ini.alamat_pulang = "Alamat tidak ditemukan"
            else:
                absensi_hari_ini.lokasi_pulang = "Koordinat tidak tersedia"
                absensi_hari_ini.alamat_pulang = "Alamat tidak tersedia"
            
            # Simpan screenshot jika ada (sudah divalidasi di atas)
            if screenshot_data:
                # Decode base64 image
                screenshot_data = screenshot_data.split(',')[1] if ',' in screenshot_data else screenshot_data
                image_data = base64.b64decode(screenshot_data)
                
                # Buat path untuk screenshot
                screenshot_path = f'absensi_screenshots/pulang/{karyawan.id}_{today.strftime("%Y%m%d")}_{datetime.now().strftime("%H%M%S")}.jpg'
                
                # Simpan file menggunakan default_storage
                screenshot_file = ContentFile(image_data)
                path = default_storage.save(screenshot_path, screenshot_file)
                
                absensi_hari_ini.screenshot_pulang = path
            
            absensi_hari_ini.save()
            print(f"DEBUG: Absensi pulang saved with lokasi: {absensi_hari_ini.lokasi_pulang} and alamat: {absensi_hari_ini.alamat_pulang}")
            messages.success(request, f'Absensi pulang berhasil disimpan untuk {karyawan.nama}')
            return redirect('magang_dashboard')
    else:
        form = AbsensiMagangForm(user=request.user)
    
    context = {
        'form': form,
        'karyawan': karyawan,
        'absensi_hari_ini': absensi_hari_ini,
        'title': 'Absensi Pulang'
    }
    return render(request, 'absensi/absen_pulang.html', context)

@csrf_exempt
@login_required
@role_required(['Magang', 'Part Time', 'Freelance', 'Project'])
def verify_face(request):
    """API untuk verifikasi wajah"""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            image_data = data.get('image_data')
            
            # Validasi data
            if not image_data:
                return JsonResponse({'status': 'error', 'message': 'Data tidak lengkap'}, status=400)
            
            # Decode base64 image
            image_data = image_data.split(',')[1] if ',' in image_data else image_data
            image_bytes = base64.b64decode(image_data)
            
            # Konversi ke numpy array
            nparr = np.frombuffer(image_bytes, np.uint8)
            img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            img_display = img.copy()  # Buat salinan untuk ditampilkan dengan anotasi
            
            # Konversi BGR ke RGB (face_recognition menggunakan RGB)
            rgb_img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
            
            # Deteksi wajah
            face_locations = face_recognition.face_locations(rgb_img)
            
            if len(face_locations) == 0:
                return JsonResponse({'status': 'error', 'message': 'Tidak ada wajah terdeteksi'}, status=400)
            
            # Ambil wajah terbesar (diasumsikan paling dekat dengan kamera)
            face_location = max(face_locations, key=lambda rect: (rect[2] - rect[0]) * (rect[3] - rect[1]))
            top, right, bottom, left = face_location
            
            # Ekstrak encoding wajah
            face_encodings = face_recognition.face_encodings(rgb_img, [face_location])
            
            if not face_encodings:
                return JsonResponse({'status': 'error', 'message': 'Gagal mengekstrak fitur wajah'}, status=400)
            
            current_encoding = face_encodings[0]
            
            # Ambil semua encoding wajah dari database
            all_face_encodings = FaceEncoding.objects.filter(is_active=True)
            
            best_match = None
            best_match_distance = 1.0  # Nilai awal (jarak maksimum)
            best_match_karyawan = None
            
            # Bandingkan dengan semua encoding yang ada
            for db_face_encoding in all_face_encodings:
                # Unpickle encoding dari database
                stored_encoding = pickle.loads(db_face_encoding.encoding)
                
                # Hitung jarak (semakin kecil semakin mirip)
                face_distance = face_recognition.face_distance([stored_encoding], current_encoding)[0]
                
                # Update best match jika ditemukan yang lebih baik
                if face_distance < best_match_distance:
                    best_match_distance = face_distance
                    best_match = db_face_encoding
            
            # Konversi jarak ke persentase kecocokan (0 = identik, 1 = sangat berbeda)
            # Rumus: (1 - jarak) * 100
            if best_match:
                confidence = float((1 - best_match_distance) * 100)  # Konversi ke float standar
                best_match_karyawan = best_match.user
                
                # Cek apakah karyawan yang login sesuai dengan wajah yang terdeteksi
                karyawan = Karyawan.objects.get(user=request.user)
                is_authorized = bool(best_match_karyawan.id == karyawan.id and confidence >= 50)  # Konversi ke bool standar
                
                # Tambahkan visualisasi pada gambar
                cv2.rectangle(img_display, (left, top), (right, bottom), (0, 255, 0), 2)
                cv2.putText(img_display, best_match_karyawan.nama, (left, top-10), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (255, 255, 0), 2)
                cv2.putText(img_display, f"{confidence:.2f}%", (left, bottom+30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 0), 2)
                
                # Encode gambar yang sudah diberi anotasi ke base64 untuk dikirim ke frontend
                _, buffer = cv2.imencode('.jpg', img_display)
                img_str = base64.b64encode(buffer).decode('utf-8')
                
                response_data = {
                    'status': 'success',
                    'message': 'Verifikasi wajah berhasil' if is_authorized else 'Wajah terdeteksi tapi tidak diizinkan',
                    'confidence': confidence,
                    'karyawan_id': best_match_karyawan.id,
                    'person_name': best_match_karyawan.nama,
                    'is_authorized': is_authorized,
                    'face_rect': {
                        'x': int(left),
                        'y': int(top),
                        'w': int(right - left),
                        'h': int(bottom - top)
                    },
                    'annotated_image': f'data:image/jpeg;base64,{img_str}'
                }
                
                return JsonResponse(response_data)
            else:
                # Jika tidak ada kecocokan
                return JsonResponse({
                    'status': 'success',
                    'message': 'Wajah terdeteksi tapi tidak dikenal',
                    'confidence': 0,
                    'person_name': None,
                    'is_authorized': False,
                    'face_rect': {
                        'x': int(left),
                        'y': int(top),
                        'w': int(right - left),
                        'h': int(bottom - top)
                    }
                })
            
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=500)
    
    return JsonResponse({'status': 'error', 'message': 'Metode tidak diizinkan'}, status=405)

@login_required
@role_required(['Magang', 'Part Time', 'Freelance', 'Project'])
def riwayat_absensi(request):
    """View untuk menampilkan riwayat absensi karyawan"""
    try:
        karyawan = Karyawan.objects.get(user=request.user)
    except Karyawan.DoesNotExist:
        messages.error(request, 'Data karyawan tidak ditemukan')
        return redirect('magang_dashboard')
    
    # Filter berdasarkan bulan dan tahun jika ada
    bulan = request.GET.get('bulan')
    tahun = request.GET.get('tahun')
    keterangan = request.GET.get('keterangan')
    
    # Buat query dasar
    absensi_query = AbsensiMagang.objects.filter(id_karyawan=karyawan).order_by('-tanggal', '-jam_masuk')
    
    # Terapkan filter
    if bulan and bulan.isdigit():
        absensi_query = absensi_query.filter(tanggal__month=int(bulan))
    
    if tahun and tahun.isdigit():
        absensi_query = absensi_query.filter(tanggal__year=int(tahun))
    
    if keterangan:
        absensi_query = absensi_query.filter(keterangan=keterangan)
    
    # Hitung total untuk statistik
    total_tepat_waktu = absensi_query.filter(status='Tepat waktu').count()
    total_terlambat = absensi_query.filter(status='Terlambat').count()
    total_absensi = absensi_query.count()
    
    # Pagination
    from django.core.paginator import Paginator
    paginator = Paginator(absensi_query, 3)
    page = request.GET.get('page')
    absensi_list = paginator.get_page(page)
    
    # Pilihan bulan dan tahun untuk filter
    months = [
        (1, 'Januari'), (2, 'Februari'), (3, 'Maret'), (4, 'April'),
        (5, 'Mei'), (6, 'Juni'), (7, 'Juli'), (8, 'Agustus'),
        (9, 'September'), (10, 'Oktober'), (11, 'November'), (12, 'Desember')
    ]
    
    # Tahun dari 3 tahun lalu sampai tahun depan
    current_year = datetime.now().year
    years = range(current_year - 3, current_year + 2)
    
    context = {
        'absensi_list': absensi_list,
        'karyawan': karyawan,
        'selected_month': int(bulan) if bulan and bulan.isdigit() else '',
        'selected_year': int(tahun) if tahun and tahun.isdigit() else '',
        'selected_keterangan': keterangan if keterangan else '',
        'months': months,
        'years': years,
        'total_tepat_waktu': total_tepat_waktu,
        'total_terlambat': total_terlambat,
        'total_absensi': total_absensi,
        'title': 'Riwayat Absensi'
    }
    
    return render(request, 'absensi/riwayat_absensi.html', context)