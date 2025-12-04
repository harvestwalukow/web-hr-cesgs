from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models

class CustomUserManager(BaseUserManager):
    
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError("Email harus diisi")
        email = self.normalize_email(email)
        extra_fields.pop('username', None)  # Buang username karena kita pakai email
        
        # Generate password jika tidak disediakan
        if not password and 'nama' in extra_fields and 'tanggal_lahir' in extra_fields:
            # Ambil nama depan saja
            nama_depan = extra_fields['nama'].split()[0].lower()
            tanggal_lahir = extra_fields['tanggal_lahir'].strftime('%d%m%Y')
            password = f"{nama_depan}{tanggal_lahir}"
        
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.pop('username', None)

        return self.create_user(email, password, **extra_fields)

class User(AbstractUser):
    username = None  # Hapus field username bawaan

    HRD = 'HRD'
    KARYAWAN_TETAP = 'Karyawan Tetap'
    MAGANG = 'Magang'
    PART_TIME = 'Part Time'
    FREELANCE = 'Freelance'
    PROJECT = 'Project'

    ROLE_CHOICES = [
        (HRD, 'HRD'),
        (KARYAWAN_TETAP, 'Fulltime'),
        (MAGANG, 'Magang'),
        (PART_TIME, 'Part Time'),
        (FREELANCE, 'Freelance'),
        (PROJECT, 'Project'),
    ]

    email = models.EmailField(unique=True)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ['role']

    objects = CustomUserManager()

    def __str__(self):
        return f"{self.email} - {self.role}"
