"""
Validators for Attendance System
- File upload validation for WFH documentation
"""
from django.core.exceptions import ValidationError
import os

# Constants
MAX_FILE_SIZE = 5 * 1024 * 1024  # 5MB
ALLOWED_WFH_EXTENSIONS = ['.png', '.jpg', '.jpeg', '.pdf']


def validate_wfh_document_extension(value):
    """
    Validate that uploaded WFH approval document is .png, .jpg, or .pdf
    
    Args:
        value: FileField value
        
    Raises:
        ValidationError: If file extension is not allowed
    """
    ext = os.path.splitext(value.name)[1].lower()
    
    if ext not in ALLOWED_WFH_EXTENSIONS:
        raise ValidationError(
            f'File harus berformat {", ".join(ALLOWED_WFH_EXTENSIONS)}. '
            f'File Anda: {ext}'
        )


def validate_file_size_wfh(value):
    """
    Validate that uploaded file is under maximum size limit
    
    Args:
        value: FileField value
        
    Raises:
        ValidationError: If file size exceeds limit
    """
    if value.size > MAX_FILE_SIZE:
        size_mb = value.size / (1024 * 1024)
        max_mb = MAX_FILE_SIZE / (1024 * 1024)
        raise ValidationError(
            f'Ukuran file maksimal {max_mb:.0f}MB. '
            f'File Anda: {size_mb:.1f}MB'
        )
