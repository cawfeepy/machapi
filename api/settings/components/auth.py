from datetime import timedelta
from machtms.core.envctrl import env

SECRET_KEY = env.django.SECRET_KEY.get_secret_value()
AUTH_USER_MODEL = 'machtms.OrganizationUser'
REST_KNOX = {'TOKEN_TTL': timedelta(hours=36)}
