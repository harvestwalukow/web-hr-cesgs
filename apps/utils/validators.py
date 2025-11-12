from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

def validate_file_size(file):
    """Validasi ukuran file maksimal 5MB"""
    max_size = 5 * 1024 * 1024  # 5MB dalam bytes
    if file.size > max_size:
        raise ValidationError(
            _(f'Ukuran file terlalu besar. Maksimal 5MB. File Anda: {file.size / (1024*1024):.2f}MB')
        )
    return file

def validate_file_extension(file):
    """Validasi ekstensi file yang diizinkan"""
    allowed_extensions = ['.pdf', '.doc', '.docx', '.jpg', '.jpeg', '.png', '.xls', '.xlsx']
    file_extension = file.name.lower().split('.')[-1]
    if f'.{file_extension}' not in allowed_extensions:
        raise ValidationError(
            _(f'Tipe file tidak diizinkan. Hanya diperbolehkan: {", ".join(allowed_extensions)}')
        )
    return file