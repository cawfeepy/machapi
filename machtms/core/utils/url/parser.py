# TODO include the environment using environment controller

from typing import TypeAlias
from urllib.parse import urlparse

ALLOWED_HOSTS: TypeAlias = str
CSRF_TRUSTED_ORIGINS: TypeAlias = str
CORS_ALLOWED_ORIGINS: TypeAlias = str

def get_parsed_url(url):
    parsed_url = urlparse(url)
    print(parsed_url)
    return parsed_url


def configure_full_url(url) -> CSRF_TRUSTED_ORIGINS | CORS_ALLOWED_ORIGINS:
    parsed_url = get_parsed_url(url)
    hostname = parsed_url.netloc
    origin = f"{parsed_url.scheme}://{hostname}"
    return origin


def configure_allowed_hosts(hostname) -> ALLOWED_HOSTS:
    if hostname == '*':
        return '*'
    allowed_hosts = f".{hostname}"
    return allowed_hosts 
