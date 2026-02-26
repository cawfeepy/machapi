from machtms.core.envctrl import env


DEBUG = env.django.DEBUG

# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/3.1/howto/static-files/
STATIC_URL = '/static/'
if not DEBUG:
    STATIC_ROOT = '/app/static'
