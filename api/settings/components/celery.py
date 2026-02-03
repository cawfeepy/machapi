# https://www.shubhamdipt.com/blog/django-celery-and-rabbitmq/
from environments import env

if env("USE_CELERY"):
    CELERY_BROKER_URL = env("CELERY_BROKER_URL")
    CELERY_RESULT_BACKEND = env("CELERY_RESULT_BACKEND", default=None)

    CELERY_ACCEPT_CONTENT = ["application/json"]
    CELERY_TASK_SERIALIZER = "json"
    CELERY_RESULT_SERIALIZER = "json"
    CELERY_TIMEZONE = "UTC"

    CELERY_TASK_TRACK_STARTED = True
    CELERY_TASK_TIME_LIMIT = 30 * 60  # 30 minutes

    # CeleryController signal logging settings
    # Set to True to enable logging for successful task completions
    CELERY_ENABLE_SUCCESS_LOGGING = False
    # Set to True to enable logging before task execution starts
    CELERY_ENABLE_PRERUN_LOGGING = False
