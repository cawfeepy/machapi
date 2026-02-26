"""
This is a django-split-settings main file.

For more information read this:
https://github.com/sobolevn/django-split-settings
https://sobolevn.me/2017/04/managing-djangos-settings

To change settings file:
`DJANGO_ENV=production python manage.py runserver`
"""

from split_settings.tools import include
from machtms.core.envctrl import get_env

env = get_env()

ENV = env.django.DJANGO_ENV

_settings = [
        "components/*.py",
        ]

include(*_settings)
