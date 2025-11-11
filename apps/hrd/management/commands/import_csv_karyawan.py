import csv
import re
import unicodedata
import datetime
from typing import List, Dict, Tuple
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from apps.authentication.models import User
from apps.hrd.models import Karyawan
from apps.hrd.utils.generate_password import generate_default_password

def parse_date(value):
    if not value:
        return None
    s = str(value).strip()
    if not s:
        return None
    for fmt in ('%Y-%m-%d', '%d-%m-%Y', '%d/%m/%Y', '%m/%d/%Y', '%Y/%m/%d', '%d.%m.%Y', '%Y.%m.%d'):
        try:
            return datetime.datetime.strptime(s, fmt).date()
        except Exception:
            continue
    try:
        parts = [p for p in s.replace('.', '-').replace('/', '-').split('-') if p]
        if len(parts) == 3:
            if len(parts[0]) == 4:
                y, m, d = parts
            else:
                d, m, y = parts
            return datetime.date(int(y), int(m), int(d))
    except Exception:
        return None
    return None

def slugify_name(s):
    s = unicodedata.normalize('NFKD', str(s or ''))
    s = ''.join(c for c in s if not unicodedata.combining(c))
    s = re.sub(r'[^a-zA-Z0-9\s]', '', s).strip().lower()
    parts = [p for p in s.split() if p]
    return '-'.join(parts)

def generate_email_from_nama(nama, domain):
    base = slugify_name(nama) or 'user'
    local = '.'.join(base.split('-'))
    return f"{local}@{domain}"

def normalize_gender(s):
    s = (s or '').strip().lower()
    if s in ('laki-laki', 'l', 'male', 'm'):
        return 'L'
    if s in ('perempuan', 'p', 'female', 'f'):
        return 'P'
    return None

# Helper untuk normalisasi label teks (hapus diakritik, spasi/karakter non-alfanumerik)
def _normalize_label(s: str) -> str:
    s = unicodedata.normalize('NFKD', str(s or ''))
    s = ''.join(c for c in s if not unicodedata.combining(c))
    s = re.sub(r'[^a-zA-Z0-9\s]', ' ', s).strip().upper()
    s = re.sub(r'\s+', ' ', s)
    return s

# Pemetaan provinsi: label -> kode 2 digit (ambil dari Karyawan.PROVINSI_CHOICES)
_PROV_CODE_SET = {code for code, _ in Karyawan.PROVINSI_CHOICES}
_PROV_NAME_MAP = {_normalize_label(name): code for code, name in Karyawan.PROVINSI_CHOICES}

def normalize_provinsi(value: str):
    s = (value or '').strip()
    if not s:
        return None
    s_up = s.upper()
    # Jika sudah kode 2 digit yang valid
    if s_up in _PROV_CODE_SET:
        return s_up
    # Cocokkan berdasarkan label yang dinormalisasi
    return _PROV_NAME_MAP.get(_normalize_label(s))

def normalize_kabupaten_kota(value: str):
    s = (value or '').strip()
    if not s:
        return None
    digits = re.sub(r'\D', '', s)
    return digits if len(digits) == 4 else None

class Command(BaseCommand):
    help = 'Impor CSV karyawan secara batch dengan upsert'

    def add_arguments(self, parser):
        parser.add_argument('csv_path', type=str)
        parser.add_argument('--encoding', default='utf-8-sig')
        parser.add_argument('--delimiter', default=',')
        parser.add_argument('--batch-size', type=int, default=1000)
        parser.add_argument('--dry-run', action='store_true')
        parser.add_argument('--no-create', action='store_true')
        parser.add_argument('--no-update', action='store_true')
        parser.add_argument('--email-domain', default='cesgs.local')
        parser.add_argument('--set-default-passwords', action='store_true')

    def handle(self, *args, **opts):
        path = opts['csv_path']
        enc = opts['encoding']
        delim = opts['delimiter']
        batch_size = opts['batch_size']
        dry = opts['dry_run']
        no_create = opts['no_create']
        no_update = opts['no_update']
        email_domain = opts['email_domain']
        set_default_passwords = opts.get('set_default_passwords')
        created = 0
        updated = 0
        skipped = 0
        updated_passwords = 0
        errors: List[str] = []

        def clean_row(r: Dict[str, str]) -> Dict[str, str]:
            row = { (k.strip() if isinstance(k,str) else k): (v.strip() if isinstance(v,str) else v)
                    for k, v in r.items() }
            nama = row.get('nama') or row.get('Nama') or ''
            email = (row.get('email') or row.get('Email') or '').lower()
            if not email:
                email = generate_email_from_nama(nama, email_domain)
            gender = normalize_gender(row.get('jenis_kelamin') or row.get('gender'))
            tgl_lahir = parse_date(row.get('tanggal_lahir'))
            mulai_kontrak = parse_date(row.get('mulai_kontrak'))
            batas_kontrak = parse_date(row.get('batas_kontrak'))
            return {
                'email': email,
                'nama': nama,
                'nama_catatan_kehadiran': (row.get('nama_catatan_kehadiran')
                                           or row.get('Nama Sesuai Catatan Kehadiran')
                                           or row.get('nama sesuai catatan kehadiran')
                                           or '').strip()[:100],
                'jenis_kelamin': gender,
                'tanggal_lahir': tgl_lahir,
                'mulai_kontrak': mulai_kontrak,
                'batas_kontrak': batas_kontrak,
                'jabatan': row.get('jabatan') or '',
                'divisi': row.get('divisi') or '',
                'alamat': row.get('alamat') or '',
                'no_telepon': row.get('no_telepon') or '',
                'status': row.get('status') or '',
                'status_keaktifan': row.get('status_keaktifan') or '',
                'provinsi': normalize_provinsi(row.get('provinsi') or row.get('Provinsi')),
                'kabupaten_kota': normalize_kabupaten_kota(row.get('kabupaten_kota') or row.get('Kabupaten/Kota')),
            }

        def process_batch(clean_rows: List[Dict[str,str]]):
            nonlocal created, updated, skipped, updated_passwords
            emails = [r['email'] for r in clean_rows if r.get('email')]
            existing_users = {u.email.lower(): u for u in User.objects.filter(email__in=emails)}
            existing_karyawans = {k.user.email.lower(): k for k in Karyawan.objects.select_related('user').filter(user__email__in=emails)}

            to_create_users: List[User] = []
            to_update_users: List[User] = []
            to_create_karyawans: List[Karyawan] = []
            to_update_karyawans: List[Karyawan] = []

            for r in clean_rows:
                try:
                    email = r['email']
                    nama = r['nama']
                    tgl_lahir_r = r.get('tanggal_lahir')  # pastikan terdefinisi sebelum branching
                
                    user = existing_users.get(email)
                    if not user and not no_create:
                        user = User(email=email, first_name=nama.split()[0] if nama else '', role='Karyawan Tetap')
                        if tgl_lahir_r:
                            password_default = generate_default_password(nama, tgl_lahir_r)
                            user.set_password(password_default)
                        else:
                            user.set_unusable_password()
                        to_create_users.append(user)
                    elif user and set_default_passwords:
                        if not user.has_usable_password() and tgl_lahir_r:
                            user.set_password(generate_default_password(nama, tgl_lahir_r))
                            to_update_users.append(user)

                    karyawan = existing_karyawans.get(email)
                    if not karyawan and not no_create:
                        karyawan = Karyawan(user=user, nama=nama)

                    if karyawan and not no_update:
                        karyawan.nama = r['nama'] or karyawan.nama
                        karyawan.nama_catatan_kehadiran = r['nama_catatan_kehadiran'] or karyawan.nama_catatan_kehadiran
                        karyawan.jenis_kelamin = r['jenis_kelamin'] or karyawan.jenis_kelamin
                        karyawan.tanggal_lahir = r['tanggal_lahir'] or karyawan.tanggal_lahir
                        karyawan.mulai_kontrak = r['mulai_kontrak'] or karyawan.mulai_kontrak
                        karyawan.batas_kontrak = r['batas_kontrak'] or karyawan.batas_kontrak
                        karyawan.jabatan = r['jabatan'] or karyawan.jabatan
                        karyawan.divisi = r['divisi'] or karyawan.divisi
                        karyawan.alamat = r['alamat'] or karyawan.alamat
                        karyawan.no_telepon = r['no_telepon'] or karyawan.no_telepon
                        karyawan.status = r['status'] or karyawan.status
                        karyawan.status_keaktifan = r['status_keaktifan'] or karyawan.status_keaktifan
                        karyawan.provinsi = r['provinsi'] or karyawan.provinsi
                        karyawan.kabupaten_kota = r['kabupaten_kota'] or karyawan.kabupaten_kota

                        if email in existing_karyawans:
                            to_update_karyawans.append(karyawan)
                        else:
                            to_create_karyawans.append(karyawan)
                except Exception as e:
                    errors.append(str(e))
                    skipped += 1

            if dry:
                created += len(to_create_users) + len([k for k in to_create_karyawans])
                updated += len(to_update_karyawans)
                updated_passwords += len(to_update_users)
                return

            with transaction.atomic():
                if to_create_users:
                    User.objects.bulk_create(to_create_users, ignore_conflicts=True)
                    created += len(to_create_users)
                # Refresh mapping for users that may have been created
                created_emails = [u.email for u in to_create_users]
                if created_emails:
                    for u in User.objects.filter(email__in=created_emails):
                        existing_users[u.email.lower()] = u
                # Attach user instances to karyawan creates
                for k in to_create_karyawans:
                    k.user = existing_users.get(k.user.email.lower(), k.user)

                if to_create_karyawans:
                    Karyawan.objects.bulk_create(to_create_karyawans, ignore_conflicts=True)
                    created += len(to_create_karyawans)

                if to_update_karyawans:
                    Karyawan.objects.bulk_update(
                        to_update_karyawans,
                        ['nama','nama_catatan_kehadiran','jenis_kelamin','tanggal_lahir','mulai_kontrak','batas_kontrak',
                         'jabatan','divisi','alamat','no_telepon','status','status_keaktifan',
                         'provinsi','kabupaten_kota']
                    )
                    updated += len(to_update_karyawans)
                if to_update_users:
                    User.objects.bulk_update(to_update_users, ['password'])
                    updated_passwords += len(to_update_users)

        with open(path, mode='r', encoding=enc, newline='') as f:
            reader = csv.DictReader(f, delimiter=delim)
            batch: List[Dict[str,str]] = []
            for i, row in enumerate(reader, start=2):
                try:
                    clean = clean_row(row)
                    batch.append(clean)
                    if len(batch) >= batch_size:
                        process_batch(batch)
                        batch.clear()
                except Exception as e:
                    errors.append(f'Baris {i}: {e}')
                    skipped += 1
            if batch:
                process_batch(batch)

        self.stdout.write(f'Created: {created}, Updated: {updated}, Skipped: {skipped}')
        self.stdout.write(f'Updated Passwords: {updated_passwords}')
        if errors:
            self.stderr.write('Errors:\n' + '\n'.join(errors))