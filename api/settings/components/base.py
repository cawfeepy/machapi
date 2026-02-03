import logging
from django.conf.global_settings import DATETIME_INPUT_FORMATS
from machtms.core.envctrl import env

L = logging.getLogger(__name__)

DEBUG: bool = env.django.DEBUG
INSECURE = env.django.INSECURE


IS_SECURE = not DEBUG and not INSECURE
if not IS_SECURE:
    L.info(f"WARNING - DEBUG:{DEBUG} ;; INSECURE:{INSECURE}")


# MIGRATION_MODULES = {
#     'machtms': 'machtms.migrations_development' if DEBUG else 'machtms.migrations'
# }

ROOT_URLCONF = 'api.urls'
ASGI_APPLICATION = 'api.asgi.application'
DATETIME_INPUT_FORMATS += ('%Y-%m-%dT%H:%M:%S.%fZ', '%Y-%m-%dT%H:%M:%SZ',)

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_L10N = False
# Internationalization
# https://docs.djangoproject.com/en/3.1/topics/i18n/
#USE_I18N = True
USE_TZ = True
APPEND_SLASH=True

if IS_SECURE:
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

REST_FRAMEWORK = {
    'DEFAULT_FILTER_BACKENDS': ('django_filters.rest_framework.DjangoFilterBackend',),
    'DEFAULT_AUTHENTICATION_CLASSES': ['machtms.core.auth.authentication.TMSAuthentication',],
    'DEFAULT_PERMISSION_CLASSES': ['machtms.core.auth.permissions.TMSCustomPermission',],
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
}

# Application definition
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'rest_framework',
    "rest_framework_api_key",
    'django_filters',
    'django_extensions',
    'corsheaders',
    'knox',
    'drf_spectacular',
    'machtms',
]

DEFAULT_AUTO_FIELD = 'django.db.models.AutoField'

# Use testcontainers for running tests
TEST_RUNNER = 'api.runner.TestContainerRunner'

SPECTACULAR_SETTINGS = {
    # … your existing settings …
    'COMPONENT_SPLIT_REQUEST': True,
    'COMPONENT_NO_READ_ONLY_REQUIRED': True,
    'CAMELIZE_NAMES': False,
    'POSTPROCESSING_HOOKS': [
            'drf_spectacular.contrib.djangorestframework_camel_case.camelize_serializer_fields',
            'drf_spectacular.hooks.postprocess_schema_enums'
    ],
}

