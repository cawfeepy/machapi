import logging
from machtms.core.envctrl import env
from machtms.core.utils.url.parser import configure_allowed_hosts, configure_full_url


CORS_ALLOW_CREDENTIALS = True # not DEBUG
# CORS_ALLOW_ALL_ORIGINS = S.DEBUG or S.INSECURE

ALLOWED_HOSTS = [configure_allowed_hosts(hostname) for hostname in env.django.ALLOWED_HOSTS]
# CORS_ALLOWED_ORIGINS = [configure_full_url(url) for url in env.django.CORS_ALLOWED_ORIGINS]
CSRF_TRUSTED_ORIGINS = [configure_full_url(url) for url in env.django.CSRF_TRUSTED_ORIGINS]
CORS_ALLOWED_ORIGIN_REGEXES = env.django.CORS_ALLOWED_ORIGIN_REGEXES
# CORS_EXPOSE_HEADERS = (
#     'content-disposition',
#     'content-length',
# )
print("inside origins", ALLOWED_HOSTS)
print("inside origins", CSRF_TRUSTED_ORIGINS)
print("after allowed_hosts")
