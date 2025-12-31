"""
Fonnte WhatsApp API Client

Untuk mengirim notifikasi WhatsApp ke karyawan via Fonnte API.
Dokumentasi: https://docs.fonnte.com/
"""

import requests
import logging
from django.conf import settings

logger = logging.getLogger(__name__)


def send_whatsapp(target: str, message: str, schedule: int = None) -> dict:
    """
    Kirim pesan WhatsApp via Fonnte API
    
    Args:
        target: Nomor telepon tujuan (format: 08xxx atau 62xxx)
        message: Isi pesan yang akan dikirim
        schedule: Unix timestamp untuk jadwal pengiriman (optional)
    
    Returns:
        dict: Response dari Fonnte API
            - status: True jika berhasil
            - detail: Pesan detail dari API
    
    Example:
        >>> result = send_whatsapp('082396333595', 'Halo dari HR!')
        >>> print(result)
        {'status': True, 'detail': 'message sent'}
    """
    if not settings.FONNTE_TOKEN:
        logger.error("FONNTE_TOKEN tidak dikonfigurasi di .env")
        return {'status': False, 'detail': 'Token tidak dikonfigurasi'}
    
    headers = {
        'Authorization': settings.FONNTE_TOKEN
    }
    
    payload = {
        'target': target,
        'message': message,
        'countryCode': '62',  # Indonesia - replace leading 0 with 62
    }
    
    if schedule:
        payload['schedule'] = schedule
    
    try:
        response = requests.post(
            settings.FONNTE_API_URL,
            headers=headers,
            data=payload,
            timeout=30
        )
        result = response.json()
        
        if result.get('status'):
            logger.info(f"WhatsApp terkirim ke {target}")
        else:
            logger.warning(f"Gagal kirim WA ke {target}: {result.get('detail', 'Unknown error')}")
        
        return result
        
    except requests.exceptions.Timeout:
        logger.error(f"Timeout saat kirim WA ke {target}")
        return {'status': False, 'detail': 'Request timeout'}
    except requests.exceptions.RequestException as e:
        logger.error(f"Error kirim WA ke {target}: {str(e)}")
        return {'status': False, 'detail': str(e)}
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        return {'status': False, 'detail': str(e)}


def send_overtime_alert(karyawan, jam_kerja: float) -> dict:
    """
    Kirim alert lembur ke karyawan yang sudah kerja 10+ jam
    
    Args:
        karyawan: Instance model Karyawan
        jam_kerja: Jumlah jam kerja saat ini
    
    Returns:
        dict: Response dari Fonnte API
    """
    if not karyawan.no_telepon:
        return {'status': False, 'detail': 'Nomor telepon tidak tersedia'}
    
    message = f"""⏰ *Alert Lembur - HR CESGS*

Hai {karyawan.nama}!

Anda sudah bekerja selama *{int(jam_kerja)} jam* hari ini.

Jika Anda ingin mengajukan lembur, silakan buka:
👉 https://hr.esgi.ai/karyawan/pengajuan-izin/

Terima kasih atas dedikasi Anda! 💪

_Pesan otomatis dari HR CESGS_"""
    
    return send_whatsapp(karyawan.no_telepon, message)
