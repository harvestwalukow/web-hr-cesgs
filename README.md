# CESGS Web HR

## Deskripsi Project

CESGS Web HR adalah sistem manajemen sumber daya manusia berbasis web yang dikembangkan menggunakan Django. Sistem ini menyediakan solusi lengkap untuk mengelola karyawan, absensi, cuti, izin, dan berbagai aspek HR lainnya dengan teknologi location-based via GPS untuk absensi.

## Fitur Utama

### Manajemen Karyawan
- **Multi-role System**: HRD, Fulltime, Magang, Part Time, Freelance, Project
- **Profil Karyawan Lengkap**: Data personal, jabatan, divisi, kontrak
- **Status Keaktifan**: Tracking status aktif/non-aktif karyawan
- **Dashboard Ulang Tahun**: Notifikasi ulang tahun karyawan

### Sistem Absensi
- **Location-based GPS**: Validasi lokasi karyawan saat absensi menggunakan GPS
- **Absensi Real-time**: Jam masuk dan keluar tercatat otomatis
- **Geolocation**: Tracking lokasi saat absensi (WFO/WFA)
- **Rules Engine**: Aturan jam kerja, toleransi keterlambatan
- **Multi-status**: Tepat Waktu, Terlambat, Izin, Sakit, Cuti, Libur

### Manajemen Cuti
- **Sistem Jatah Cuti**: Tracking sisa cuti per tahun
- **Approval Workflow**: Sistem persetujuan HRD
- **Cuti Bersama**: Manajemen hari libur nasional
- **Export Excel**: Laporan riwayat cuti

### Sistem Izin
- **Jenis Izin**: Izin Telat, Izin WFA
- **Approval System**: Persetujuan dari HRD
- **File Upload**: Dokumen pendukung
- **Feedback System**: Komentar dari HRD

### Dashboard & Analytics
- **Dashboard HRD**: Statistik lengkap karyawan, cuti, absensi
- **Calendar View**: Visualisasi cuti, izin, dan ulang tahun
- **Top Performance**: Ranking karyawan tepat waktu
- **Charts & Graphs**: Analisis data per bulan/tahun
- **Real-time Notifications**: Sistem notifikasi terintegrasi

### Sistem Notifikasi
- **Real-time Alerts**: Notifikasi pengajuan cuti/izin
- **Email Integration**: Notifikasi via email
- **Status Updates**: Update status approval

## Teknologi yang Digunakan

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

## Arsitektur Proyek

```
┌─────────────────────────────────────────────────────────────────────────────────────────────┐
│                                      CLIENT REQUEST                                         │
│                              (Browser / Mobile Device)                                      │
└─────────────────────────────────────────────────────────────────────────────────────────────┘
                                               │
                                               ▼
┌─────────────────────────────────────────────────────────────────────────────────────────────┐
│                                        DJANGO CORE                                          │
│                              (core/settings.py, core/urls.py)                               │
├─────────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                             │
│   ┌─────────────────────────────────────────────────────────────────────────────────────┐   │
│   │                                    FRONTEND LAYER                                   │   │
│   │  ┌──────────────────────┐  ┌──────────────────┐  ┌──────────────────────────────┐   │   │
│   │  │ Django Templates     │  │ Argon Dashboard  │  │ FullCalendar + Chart.js      │   │   │
│   │  │ (Server-side render) │  │ (Bootstrap UI)   │  │ (Calendar & Analytics)       │   │   │
│   │  └──────────────────────┘  └──────────────────┘  └──────────────────────────────┘   │   │
│   └─────────────────────────────────────────────────────────────────────────────────────┘   │
│                                              │                                              │
│                                              ▼                                              │
│   ┌─────────────────────────────────────────────────────────────────────────────────────┐   │
│   │                                      APPS LAYER                                     │   │
│   │                                                                                     │   │
│   │   ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐  ┌──────────────┐   │   │
│   │   │ authentication  │  │       hrd       │  │    karyawan     │  │   absensi    │   │   │
│   │   │ ─────────────── │  │ ─────────────── │  │ ─────────────── │  │ ──────────── │   │   │
│   │   │ • User Model    │  │ • Karyawan CRUD │  │ • Dashboard     │  │ • GPS Loc    │   │   │
│   │   │ • Role-based    │  │ • Cuti/Izin     │  │ • Pengajuan     │  │ • Upload     │   │   │
│   │   │ • Login/Logout  │  │ • Jatah Cuti    │  │   Cuti/Izin     │  │ • Rules      │   │   │
│   │   │                 │  │ • Booking Rapat │  │ • Riwayat       │  │ • Riwayat    │   │   │
│   │   └─────────────────┘  └─────────────────┘  └─────────────────┘  └──────────────┘   │   │
│   │                                                                                     │   │
│   │   ┌─────────────────┐  ┌─────────────────┐                                          │   │
│   │   │     profil      │  │   notifikasi    │                                          │   │
│   │   │ ─────────────── │  │ ─────────────── │                                          │   │
│   │   │ • Edit Profil   │  │ • Real-time     │                                          │   │
│   │   │ • Foto Profil   │  │ • Mark as Read  │                                          │   │
│   │   └─────────────────┘  └─────────────────┘                                          │   │
│   └─────────────────────────────────────────────────────────────────────────────────────┘   │
│                                              │                                              │
└──────────────────────────────────────────────┼──────────────────────────────────────────────┘
                                               │
                   ┌───────────────────────────┼───────────────────────────┐
                   │                           │                           │
                   ▼                           ▼                           ▼
┌─────────────────────────────┐  ┌─────────────────────────┐  ┌─────────────────────────────┐
│        DATABASE             │  │        STORAGE          │  │     EXTERNAL SERVICES       │
│ ─────────────────────────── │  │ ─────────────────────── │  │ ─────────────────────────── │
│                             │  │                         │  │                             │
│   ┌─────────────────────┐   │  │   ┌─────────────────┐   │  │   ┌─────────────────────┐   │
│   │    PostgreSQL       │   │  │   │    AWS S3       │   │  │   │  GPS Location        │   │
│   │    ───────────────  │   │  │   │    ─────────    │   │  │   │  ─────────────────  │   │
│   │    • User           │   │  │   │    • Static     │   │  │   │  • Geolocation API  │   │
│   │    • Karyawan       │   │  │   │    • Media      │   │  │   │  • Haversine calc   │   │
│   │    • Cuti/Izin      │   │  │   │    • Uploads    │   │  │   └─────────────────────┘   │
│   │    • Absensi        │   │  │   └─────────────────┘   │  │                             │
│   │    • Absensi        │   │  │                         │  │   ┌─────────────────────┐   │
│   └─────────────────────┘   │  │   ┌─────────────────┐   │  │   │  Fonnte WhatsApp    │   │
│                             │  │   │   Media Files   │   │  │   │  ─────────────────  │   │
│                             │  │   │   (Screenshots) │   │  │   │  • Notifications    │   │
│                             │  │   └─────────────────┘   │  │   └─────────────────────┘   │
└─────────────────────────────┘  └─────────────────────────┘  └─────────────────────────────┘
```

### Struktur Direktori

```
web-hr-cesgs/
├── apps/                          # Aplikasi Django utama
│   ├── authentication/            # Autentikasi & User Management
│   ├── hrd/                       # Modul HRD (admin)
│   ├── karyawan/                  # Modul Karyawan (employee self-service)
│   ├── absensi/                   # Modul Absensi & GPS Location
│   ├── profil/                    # Modul Edit Profil
│   ├── notifikasi/                # Modul Notifikasi
│   ├── utils/                     # Utility functions
│   ├── static/                    # Static files (CSS, JS, images)
│   └── templates/                 # Shared templates
├── core/                          # Django project configuration
│   ├── settings.py                # Main settings
│   ├── urls.py                    # Root URL routing
│   └── wsgi.py                    # WSGI configuration
├── config/                        # Nginx configuration
├── media/                         # User uploaded files
├── requirements.txt               # Python dependencies
├── Dockerfile                     # Docker configuration
├── docker-compose.yml             # Docker compose
└── manage.py                      # Django management script
```

### Struktur Aplikasi

| App | Fungsi |
|-----|--------|
| `authentication` | Custom User model dengan email-based auth dan 6 role |
| `hrd` | Modul admin - manajemen karyawan, approval cuti/izin, booking ruang rapat |
| `karyawan` | Self-service karyawan - pengajuan cuti/izin, dashboard |
| `absensi` | Location-based attendance via GPS, rules absensi, upload data absensi |
| `profil` | Edit profil user |
| `notifikasi` | Sistem notifikasi real-time |

## Cara Menjalankan Aplikasi

**Software yang Diperlukan:**
- Git
- Python 3.10+
- PostgreSQL

### Instalasi Lengkap

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

### Menjalankan Aplikasi

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

### Akses Aplikasi

**URLs Utama:**
- **Main App**: http://127.0.0.1:8000

### Deployment dengan Docker

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