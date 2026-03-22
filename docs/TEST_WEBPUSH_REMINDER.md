# Panduan Testing Web Push & Kelola Notifikasi

## 1. Test Halaman Kelola Notifikasi

**Akses:** Login sebagai **HRD** → sidebar "Kelola Notifikasi" → `/hrd/kelola-notifikasi/`

**Yang bisa diuji:**
- Lihat daftar jadwal (Reminder Absen Masuk, Reminder Klaim Lembur)
- Edit jam dan template pesan
- Aktifkan/nonaktifkan jadwal via toggle
- Simpan perubahan

**Default jadwal (dari migrasi):**
| Tipe | Jam | Status |
|------|-----|--------|
| Reminder Absen Masuk | 09:00 | Nonaktif |
| Reminder Klaim Lembur | 18:31 | Nonaktif |

**Penting:** Aktifkan minimal satu jadwal agar cron bisa mengirim notifikasi.

---

## 2. Menjalankan Cron

### Sekali jalan (manual)
```bash
python manage.py runcrons
```

### Loop berjalan terus (development)
```bash
python manage.py cronloop
```
Cron berjalan setiap 15 menit. Pastikan satu terminal untuk `runserver`, satu lagi untuk `cronloop`.

### Production
Jadwalkan via sistem (crontab/Task Scheduler), contoh setiap 15 menit:
```bash
*/15 * * * * cd /path/to/project && python manage.py runcrons
```

---

## 3. Kondisi agar Reminder Terkirim

### Check-in Reminder
- Jadwal aktif dan `run_time` sudah lewat hari ini
- User **belum** check-in hari ini
- User sudah subscribe Web Push (popup → Aktifkan Notifikasi)

### Overtime Alert
- Jadwal aktif dan `run_time` sudah lewat hari ini
- User **sudah** check-in, **belum** check-out, keterangan **WFO**

---

## 4. Testing Cepat (tanpa tunggu jadwal)

### A. Test Web Push (notifikasi uji)
```bash
python manage.py test_webpush your@email.com
```
Kirim notifikasi uji ke user yang sudah subscribe. Berguna untuk cek apakah Web Push berfungsi.

### B. Test logic reminder (abaikan jam jadwal)
```bash
python manage.py run_reminder_test checkin     # reminder absen masuk
python manage.py run_reminder_test overtime    # reminder klaim lembur
python manage.py run_reminder_test             # keduanya
```
Menjalankan logic pengiriman tanpa cek `run_time`. Berguna untuk testing lokal.

---

## 5. Checklist Testing Lengkap

1. [ ] User subscribe Web Push (popup saat login → Aktifkan)
2. [ ] HRD buka Kelola Notifikasi, aktifkan jadwal
3. [ ] Set `run_time` ke jam yang sudah lewat (mis. 00:01) untuk testing
4. [ ] Jalankan `python manage.py runcrons` atau `run_reminder_test`
5. [ ] Cek browser/device yang subscribe → notifikasi harus muncul
