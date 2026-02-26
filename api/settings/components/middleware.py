from machtms.core.envctrl import env

'''
configs/middleware.py

Depends on the environment
- when working in a local dev environment
it's convenient to remove CORS and CSRF
to avoid boilerplate setup.
'''

DEBUG = env.django.DEBUG
INSECURE = env.django.INSECURE

CSRF_MIDDLEWARES = [
    "machtms.core.middleware.exemption_csrf.ExemptCSRFMiddleware",
    'django.middleware.csrf.CsrfViewMiddleware'
]

MIDDLEWARE = [
    CSRF_MIDDLEWARES[0] if DEBUG or INSECURE else CSRF_MIDDLEWARES[-1],
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'machtms.core.middleware.organization.OrganizationMiddleware',
    'machtms.core.testing.OrganizationTestMiddleware',  # Must be after OrganizationMiddleware
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]
