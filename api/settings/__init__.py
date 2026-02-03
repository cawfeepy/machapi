"""
This is a django-split-settings main file.

For more information read this:
https://github.com/sobolevn/django-split-settings
https://sobolevn.me/2017/04/managing-djangos-settings

To change settings file:
`DJANGO_ENV=production python manage.py runserver`
"""

from split_settings.tools import include, optional
from environments import env

ENV = env("DJANGO_ENV")

_settings = [
        "components/*.py",
        optional(f"environments/databases.{ENV}.py"),
        optional(f"environments/redis.{ENV}.py"),
        ]

include(*_settings)

