from storages.backends.s3boto3 import S3Boto3Storage

class StaticStorage(S3Boto3Storage):
    location = 'hr_cesgs_dev/static'
    default_acl = None

class MediaStorage(S3Boto3Storage):
    location = 'hr_cesgs_dev/media'

    # 1. Pastikan file selalu privat
    default_acl = 'private' 
    file_overwrite = False

    # 2. Aktifkan link aman (presigned URL)
    querystring_auth = True 

    # 3. download file secara otomatis
    object_parameters = {
        'ContentDisposition': 'attachment',
    }