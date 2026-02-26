import os
import dj_database_url
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
    db_url = dj_database_url.config()
    _ca_cert = os.path.join(env.BASE_DIR, 'ca-certificate.crt')
    if os.path.exists(_ca_cert):
        db_url.setdefault('OPTIONS', {})
        db_url['OPTIONS']['sslrootcert'] = _ca_cert
    default = db_url

DATABASES['default'] = default
