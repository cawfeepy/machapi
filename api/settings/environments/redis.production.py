from environments import env
CACHES = {
    'default': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': env('REDIS_HOST'),
        'OPTIONS': {
            'PASSWORD': env('REDIS_PASSWORD'),
            'CLIENT_CLASS': "django_redis.client.DefaultClient",
        }
    }
}
