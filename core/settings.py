# from pathlib import Path
# import os
# from django.contrib.messages import constants as messages
# import dj_database_url

# GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")


# # Build paths inside the project like this: BASE_DIR / 'subdir'.
# BASE_DIR = Path(__file__).resolve().parent.parent


# # Quick-start development settings - unsuitable for production
# # See https://docs.djangoproject.com/en/5.2/howto/deployment/checklist/

# # SECURITY WARNING: keep the secret key used in production secret!
# SECRET_KEY = 'django-insecure-_q5%&jqm$884a0b!an#-we^fx&22(%u+rdp1#7g83on=6f&moa'

# # SECURITY WARNING: don't run with debug turned on in production!
# DEBUG = False

# # Allow localhost, 127.0.0.1, and Render's hostname (set via env var)
# ALLOWED_HOSTS = ['localhost', '127.0.0.1']
# RENDER_EXTERNAL_HOSTNAME = os.environ.get('RENDER_EXTERNAL_HOSTNAME')
# if RENDER_EXTERNAL_HOSTNAME:
#     ALLOWED_HOSTS.append(RENDER_EXTERNAL_HOSTNAME)


# # # Application definition

# INSTALLED_APPS = [
#     'rest_framework',  # required for django rest framework
#     'widget_tweaks',  # required dependency
#     'django.contrib.admin',
#     'django.contrib.auth',
#     'django.contrib.contenttypes',
#     'django.contrib.sessions',
#     'django.contrib.messages',
#     'django.contrib.humanize',
#     'django.contrib.staticfiles',
#     # 'core',   #Appname so we don't delete---only modify.
#     'core.apps.CoreConfig',  # To load predefined qualifications
#     'django_extensions',

# ]

# MIDDLEWARE = [
#     'django.middleware.security.SecurityMiddleware',
#     'whitenoise.middleware.WhiteNoiseMiddleware',
#     'django.contrib.sessions.middleware.SessionMiddleware',
#     'django.middleware.common.CommonMiddleware',
#     'django.middleware.csrf.CsrfViewMiddleware',
#     'django.contrib.auth.middleware.AuthenticationMiddleware',
#     'django.contrib.messages.middleware.MessageMiddleware',
#     'django.middleware.clickjacking.XFrameOptionsMiddleware',

# ]

# ROOT_URLCONF = 'core.urls'

# TEMPLATES = [
#     {
#         'BACKEND': 'django.template.backends.django.DjangoTemplates',
#         'DIRS': [BASE_DIR / 'templates'],
#         'APP_DIRS': True,
#         'OPTIONS': {
#             'context_processors': [
#                 'django.template.context_processors.request',
#                 'django.contrib.auth.context_processors.auth',
#                 'django.contrib.messages.context_processors.messages',
#             ],
#         },
#     },
# ]

# WSGI_APPLICATION = 'core.wsgi.application'
# # Database
# # https://docs.djangoproject.com/en/5.2/ref/settings/#databases

# DATABASES = {
#     'default': {
#         'ENGINE': 'django.db.backends.postgresql',
#         'NAME': 'chieta_lmsdb',
#         'USER': 'chieta_lmsdb_user',
#         'PASSWORD': 'KLo46ahIw4gYzF3InULyEyd64qA3tWDC',
#         'HOST': 'dpg-d4e4ut6mcj7s73cfdb6g-a.singapore-postgres.render.com',
#         'PORT': '5432',
#     }
# }


# MEDIA_URL = '/media/'
# MEDIA_ROOT = os.path.join(BASE_DIR, 'media')

# # Static files (CSS, JavaScript, Images)
# # https://docs.djangoproject.com/en/5.2/howto/static-files/

# STATIC_URL = 'static/'
# STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')

# STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

# # Password validation
# # https://docs.djangoproject.com/en/5.2/ref/settings/#auth-password-validators

# AUTH_PASSWORD_VALIDATORS = [
#     {
#         'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
#     },
#     {
#         'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
#     },
#     {
#         'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
#     },
#     {
#         'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
#     },
# ]

# # #Very important!!!!!!!!!!!!!!!!!!!!!!!!!!!! [core] is the app name before CustomUser here but we can change it later.
# AUTH_USER_MODEL = 'core.CustomUser'

# AUTHENTICATION_BACKENDS = [
#     # note appname at start so when we change this must change too.
#     'core.authback.EmailBackend',
#     'django.contrib.auth.backends.ModelBackend',
# ]

# # settings.py


# AUTHENTICATION_BACKENDS = [
#     'core.authback.EmailBackend',  #note appname at start so when we change this must change too.
#     'django.contrib.auth.backends.ModelBackend',
# ]

# # Email configuration
# if DEBUG == True:
#     # Development: Print emails to the console
#     EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'
# elif DEBUG == False:
#     # Production:

#     #BiggyMan Take note the smtp swapped for the console backend.
#     EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
#     EMAIL_HOST = 'smtp.gmail.com'
#     EMAIL_PORT = 587
#     EMAIL_USE_TLS = True
#     EMAIL_HOST_USER = 'stemappza@gmail.com'  # We swap out the real Email here.
#     EMAIL_HOST_PASSWORD = 'ddtz gltz vscj loab'  # Use the App Password generated by Google
#     DEFAULT_FROM_EMAIL = 'STEM LMS <stemappza@gmail.com>'


# MESSAGE_TAGS = {
#     messages.DEBUG: 'secondary',
#     messages.INFO: 'info',
#     messages.SUCCESS: 'success',
#     messages.WARNING: 'warning',
#     messages.ERROR: 'danger',
# }
# # Internationalization
# # https://docs.djangoproject.com/en/5.2/topics/i18n/

# LANGUAGE_CODE = 'en-us'

# TIME_ZONE = 'UTC'

# USE_I18N = True

# USE_TZ = True


# # Default primary key field type
# # https://docs.djangoproject.com/en/5.2/ref/settings/#default-auto-field

# DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

#########################################################################################################

# from pathlib import Path
# import os
# from django.contrib.messages import constants as messages
# import dj_database_url

# GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# # Build paths inside the project like this: BASE_DIR / 'subdir'.
# BASE_DIR = Path(__file__).resolve().parent.parent

# # Quick-start development settings - unsuitable for production
# # See https://docs.djangoproject.com/en/5.2/howto/deployment/checklist/

# # SECURITY WARNING: keep the secret key used in production secret!
# SECRET_KEY = 'django-insecure-_q5%&jqm$884a0b!an#-we^fx&22(%u+rdp1#7g83on=6f&moa'

# # 🚨 TEMPORARY DEMO CHANGE - Set DEBUG to True
# DEBUG = True  # Changed from False to True

# # 🚨 TEMPORARY DEMO CHANGE - Allow all hosts for demo
# ALLOWED_HOSTS = ['*']  # Changed from specific hosts to allow all

# # Application definition

# INSTALLED_APPS = [
#     'rest_framework',  # required for django rest framework
#     'widget_tweaks',  # required dependency
#     'django.contrib.admin',
#     'django.contrib.auth',
#     'django.contrib.contenttypes',
#     'django.contrib.sessions',
#     'django.contrib.messages',
#     'django.contrib.humanize',
#     'django.contrib.staticfiles',
#     'core.apps.CoreConfig',  # To load predefined qualifications
#     'django_extensions',
# ]

# MIDDLEWARE = [
#     'django.middleware.security.SecurityMiddleware',
#     'whitenoise.middleware.WhiteNoiseMiddleware',
#     'django.contrib.sessions.middleware.SessionMiddleware',
#     'django.middleware.common.CommonMiddleware',
#     'django.middleware.csrf.CsrfViewMiddleware',
#     'django.contrib.auth.middleware.AuthenticationMiddleware',
#     'django.contrib.messages.middleware.MessageMiddleware',
#     'django.middleware.clickjacking.XFrameOptionsMiddleware',
# ]

# ROOT_URLCONF = 'core.urls'

# TEMPLATES = [
#     {
#         'BACKEND': 'django.template.backends.django.DjangoTemplates',
#         'DIRS': [BASE_DIR / 'templates'],
#         'APP_DIRS': True,
#         'OPTIONS': {
#             'context_processors': [
#                 'django.template.context_processors.request',
#                 'django.contrib.auth.context_processors.auth',
#                 'django.contrib.messages.context_processors.messages',
#             ],
#         },
#     },
# ]

# WSGI_APPLICATION = 'core.wsgi.application'

# # Database
# DATABASES = {
#     'default': {
#         'ENGINE': 'django.db.backends.postgresql',
#         'NAME': 'chieta_lmsdb',
#         'USER': 'chieta_lmsdb_user',
#         'PASSWORD': 'KLo46ahIw4gYzF3InULyEyd64qA3tWDC',
#         'HOST': 'dpg-d4e4ut6mcj7s73cfdb6g-a.singapore-postgres.render.com',
#         'PORT': '5432',
#     }
# }

# # Media files
# Removed AWS credentials - use environment variables instead
# AWS_STORAGE_BUCKET_NAME = 'chieta-media'
# AWS_S3_REGION_NAME = 'us-west-2'
# AWS_S3_FILE_OVERWRITE = False
# AWS_DEFAULT_ACL = 'public-read'
# AWS_QUERYSTRING_AUTH = False

# # Default file storage to S3
# DEFAULT_FILE_STORAGE = 'storages.backends.s3boto3.S3Boto3Storage'
# MEDIA_URL = f'https://chieta-media.s3.amazonaws.com/'


# # Static files (CSS, JavaScript, Images)
# STATIC_URL = 'static/'
# STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')

# STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

# # Password validation
# AUTH_PASSWORD_VALIDATORS = [
#     {
#         'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
#     },
#     {
#         'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
#     },
#     {
#         'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
#     },
#     {
#         'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
#     },
# ]

# AUTH_USER_MODEL = 'core.CustomUser'

# AUTHENTICATION_BACKENDS = [
#     'core.authback.EmailBackend',
#     'django.contrib.auth.backends.ModelBackend',
# ]

# # Email configuration
# # 🚨 TEMPORARY DEMO CHANGE - Real email sending for demo
# EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
# EMAIL_HOST = 'smtp.gmail.com'
# EMAIL_PORT = 587
# EMAIL_USE_TLS = True
# EMAIL_HOST_USER = 'stemappza@gmail.com'
# EMAIL_HOST_PASSWORD = 'ddtz gltz vscj loab'  # Your app password
# DEFAULT_FROM_EMAIL = 'STEM LMS <stemappza@gmail.com>'

# MESSAGE_TAGS = {
#     messages.DEBUG: 'secondary',
#     messages.INFO: 'info',
#     messages.SUCCESS: 'success',
#     messages.WARNING: 'warning',
#     messages.ERROR: 'danger',
# }

# # Internationalization
# LANGUAGE_CODE = 'en-us'
# TIME_ZONE = 'UTC'
# USE_I18N = True
# USE_TZ = True

# # Default primary key field type
# DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

#########################################################################################################

from pathlib import Path
import os
from django.contrib.messages import constants as messages
import dj_database_url

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/5.2/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = 'django-insecure-_q5%&jqm$884a0b!an#-we^fx&22(%u+rdp1#7g83on=6f&moa'

# 🚨 TEMPORARY DEMO CHANGE - Set DEBUG to True
DEBUG = True  # Changed from False to True

# 🚨 TEMPORARY DEMO CHANGE - Allow all hosts for demo
ALLOWED_HOSTS = ['*']  # Changed from specific hosts to allow all

# Application definition

INSTALLED_APPS = [
    'rest_framework',  # required for django rest framework
    'widget_tweaks',  # required dependency
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.humanize',
    'django.contrib.staticfiles',
    'core.apps.CoreConfig',  # To load predefined qualifications
    'django_extensions',
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
]

ROOT_URLCONF = 'core.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
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

WSGI_APPLICATION = 'core.wsgi.application'

# Database


DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}
# DATABASES = {
#     'default': {
#         'ENGINE': 'django.db.backends.postgresql',
#         'NAME': 'chietalms_db',
#         'USER': 'chietalms_db_user',
#         'PASSWORD': 'STJoCuJLFlsxBIYFbYXF1WbUUfytDLSK',
#         'HOST': 'dpg-d4i6bb3uibrs73e0p4n0-a.oregon-postgres.render.com',
#         'PORT': '5432',
#     }
# }

# DATABASES = {
#    'default': {
#         'ENGINE': 'django.db.backends.postgresql',
#         'NAME': 'new_db',           
#         'USER': 'postgres',
#         'PASSWORD': '12345',  
#         'HOST': 'localhost',
#         'PORT': '5432',
#     }
# }


MEDIA_URL = '/media/'
MEDIA_ROOT = '/var/data/media'

# 🚨 TEMPORARY DEMO CHANGE - Create media folder on startup
os.makedirs(MEDIA_ROOT, exist_ok=True)

# Static files (CSS, JavaScript, Images)
STATIC_URL = 'static/'
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')

STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

# Password validation
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

AUTH_USER_MODEL = 'core.CustomUser'

AUTHENTICATION_BACKENDS = [
    'core.authback.EmailBackend',
    'django.contrib.auth.backends.ModelBackend',
]

# Email configuration 
# 🚨 TEMPORARY DEMO CHANGE - Real email sending for demo
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
# EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'
EMAIL_HOST = 'smtp.gmail.com'
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_HOST_USER = 'stemappza@gmail.com'
EMAIL_HOST_PASSWORD = 'ddtz gltz vscj loab'  # Your app password
DEFAULT_FROM_EMAIL = 'STEM LMS <stemappza@gmail.com>'

MESSAGE_TAGS = {
    messages.DEBUG: 'secondary',
    messages.INFO: 'info',
    messages.SUCCESS: 'success',
    messages.WARNING: 'warning',
    messages.ERROR: 'danger',
}

# Internationalization
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

# Default primary key field type
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

#P36
#p36
