from machtms.core.envctrl import env

if env.redis.available:
    cfg = env.redis.config
    CACHES = {
        'default': {
            'BACKEND': 'django_redis.cache.RedisCache',
            'LOCATION': cfg.URL,
            'OPTIONS': {
                'CLIENT_CLASS': "django_redis.client.DefaultClient",
            }
        }
    }
    if cfg.PASSWORD:
        CACHES['default']['OPTIONS']['PASSWORD'] = cfg.PASSWORD
