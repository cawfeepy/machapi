import os
from machtms.core.envctrl import env

curr_dir = os.path.dirname(__file__)
BASE_DIR = env.BASE_DIR

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "detailed": {
            "class": 'api.logconfig.formatters.colorizer.ColorFormatter',  # Use custom formatter
            # "format": "{levelname:<6} - ^{lineno:<4}:{module}.{funcName} > {message}",
            # "style": "{",  # Required for `{}` style formatting
        },
        "verbose": {
            "format": "{levelname} {name} [{asctime}] {message}",
            "style": "{",
        },
    },
    "handlers": {
        "null_handler": {
            "level": "ERROR",
            "class": "logging.NullHandler",
        },
        "console": {
            "level": "DEBUG",
            "class": "logging.StreamHandler",
            "formatter": "detailed",
        },
        "celery_file": {
            "level": "ERROR",
            "class": "logging.handlers.RotatingFileHandler",
            "filename": os.path.join(BASE_DIR, "machtms/logs/celery_logs.txt"),
            "maxBytes": 10485760,  # 10 MB
            "backupCount": 5,
            "formatter": "verbose",
        },
    },
    "loggers": {
        "django.request": {
            "handlers": ["console"],
            "level": "DEBUG" if env.django.DEBUG else "INFO",
            "propagate": False,
        },
        "tms": {
            "handlers": ["console"],
            "level": "DEBUG" if env.django.DEBUG else "INFO",
            "propagate": False,
        },
        "api": {
            "handlers": ["console"],
            "level": "DEBUG" if env.django.DEBUG else "INFO",
            "propagate": False,
        },
        "fontTools.subset": {
            "handlers": ["null_handler"],
            "propagate": False
        },
        "machtms.core.celerycontroller": {
            "handlers": ["console", "celery_file"],
            "level": "DEBUG" if env.django.DEBUG else "ERROR",
            "propagate": False,
        },
        "machtms.core.celerycontroller.signals": {
            "handlers": ["console", "celery_file"],
            "level": "DEBUG" if env.django.DEBUG else "ERROR",
            "propagate": False,
        },
        "machtms.core.base": {
            "handlers": ["console"],
            "level": "DEBUG" if env.django.DEBUG else "INFO",
            "propagate": False,
        },
        "machtms.core.utils.logs": {
            "handlers": ["console"],
            "level": "DEBUG" if env.django.DEBUG else "INFO",
            "propagate": False,
        },
    },
}

# LOGGING = {
#     "version": 1,
#     "disable_existing_loggers": False,
#     "root": {"level": "INFO", "handlers": ["file__INFO", "stream_INFO"]},
#     "handlers": {
#         'console': {
#             'class': 'logging.StreamHandler',
#         },
#         "file__INFO": {
#             "level": "INFO",
#             "class": "logging.FileHandler",
#             "filename": os.path.join(curr_dir, 'INFO.log'),
#             "formatter": "tms",
#         },
#         "stream_INFO": {
#             "level": "INFO",
#             "class": "logging.StreamHandler",
#             "formatter": "tms",
#         },
#     },
#     "loggers": {
#         "django": {
#             "handlers": ["file__INFO", "stream_INFO"],
#             "level": "INFO",
#             "propagate": True
#         },
#         'django.db.backends': {
#             'handlers': ['console'],
#             'level': 'DEBUG',  # Log all database operations
#         },
#     },
#     "formatters": {
#         "tms": {
#             "format": (
#                 u"%(asctime)s [%(levelname)-8s] "
#                 "(%(module)s.%(funcName)s) %(message)s"
#             ),
#             "datefmt": "%Y-%m-%d %H:%M:%S",
#         },
#     },
# }
