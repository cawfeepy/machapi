import logging
from machtms.core.envctrl import env

L = logging.getLogger(__name__)

if env.gmail.available:
    cfg = env.gmail.config
    GMAIL_API_CLIENT_SECRET = cfg.CLIENT_SECRET.get_secret_value()
    GMAIL_API_TOKEN_REDIRECT = cfg.REDIRECT_URI
    GMAIL_API_SCOPES = cfg.SCOPES
    GMAIL_API_CLIENT_ID = cfg.CLIENT_ID
