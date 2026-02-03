import logging
from environments import env

L = logging.getLogger(__name__)

GMAIL_API_CLIENT_SECRET = env('GMAIL_API_CLIENT_SECRET')
GMAIL_API_TOKEN_REDIRECT = env('GMAIL_API_REDIRECT_URI')
GMAIL_API_SCOPES = env.list('GMAIL_API_SCOPES')
GMAIL_API_CLIENT_ID = env('GMAIL_API_CLIENT_ID')

# if any(variable == '' for variable in [
#     GMAIL_API_CLIENT_SECRET,
#     GMAIL_API_TOKEN_REDIRECT,
#     GMAIL_API_SCOPES,
#     GMAIL_API_CLIENT_ID
# ]):
#     L.error("Some GMAIL_API_* env-vars aren't set")
#
