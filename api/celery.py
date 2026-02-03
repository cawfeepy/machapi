"""
Celery application configuration for machTMS.

This module initializes the Celery application and configures it to work
with Django settings and RabbitMQ as the message broker.

Signal handlers are initialized for centralized task execution logging.
Configure optional logging via Django settings:
    - CELERY_ENABLE_SUCCESS_LOGGING: Log task successes (default: False)
    - CELERY_ENABLE_PRERUN_LOGGING: Log task pre-run events (default: False)
"""

import os

from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "api.settings")

app = Celery("machtms")

app.config_from_object("django.conf:settings", namespace="CELERY")

app.autodiscover_tasks()

# Initialize Celery signal handlers for centralized logging
from machtms.core.celerycontroller import setup_celery_logging

setup_celery_logging()
