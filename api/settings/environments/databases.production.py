import os, dj_database_url
from environments import env, BASE_DIR

# DEFAULT production environment
# overrides if DJANGO_ENV == 'production'

DEBUG = False
# Databases configuration for production

DB_URL = env("DATABASE_URL")
DATABASES = {}

_CA_CERT = os.path.join(BASE_DIR, 'ca-certificate.crt')
if not os.path.exists(_CA_CERT):
    err = "_CA_CERT must be set. Please check with your service provider and download the certificate"
    raise ValueError(err)
DB_URL += f'?sslrootcert={_CA_CERT}'
DATABASES['default'] = dj_database_url.config(default=DB_URL)

