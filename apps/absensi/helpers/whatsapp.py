"""
WhatsApp Integration for Attendance System
Uses Fonnte API to send WhatsApp alerts
"""
import requests
import logging
from django.conf import settings

logger = logging.getLogger(__name__)


def send_whatsapp_alert(phone_number, message):
    """
    Core function to send WhatsApp message via Fonnte API
    
    Args:
        phone_number (str): Phone number in format 08xxx or 628xxx
        message (str): Message content to send
        
    Returns:
        dict: Response from Fonnte API
    """
    try:
        # Normalize phone number to format without leading 0
        if phone_number.startswith('0'):
            phone_number = '62' + phone_number[1:]
        elif not phone_number.startswith('62'):
            phone_number = '62' + phone_number
            
        payload = {
            'target': phone_number,
            'message': message,
            'countryCode': '62'
        }
        
        headers = {
            'Authorization': settings.FONNTE_TOKEN
        }
        
        response = requests.post(
            settings.FONNTE_API_URL,
            data=payload,
            headers=headers,
            timeout=10
        )
        
        response_data = response.json()
        
        if response.status_code == 200:
            logger.info(f"WhatsApp sent successfully to {phone_number}")
        else:
            logger.error(f"Failed to send WhatsApp to {phone_number}: {response_data}")
            
        return response_data
        
    except requests.exceptions.RequestException as e:
        logger.error(f"Request error sending WhatsApp to {phone_number}: {str(e)}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error sending WhatsApp to {phone_number}: {str(e)}")
        raise


def get_url_role(user_role):
    """Helper to determine URL segment based on user role"""
    if user_role in ['Magang', 'Part Time', 'Freelance', 'Project']:
        return "magang"
    return "karyawan"


def send_checkin_reminder(karyawan):
    """
    Send check-in reminder to employee at 09:00 AM
    Reminds them to check in before 10:00 AM deadline
    
    Args:
        karyawan: Karyawan object
        
    Returns:
        dict: Response from WhatsApp API
    """
    url_role = get_url_role(karyawan.user.role if hasattr(karyawan, 'user') else 'Magang')
    
    message = f"""Reminder Absensi

Halo {karyawan.nama},

Anda belum melakukan check-in hari ini.

Batas waktu check-in: 10:00 WIB
Segera lakukan absensi di:
https://hr.esgi.ai/{url_role}/absensi/

Terima kasih,
Tim HRD CESGS"""
    
    return send_whatsapp_alert(karyawan.no_telepon, message)


def send_overtime_alert(karyawan):
    """
    Send overtime alert to employee still working after 18:30
    Reminds them they can claim overtime
    
    Args:
        karyawan: Karyawan object
        
    Returns:
        dict: Response from WhatsApp API
    """
    url_role = get_url_role(karyawan.user.role if hasattr(karyawan, 'user') else 'Magang')
    
    message = f"""Notifikasi Lembur

Halo {karyawan.nama},

Anda masih bekerja melewati jam 18:30 WIB.

Anda dapat mengajukan klaim lembur untuk hari ini.
Jangan lupa untuk melakukan check-out.

Pengajuan lembur:
https://hr.esgi.ai/{url_role}/pengajuan-izin/

Terima kasih,
Tim HRD CESGS"""
    
    return send_whatsapp_alert(karyawan.no_telepon, message)
