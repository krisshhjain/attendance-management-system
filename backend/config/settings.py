"""
Django settings for the Attendance Management System.

Configures application modules, security boundaries, PostgreSQL database connectivity,
JWT authentication via Django REST Framework, CORS policies, and localized timezone rules.

For more information on this file, see:
https://docs.djangoproject.com/en/5.2/topics/settings/
"""

from pathlib import Path
import os

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent


# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/5.2/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
# Default fallback development key; production environments must override this via environment variables.
SECRET_KEY = 'django-insecure-kq4_#owmid(ueiyneg$10t_xxw!@-7x#!rz!ls_hots#xwi(%-'

# SECURITY WARNING: don't run with debug turned on in production!
# Set to True for development debugging and local media serving; must be False in production.
DEBUG = True

# Sourced from ALLOWED_HOSTS environment variable; defaults to wildcard ('*') for local container and dev setups.
ALLOWED_HOSTS = os.environ.get("ALLOWED_HOSTS", "*").split(",")


# Application definition

INSTALLED_APPS = [
    # Core domain business applications
    "accounts",
    "employees",
    "attendance",
    "leave_management",

    # Third-party extensions
    "rest_framework",
    "corsheaders",

    # Django built-in contrib apps
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
]

# Configure Django REST Framework to use SimpleJWT authentication globally across API views
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ),
}

# Middleware execution order:
# CorsMiddleware must reside at the top to handle cross-origin preflight requests
# before security, session, and authentication middlewares process the request.
MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

# Cross-Origin Resource Sharing (CORS) development settings.
# Permissive defaults allow frontend development servers (e.g. Vite on port 5173).
# In production, CORS_ALLOW_ALL_ORIGINS should be False with specific trusted origins in CORS_ALLOWED_ORIGINS.
CORS_ALLOW_ALL_ORIGINS = True
CORS_ALLOW_CREDENTIALS = True

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'


# Database configuration
# Connects to PostgreSQL, reading connection parameters from environment variables.
# Default port 5434 is configured to prevent port conflicts with local system PostgreSQL instances (5432).
# https://docs.djangoproject.com/en/5.2/ref/settings/#databases

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.environ.get("POSTGRES_DB", "attendance_db"),
        "USER": os.environ.get("POSTGRES_USER", "attendance_user"),
        "PASSWORD": os.environ.get("POSTGRES_PASSWORD", "attendance_password"),
        "HOST": os.environ.get("POSTGRES_HOST", "127.0.0.1"),
        "PORT": os.environ.get("POSTGRES_PORT", "5434"),
    }
}


# Password validation
# Applied by accounts.serializers.ChangePasswordSerializer and createsuperuser command
# https://docs.djangoproject.com/en/5.2/ref/settings/#auth-password-validators

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


# Internationalization & Localization
# Operating timezone is set to Asia/Kolkata (IST) to ensure attendance logs and leaves align with local business hours.
# https://docs.djangoproject.com/en/5.2/topics/i18n/

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'Asia/Kolkata'

USE_I18N = True

USE_TZ = True

# Override default Django User model with custom email-based authentication model
AUTH_USER_MODEL = "accounts.User"


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/5.2/howto/static-files/

STATIC_URL = 'static/'

# Default primary key field type
# https://docs.djangoproject.com/en/5.2/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Media files (User uploads such as profile attachments or documents)
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'
