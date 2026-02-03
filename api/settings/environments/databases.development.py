import dj_database_url
from django.conf import settings
from environments import env

DATABASES = {}
if env("DEBUG"):
    default = {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": "postgres",
            "USER": "postgres",
            "PASSWORD": "postgres",
            "HOST": env("POSTGRES_HOST"),
            "PORT": "5432",
            'TEST': {
                'TEMPLATE': 'postgres',
            },
    }

else:
    default = dj_database_url.config(default=env.db())

DATABASES['default'] = default
