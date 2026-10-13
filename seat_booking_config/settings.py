"""
Django settings for seat_booking_config project.

Kenya Sports Venue Seat Booking and Visualization System
BBIT 4 - IS Project II - Strathmore University
"""

from pathlib import Path
import os
from decouple import config
from django.core.exceptions import ImproperlyConfigured

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent


# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/6.1/howto/deployment/checklist/

# SECURITY WARNING: don't run with debug turned on in production!
# Off unless .env says DEBUG=True, so a server with a missing .env fails safe.
DEBUG = config('DEBUG', default=False, cast=bool)

# SECURITY WARNING: keep the secret key used in production secret!
# The fallback key is public (it is in the git history), so it is only allowed while debugging.
SECRET_KEY = config('SECRET_KEY', default='')
if not SECRET_KEY or SECRET_KEY.startswith('django-insecure'):
    if not DEBUG:
        raise ImproperlyConfigured(
            'Set a real SECRET_KEY in .env for production, e.g. the output of: '
            'python -c "from django.core.management.utils import get_random_secret_key as k; print(k())"')
    SECRET_KEY = SECRET_KEY or 'django-insecure-development-only-key'

ALLOWED_HOSTS = config('ALLOWED_HOSTS', default='localhost,127.0.0.1', cast=lambda v: [s.strip() for s in v.split(',')])

# Full origins (scheme + host) allowed to submit forms over HTTPS, e.g. your ngrok address,
# so the Django admin login works there. Wildcards like https://*.ngrok-free.app are allowed.
CSRF_TRUSTED_ORIGINS = config('CSRF_TRUSTED_ORIGINS', default='', cast=lambda v: [s.strip() for s in v.split(',') if s.strip()])


# Application definition

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    
    # Third-party apps
    'rest_framework',
    'rest_framework_simplejwt.token_blacklist',
    'corsheaders',
    'django_filters',
    
    # Local apps
    'users.apps.UsersConfig',
    'venues.apps.VenuesConfig',
    'events.apps.EventsConfig',
    'bookings.apps.BookingsConfig',
    'payments.apps.PaymentsConfig',
    'tickets.apps.TicketsConfig',
    'gates.apps.GatesConfig',
    'reports.apps.ReportsConfig',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',  # For static files in production
    'django.contrib.sessions.middleware.SessionMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

# CORS Configuration
CORS_ALLOWED_ORIGINS = config('CORS_ALLOWED_ORIGINS', default='http://localhost:3000,http://localhost:8000', cast=lambda v: [s.strip() for s in v.split(',')])

ROOT_URLCONF = 'seat_booking_config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.template.context_processors.media',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'seat_booking_config.context_processors.site',
            ],
        },
    },
]

WSGI_APPLICATION = 'seat_booking_config.wsgi.application'


# Database Configuration
# https://docs.djangoproject.com/en/6.1/ref/settings/#databases
# PostgreSQL configuration for production, SQLite for development

if config('USE_POSTGRESQL', default=False, cast=bool):
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': config('DB_NAME', default='seat_booking'),
            'USER': config('DB_USER', default='postgres'),
            'PASSWORD': config('DB_PASSWORD', default=''),
            'HOST': config('DB_HOST', default='localhost'),
            'PORT': config('DB_PORT', default='5432'),
            # No ATOMIC_REQUESTS: the booking/payment services manage their own transactions
            # (and are tested that way); wrapping whole requests would change their behaviour.
            'CONN_MAX_AGE': 600,         # reuse connections for 10 minutes
            'CONN_HEALTH_CHECKS': True,  # ...but drop ones the server has closed
        }
    }
else:
    # Development: SQLite
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }


# Password validation
# https://docs.djangoproject.com/en/6.1/ref/settings/#auth-password-validators

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
# https://docs.djangoproject.com/en/6.1/topics/i18n/

LANGUAGE_CODE = 'en-us'

# Set timezone to East Africa Time (Nairobi)
TIME_ZONE = 'Africa/Nairobi'

USE_I18N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/6.1/howto/static-files/

STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_DIRS = [BASE_DIR / 'static'] if (BASE_DIR / 'static').exists() else []

# In production WhiteNoise serves compressed static files with content-hashed names
# (style.3f2a1c.css), so browsers can cache them forever and still get updates.
# Run `python manage.py collectstatic` when deploying.
STORAGES = {
    'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
    'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage' if DEBUG
                    else 'whitenoise.storage.CompressedManifestStaticFilesStorage'},
}

# Media files (User uploads)
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# Default primary key field type
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'


# Email Configuration
# https://docs.djangoproject.com/en/6.1/topics/email/#topic-email-configuration

EMAIL_BACKEND = config('EMAIL_BACKEND', default='django.core.mail.backends.console.EmailBackend')
EMAIL_HOST = config('EMAIL_HOST', default='smtp.gmail.com')
EMAIL_PORT = config('EMAIL_PORT', default=587, cast=int)
EMAIL_USE_TLS = config('EMAIL_USE_TLS', default=True, cast=bool)
EMAIL_HOST_USER = config('EMAIL_HOST_USER', default='')
EMAIL_HOST_PASSWORD = config('EMAIL_HOST_PASSWORD', default='')
DEFAULT_FROM_EMAIL = config('DEFAULT_FROM_EMAIL', default='noreply@seatbooking.app')


# REST Framework Configuration
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    'DEFAULT_FILTER_BACKENDS': [
        'django_filters.rest_framework.DjangoFilterBackend',
        'rest_framework.filters.SearchFilter',
        'rest_framework.filters.OrderingFilter',
    ],
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 50,
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
}

# JWT Configuration
from datetime import timedelta

SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=60),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=7),
    'ROTATE_REFRESH_TOKENS': True,
    'BLACKLIST_AFTER_ROTATION': True,
}

# Authentication
AUTH_USER_MODEL = 'users.User'

# Seat booking
# Name shown in the page header, footer and browser tab. Change it in .env.
SITE_NAME = config('SITE_NAME', default='Seat Booking')
SEAT_HOLD_DURATION_MINUTES = config('SEAT_HOLD_DURATION_MINUTES', default=10, cast=int)

# M-Pesa Daraja (STK Push). Sandbox credentials: https://developer.safaricom.co.ke
DARAJA_ENV = config('DARAJA_ENV', default='sandbox')  # 'sandbox' or 'production'
DARAJA_BASE_URL = ('https://api.safaricom.co.ke' if DARAJA_ENV == 'production'
                   else 'https://sandbox.safaricom.co.ke')
DARAJA_CONSUMER_KEY = config('DARAJA_CONSUMER_KEY', default='')
DARAJA_CONSUMER_SECRET = config('DARAJA_CONSUMER_SECRET', default='')
DARAJA_BUSINESS_SHORTCODE = config('DARAJA_BUSINESS_SHORTCODE', default='174379')
DARAJA_PASSKEY = config('DARAJA_PASSKEY', default='')
# Public HTTPS base URL Safaricom can reach (e.g. an ngrok URL in development).
DARAJA_CALLBACK_BASE_URL = config('DARAJA_CALLBACK_BASE_URL', default='')
# Secret path segment so only Safaricom (who is given the full URL) can post payment results.
DARAJA_CALLBACK_TOKEN = config('DARAJA_CALLBACK_TOKEN', default='')
# Amount actually sent to M-Pesa per payment while testing. The sandbox can debit a real phone's
# M-Pesa, so by default it charges KES 1 whatever the ticket price (the booking still records the
# real price). Set to 0 to charge the full price.
DARAJA_TEST_AMOUNT = config('DARAJA_TEST_AMOUNT', default=1 if DARAJA_ENV == 'sandbox' else 0, cast=int)

# Security Settings (production)
if not DEBUG:
    # Hosting platforms terminate HTTPS at their proxy and pass this header on;
    # set BEHIND_HTTPS_PROXY=False only if Django itself receives HTTPS directly.
    if config('BEHIND_HTTPS_PROXY', default=True, cast=bool):
        SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
    SECURE_SSL_REDIRECT = config('SECURE_SSL_REDIRECT', default=True, cast=bool)
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    # Tell browsers to use HTTPS only. Start small; raise to 31536000 (1 year) once HTTPS is stable.
    SECURE_HSTS_SECONDS = config('SECURE_HSTS_SECONDS', default=3600, cast=int)
    SECURE_CONTENT_TYPE_NOSNIFF = True
    SECURE_REFERRER_POLICY = 'same-origin'
    X_FRAME_OPTIONS = 'DENY'

# Logging Configuration
(BASE_DIR / 'logs').mkdir(exist_ok=True)  # a fresh server has no logs/ folder yet
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {process:d} {thread:d} {message}',
            'style': '{',
        },
        'simple': {
            'format': '{levelname} {asctime} {module} {message}',
            'style': '{',
        },
    },
    'filters': {
        'require_debug_false': {
            '()': 'django.utils.log.RequireDebugFalse',
        },
        'require_debug_true': {
            '()': 'django.utils.log.RequireDebugTrue',
        },
    },
    'handlers': {
        'console': {
            'level': 'DEBUG',
            'class': 'logging.StreamHandler',
            'formatter': 'simple',
        },
        'file': {
            'level': 'WARNING',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': BASE_DIR / 'logs' / 'seat_booking.log',
            'maxBytes': 1024 * 1024 * 10,  # 10MB
            'backupCount': 5,
            'formatter': 'verbose',
        },
        # Every M-Pesa request/callback, kept as an audit trail for reconciling payments.
        'payments_file': {
            'level': 'INFO',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': BASE_DIR / 'logs' / 'payments.log',
            'maxBytes': 1024 * 1024 * 10,
            'backupCount': 10,
            'formatter': 'simple',
        },
    },
    'loggers': {
        'django': {
            'handlers': ['console', 'file'],
            'level': 'INFO',
            'propagate': False,
        },
        'payments': {
            'handlers': ['console', 'payments_file'],
            'level': 'INFO',
            'propagate': False,
        },
        'seat_booking': {
            'handlers': ['console', 'file'],
            'level': 'DEBUG',
            'propagate': False,
        },
    },
}
