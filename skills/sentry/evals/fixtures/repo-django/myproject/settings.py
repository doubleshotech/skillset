import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

# Secrets and per-env config come from the environment, not the source.
SECRET_KEY = os.environ.get('DJANGO_SECRET_KEY', 'dev-insecure-key')
DEBUG = os.environ.get('DJANGO_DEBUG', '1') == '1'
ALLOWED_HOSTS = [h for h in os.environ.get('DJANGO_ALLOWED_HOSTS', '').split(',') if h]

INSTALLED_APPS = [
    'django.contrib.contenttypes',
    'django.contrib.auth',
    'widgets',
]

MIDDLEWARE = [
    'django.middleware.common.CommonMiddleware',
]

ROOT_URLCONF = 'myproject.urls'
WSGI_APPLICATION = 'myproject.wsgi.application'

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
