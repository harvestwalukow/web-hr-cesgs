# -*- encoding: utf-8 -*-
"""
Copyright (c) 2019 - present AppSeed.us
"""

import os
from decouple import config
from unipath import Path
from dotenv import load_dotenv

# Build paths inside the project like this: os.path.join(BASE_DIR, ...)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CORE_DIR = BASE_DIR

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = config('SECRET_KEY')

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = config('DEBUG', default=True, cast=bool)

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
AUTH_USER_MODEL = 'authentication.User'

# load production server from .env
ALLOWED_HOSTS = ['localhost', '127.0.0.1', config('SERVER', default='127.0.0.1')]

MEDIA_ROOT = os.path.join(BASE_DIR, 'media')  

# Application definition

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'storages', # aws storage
    'apps.authentication', # auth
    'apps.hrd', # hrd 
    'apps.karyawan', # karyawan
    'apps.profil', # profil
    'apps.absensi', # absensi
    'django_cron',
    'notifications',
    'apps.notifikasi',
]

CRON_CLASSES = [
    'apps.hrd.cron.CekKontrakKaryawan',
    'apps.hrd.cron.PotongJatahCutiHMinus1',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'apps.hrd.middleware.CheckKaryawanStatusMiddleware',
]

ROOT_URLCONF = 'core.urls'
LOGIN_URL = "/auth/login/"  # Route untuk login
LOGIN_REDIRECT_URL = "home"  # Route defined in home/urls.py
LOGOUT_REDIRECT_URL = "home"  # Route defined in home/urls.py

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [
            os.path.join(BASE_DIR, 'apps', 'authentication', 'templates'),
            os.path.join(BASE_DIR, 'apps', 'hrd', 'templates'),
            os.path.join(BASE_DIR, 'apps', 'karyawan', 'templates'),
            os.path.join(BASE_DIR, 'apps', 'templates'),
            os.path.join(BASE_DIR, 'templates'),
        ],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'apps.authentication.context_processors.sidebar_menu',
            ],
        },
    },
]



WSGI_APPLICATION = 'core.wsgi.application'

# Database
load_dotenv()

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.getenv('DB_NAME', default=''),
        'USER': os.getenv('DB_USER', default=''),
        'PASSWORD': os.getenv('DB_PASSWORD', default=''),
        'HOST': os.getenv('DB_HOST', default='localhost'),
        'PORT': os.getenv('DB_PORT'),
    }
}

# Password validation
# https://docs.djangoproject.com/en/3.0/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]


# Internationalization
# https://docs.djangoproject.com/en/3.0/topics/i18n/

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'Asia/Jakarta'

USE_I18N = True

USE_L10N = True

USE_TZ = True

#############################################################
# SRC: https://devcenter.heroku.com/articles/django-assets

# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/3.0/howto/static-files/

STATIC_ROOT = os.path.join(CORE_DIR, 'staticfiles')
STATIC_URL = '/static/'  # Dinonaktifkan, menggunakan S3

# Extra places for collectstatic to find static files.
STATICFILES_DIRS = (
    os.path.join(CORE_DIR, 'apps/static'),
)

# File Upload Settings
FILE_UPLOAD_MAX_MEMORY_SIZE = 5242880  # 5MB
DATA_UPLOAD_MAX_MEMORY_SIZE = 5242880  # 5MB
DATA_UPLOAD_MAX_NUMBER_FILES = 1000
DATA_UPLOAD_MAX_NUMBER_FIELDS = None

# Session Settings
SESSION_COOKIE_AGE = 86400
SESSION_SAVE_EVERY_REQUEST = True 


# AWS S3 Configuration
AWS_STORAGE_BUCKET_NAME = os.environ.get('bucket_name')
AWS_S3_REGION_NAME = os.environ.get('region', 'ap-southeast-1')
AWS_ACCESS_KEY_ID = os.environ.get('aws_access_key_id')
AWS_SECRET_ACCESS_KEY = os.environ.get('aws_secret_access_key')
AWS_S3_CUSTOM_DOMAIN = os.environ.get(
    'aws_s3_custom_domain', 
    f'{AWS_STORAGE_BUCKET_NAME}.s3.{AWS_S3_REGION_NAME}.amazonaws.com'
)

# Nonaktifkan ACL karena bucket owner enforced
AWS_DEFAULT_ACL = None

# Storage backends
# STATICFILES_STORAGE = 'apps.utils.storages.StaticStorage'
# DEFAULT_FILE_STORAGE = 'apps.utils.storages.MediaStorage'

# URLs untuk static dan media files
# STATIC_URL = f"https://{AWS_S3_CUSTOM_DOMAIN}/hr_cesgs_dev/static/"
# MEDIA_URL = f"https://{AWS_S3_CUSTOM_DOMAIN}/hr_cesgs_dev/media/"