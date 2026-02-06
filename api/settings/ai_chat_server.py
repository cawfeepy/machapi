"""
Settings override for the ai_chat management command subprocess.

The ai_chat command starts testcontainers on random ports and needs the
runserver subprocess to connect to those containers. Because the base
settings module (via environments.py) calls ``env.read_env(.env.local,
overwrite=True)``, standard env var names like ``POSTGRES_HOST`` get
clobbered. We use a ``MACHAPI_TC_`` prefix to safely pass container
URLs from the parent process.
"""

import os

import dj_database_url

from api.settings import *  # noqa: F401, F403

_db_url = os.environ.get("MACHAPI_TC_DATABASE_URL")
if _db_url:
    DATABASES = {"default": dj_database_url.parse(_db_url)}

_broker = os.environ.get("MACHAPI_TC_BROKER_URL")
if _broker:
    CELERY_BROKER_URL = _broker

_result = os.environ.get("MACHAPI_TC_RESULT_BACKEND")
if _result:
    CELERY_RESULT_BACKEND = _result

_redis = os.environ.get("MACHAPI_TC_REDIS_URL")
if _redis:
    CACHES = {
        "default": {
            "BACKEND": "django_redis.cache.RedisCache",
            "LOCATION": _redis,
            "OPTIONS": {"CLIENT_CLASS": "django_redis.client.DefaultClient"},
        }
    }
    REDIS_URL = _redis
