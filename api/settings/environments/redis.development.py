import sys
from environments import env

if 'test' in sys.argv:
    from fakeredis import FakeConnection
    CACHES = {
        'default': {
            'BACKEND': 'django_redis.cache.RedisCache',
            'LOCATION': 'redis://127.0.0.1:6379/0',
            'OPTIONS': {
                'CLIENT_CLASS': "django_redis.client.DefaultClient",
                'CONNECTION_POOL_KWARGS': {'connection_class': FakeConnection},
            }
        }
    }
if env("USE_REDIS"):
    CACHES = {
        'default': {
            'BACKEND': 'django_redis.cache.RedisCache',
            'LOCATION': env("REDIS_HOST"),
            'OPTIONS': {
                'PASSWORD': env("REDIS_PASSWORD"),
                'CLIENT_CLASS': "django_redis.client.DefaultClient",
            }
        }
    }

