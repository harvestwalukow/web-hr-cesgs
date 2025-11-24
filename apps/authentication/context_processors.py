def sidebar_menu(request):
    user = request.user
    sidebar = []

    if user.is_authenticated:
        if user.role == 'HRD':
            sidebar = [
                {'name': 'Dashboard', 'url': '/hrd/', 'icon': 'fa fa-home text-primary'},
                {'name': 'Manajemen Karyawan', 'url': '/hrd/manajemen-karyawan/', 'icon': 'ni ni-badge text-success'},
                {
                    'name': 'Absensi',
                    'icon': 'ni ni-camera-compact text-danger',
                    'submenu': [
                        {'name': 'Upload Data Absensi', 'url': '/absensi/upload/', 'icon': 'ni ni-cloud-upload-96 text-info'},
                        {'name': 'Rules Absensi', 'url': '/absensi/rules/', 'icon': 'ni ni-settings text-warning'},
                        {'name': 'Riwayat Absensi Magang', 'url': '/absensi/magang-hr/', 'icon': 'fa fa-history text-dark'},
                    ]
                },
                {
                    'name': 'Cuti',
                    'icon': 'ni ni-calendar-grid-58 text-warning',
                    'submenu': [
                        {'name': 'Approval Cuti', 'url': '/hrd/approval-cuti/', 'icon': 'fa fa-circle text-dark'},
                        {'name': 'Pengajuan Cuti', 'url': '/karyawan/pengajuan-cuti/', 'icon': 'fa fa-circle text-dark'},
                        {'name': 'Detail Riwayat Cuti', 'url': '/karyawan/riwayat-cuti-detail/', 'icon': 'fas fa-history'},
                        {'name': 'Jatah Cuti Karyawan', 'url': '/hrd/laporan-jatah-cuti/', 'icon': 'fa fa-circle text-dark'},
                        {'name': 'Input Cuti Bersama', 'url': '/hrd/cuti-bersama/', 'icon': 'fa fa-circle text-dark'},
                        {'name': 'Tidak Ambil Cuti Bersama', 'url': '/karyawan/tidak-ambil-cuti/', 'icon': 'fa fa-circle text-dark'},
                    ]
                },
                {
                    'name': 'Izin',
                    'icon': 'ni ni-time-alarm text-info',
                    'submenu': [
                        {'name': 'Approval Izin', 'url': '/hrd/approval-izin/', 'icon': 'fa fa-circle text-dark'},
                        {'name': 'Pengajuan Izin', 'url': '/karyawan/pengajuan-izin/', 'icon': 'fa fa-circle text-dark'},
                    ]
                },
                {'name': 'Booking Ruang Rapat', 'url': '/hrd/booking-ruang-rapat/', 'icon': 'ni ni-building text-purple'},
                {'name': 'Edit Profil', 'url': '/profil/', 'icon': 'ni ni-single-02 text-primary'},
            ]

        # Kode untuk role lain tetap sama
        elif user.role == 'Karyawan Tetap':
            sidebar = [
                {'name': 'Dashboard', 'url': '/karyawan/', 'icon': 'fa fa-home text-primary'},
                {'name': 'Edit Profil', 'url': '/profil/', 'icon': 'ni ni-single-02 text-primary'},
                {
                    'name': 'Cuti',
                    'icon': 'ni ni-calendar-grid-58 text-warning',
                    'submenu': [
                        {'name': 'Pengajuan Cuti', 'url': '/karyawan/pengajuan-cuti/', 'icon': 'fa fa-circle text-dark'},
                        {'name': 'Detail Riwayat Cuti', 'url': '/karyawan/riwayat-cuti-detail/', 'icon': 'fas fa-history'},
                        {'name': 'Tidak Ambil Cuti Bersama', 'url': '/karyawan/tidak-ambil-cuti/', 'icon': 'fa fa-circle text-dark'},
                    ]
                },
                {
                    'name': 'Izin',
                    'icon': 'ni ni-time-alarm text-info',
                    'submenu': [
                        {'name': 'Pengajuan Izin', 'url': '/karyawan/pengajuan-izin/', 'icon': 'fa fa-circle text-dark'},
                    ]
                },
                {'name': 'Booking Ruang Rapat', 'url': '/hrd/booking-ruang-rapat/', 'icon': 'ni ni-building text-purple'},
            ]

        elif user.role in ['Magang', 'Part Time', 'Freelance', 'Project']:
            sidebar = [
                {'name': 'Dashboard', 'url': '/magang/', 'icon': 'fa fa-home text-primary'},
                {'name': 'Edit Profil', 'url': '/magang/edit-profil/', 'icon': 'ni ni-single-02 text-primary'},
                {
                    'name': 'Absensi Wajah',
                    'icon': 'ni ni-camera-compact text-danger',
                    'submenu': [
                        {'name': 'Absen Masuk', 'url': '/absensi/magang/absen/', 'icon': 'fa fa-circle text-dark'},
                        {'name': 'Absen Pulang', 'url': '/absensi/magang/absen-pulang/', 'icon': 'fa fa-circle text-dark'},
                        {'name': 'Daftar Wajah', 'url': '/absensi/magang/ambil-wajah/', 'icon': 'fa fa-circle text-dark'},
                        {'name': 'Riwayat Absensi', 'url': '/absensi/magang/riwayat/', 'icon': 'fa fa-circle text-dark'},
                    ]
                },
            ]

    return {'sidebar_menu': sidebar}
