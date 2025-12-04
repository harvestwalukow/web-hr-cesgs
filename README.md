# CESGS Web HR - Sistem Manajemen Sumber Daya Manusia

## 📋 Deskripsi Project

CESGS Web HR adalah sistem manajemen sumber daya manusia berbasis web yang dikembangkan menggunakan Django. Sistem ini menyediakan solusi lengkap untuk mengelola karyawan, absensi, cuti, izin, dan berbagai aspek HR lainnya dengan teknologi face recognition untuk absensi.

## 🚀 Fitur Utama

### 👥 Manajemen Karyawan
- **Multi-role System**: HRD, Fulltime, Magang, Part Time, Freelance, Project
- **Profil Karyawan Lengkap**: Data personal, jabatan, divisi, kontrak
- **Status Keaktifan**: Tracking status aktif/non-aktif karyawan
- **Dashboard Ulang Tahun**: Notifikasi ulang tahun karyawan

### 📅 Sistem Absensi
- **Face Recognition**: Teknologi pengenalan wajah untuk absensi
- **Absensi Real-time**: Jam masuk dan keluar dengan screenshot
- **Geolocation**: Tracking lokasi saat absensi (WFO/WFH)
- **Rules Engine**: Aturan jam kerja, toleransi keterlambatan
- **Multi-status**: Tepat Waktu, Terlambat, Izin, Sakit, Cuti, Libur

### 🏖️ Manajemen Cuti
- **Sistem Jatah Cuti**: Tracking sisa cuti per tahun
- **Approval Workflow**: Sistem persetujuan HRD
- **Cuti Bersama**: Manajemen hari libur nasional
- **Export Excel**: Laporan riwayat cuti

### 📝 Sistem Izin
- **Jenis Izin**: Izin Telat, Izin WFH
- **Approval System**: Persetujuan dari HRD
- **File Upload**: Dokumen pendukung
- **Feedback System**: Komentar dari HRD

### 📊 Dashboard & Analytics
- **Dashboard HRD**: Statistik lengkap karyawan, cuti, absensi
- **Calendar View**: Visualisasi cuti, izin, dan ulang tahun
- **Top Performance**: Ranking karyawan tepat waktu
- **Charts & Graphs**: Analisis data per bulan/tahun
- **Real-time Notifications**: Sistem notifikasi terintegrasi

### 🔔 Sistem Notifikasi
- **Real-time Alerts**: Notifikasi pengajuan cuti/izin
- **Email Integration**: Notifikasi via email
- **Status Updates**: Update status approval

## 🛠️ Teknologi yang Digunakan

### Backend
- **Framework**: Django 3.2.6
- **Database**: PostgreSQL
- **Authentication**: Custom User Model dengan role-based access
- **File Storage**: Django Media Files
- **Task Scheduling**: Django-cron

### Frontend
- **Template Engine**: Django Templates
- **UI Framework**: Argon Dashboard
- **Calendar**: FullCalendar 6.1.17
- **Charts**: Chart.js integration
- **Responsive Design**: Bootstrap-based


## 🚀 Cara Menjalankan Aplikasi

**Software yang Diperlukan:**
- Git
- Python 3.10+
- PostgreSQL
- Visual Studio Build Tools (untuk Windows)
- CMake (untuk kompilasi dlib)

### 🔧 Instalasi Lengkap

#### 1. **Persiapan Environment**

```bash
# Install Python 3.10+ dari python.org
# Install PostgreSQL dari postgresql.org
# Install Visual Studio Build Tools
# Install Git dari git-scm.com
```
```

#### 2. **Setup Database PostgreSQL**

```bash
# Masuk ke PostgreSQL console
psql -U postgres

# Buat database dan user
CREATE DATABASE test_db;
CREATE USER test;
```

#### 3. **Clone dan Setup Project**

```bash
# Clone repository
git clone <repository-url>
cd cesgs_web_hr

# Buat virtual environment
python -m venv env

# Aktivasi virtual environment
# Windows:
env\Scripts\activate

# Linux/macOS:
source env/bin/activate

# Upgrade pip
python -m pip install --upgrade pip
```

#### 4. **Install Dependencies**

```bash
# Install semua dependencies
pip install -r requirements.txt
```

#### 5. **Konfigurasi Environment Variables**

```bash
# Copy file environment
copy .env.example .env  # Windows
cp .env.example .env    # Linux/macOS
```

**Edit file `.env`:**
```env
# Security
SECRET_KEY=django-insecure-your-very-long-secret-key-here-change-this-in-production
DEBUG=True
SERVER=127.0.0.1
APP_PORT=8000
MODE=development

# Database Configuration
DB_NAME= 
DB_USER=
DB_PASSWORD=
DB_HOST=
DB_PORT=

# AWS Configuration
bucket_name=
region=
aws_access_key_id=
aws_secret_access_key=
aws_s3_custom_domain=
```

#### 6. **Database Migration**

```bash
# Buat migrations
python manage.py makemigrations

# Jalankan migrations
python manage.py migrate
```

#### 7. **Buat Superuser (Admin)**

```bash
python manage.py createsuperuser
```

**Input yang diperlukan:**
- **Email**: admin@test.com
- **Role**: HRD
- **Password**: [buat password]

#### 8. **Collect Static Files**

Upload static ke S3
```bash
python manage.py collectstatic --noinput
```

Upload static dan bersihkan file lama (opsional)
```bash
python manage.py collectstatic --noinput --clear
```

#### 9. **Setup Cron Jobs**

Jalankan semua cron sekarang (sekali jalan)
```bash
python manage.py runcrons
```

Jalankan cron job loop (berjalan terus-menerus)
```bash
python manage.py cronloop
```

### 🎯 Menjalankan Aplikasi

#### **Development Mode**

```bash
# Pastikan virtual environment aktif
env310\Scripts\activate  # Windows
source env310/bin/activate  # Linux/macOS

# Jalankan development server
python manage.py runserver

# Atau dengan custom host dan port
python manage.py runserver 0.0.0.0:8000
```

### 🌐 Akses Aplikasi

**URLs Utama:**
- **Main App**: http://127.0.0.1:8000

### 🐳 Deployment dengan Docker

#### **Development dengan Docker**

```bash
# Build dan jalankan containers
docker-compose up --build

# Jalankan di background
docker-compose up -d

# Lihat logs
docker-compose logs -f

# Stop containers
docker-compose down
```

---