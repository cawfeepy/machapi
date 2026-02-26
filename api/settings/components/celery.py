# https://www.shubhamdipt.com/blog/django-celery-and-rabbitmq/
from machtms.core.envctrl import env

if env.celery.available:
    cfg = env.celery.config
    CELERY_BROKER_URL = cfg.BROKER_URL
    CELERY_RESULT_BACKEND = cfg.RESULT_BACKEND

    CELERY_ACCEPT_CONTENT = cfg.ACCEPT_CONTENT
    CELERY_TASK_SERIALIZER = cfg.TASK_SERIALIZER
    CELERY_RESULT_SERIALIZER = cfg.RESULT_SERIALIZER
    CELERY_TIMEZONE = cfg.TIMEZONE

    CELERY_TASK_TRACK_STARTED = cfg.TASK_TRACK_STARTED
    CELERY_TASK_TIME_LIMIT = cfg.TASK_TIME_LIMIT

    # CeleryController signal logging settings
    # Set to True to enable logging for successful task completions
    CELERY_ENABLE_SUCCESS_LOGGING = False
    # Set to True to enable logging before task execution starts
    CELERY_ENABLE_PRERUN_LOGGING = False
