import dj_database_url
from django.conf import settings
from machtms.core.envctrl import env

DATABASES = {}
if env.django.DEBUG:
    default = {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": env.database.POSTGRES_DB,
            "USER": env.database.POSTGRES_USER,
            "PASSWORD": env.database.POSTGRES_PASSWORD,
            "HOST": env.database.POSTGRES_HOST,
            "PORT": str(env.database.POSTGRES_PORT),
            'TEST': {
                'TEMPLATE': env.database.POSTGRES_DB,
            },
    }

else:
    default = dj_database_url.config()

DATABASES['default'] = default
