import logging
import environ
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

"""
Below you'll find the default environment
variables for the whole application 'tms'.

Notes:
DEBUG = False; will enable organization models
INSECURE = True;
* DO NOT USE IN PRODUCTION ENVIRONMENT
* will remove permissions/authentication classes;
* removes CORs and CSRF security.

To create a production environment set the following:
DEBUG = False
INSECURE = False

A staging event with no security
DEBUG = False
INSECURE = True

"""

logger = logging.getLogger(__name__)

env = environ.Env(
    HOST=(str, 'localhost'),
    DEBUG=(bool, True),
    SECRET_KEY=(str, "debug_secret_key_123"),
    INSECURE=(bool, True),
    DJANGO_ENV=(str, 'development'),
    CSRF_TRUSTED_ORIGINS=(list, []),
    CORS_ALLOWED_ORIGINS=(list, []),
    CORS_ALLOWED_ORIGIN_REGEXES=(str, ''),
    ALLOWED_HOSTS=(list, ["*"]),
    POSTGRES_HOST=(str, "localhost"),
    MAPS_API_KEY=(str, None),
    COOKIE_DOMAIN=(str, None),

    USE_CELERY=(bool, False),
    CELERY_BROKER_URL=(str, ""),

    USE_REDIS=(bool, False),
    USE_MEILISEARCH=(bool, False),

    AWS_ACCESS_KEY=(str, ""),
    AWS_SECRET_KEY=(str, ""),
    AWS_REGION_NAME=(str, ""),
    AWS_UPLOAD_BUCKET=(str, ""),
    AWS_POST_SHIPMENT_BUCKET=(str, ""),

    GMAIL_API_CLIENT_SECRET=(str, ""),
    GMAIL_API_REDIRECT_URI=(str, ""),
    GMAIL_API_SCOPES=(str, ""),
    GMAIL_API_CLIENT_ID=(str, "")
)
local = BASE_DIR.joinpath(f'.env.local')
if local.exists():
    env.read_env(local, overwrite=True)

SERVICES = [
    'aws',
    'gmail',
    'meiliesearch'
]

ENV_FILES = BASE_DIR / 'env_files' / 'env'

for service in SERVICES:
    env_file = ENV_FILES.joinpath(f'.env.{service}')
    if env_file.exists():
        env.read_env(env_file, overwrite=True)
