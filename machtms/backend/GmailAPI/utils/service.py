import logging
from datetime import timezone
logger = logging.getLogger(__name__)
import os
from pathlib import Path
from django.conf import settings
from googleapiclient import errors
from google_auth_oauthlib.flow import Flow, InstalledAppFlow
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from machtms.backend.GmailAPI.models import GmailBillingConfig, GoogleCredentials

class GmailService:
    token_uri = 'https://oauth2.googleapis.com/token'
    auth_uri = 'https://accounts.google.com/o/oauth2/auth'
    try:
        client_id = settings.GMAIL_CLIENT_ID
        client_secret = settings.GMAIL_CLIENT_SECRET
        redirect_uris = settings.GMAIL_CLIENT_REDIRECT_URIS
        scopes = settings.GMAIL_CLIENT_SCOPES
    except AttributeError:
        logger.warning("GMAIL environments not set")
        client_id = None
        client_secret = None
        redirect_uris = None

        scopes = ['https://www.googleapis.com/auth/gmail.compose',
                    'https://www.googleapis.com/auth/gmail.send']


    def __init__(self, credentials, organization=None):
        self.credentials = credentials
        self.service = build('gmail', 'v1', credentials=credentials)
        self.organization = organization
        self.get_user_email().set_user_credentials()


    def get_user_email(self):
        """ Requires the scope https://www.googleapis.com/auth/gmail.metadata """
        profile = self.service.users().getProfile(userId='me').execute()
        self.email = profile.get("emailAddress")
        return self


    def set_user_credentials(self):
        creds, is_created =GoogleCredentials.objects.update_or_create(
            organization=self.organization,
            email=self.email,
            defaults={
                'token': self.credentials.token,
                'refresh_token': self.credentials.refresh_token,
                'expiry': self.credentials.expiry.astimezone(timezone.utc),
            }
        )
        if is_created:
            GmailBillingConfig.objects.create(
                organization=self.organization,
                gmail_credentials=creds
            )
        return self


    @classmethod
    def sign_out(cls, organization, with_email):
        creds = GoogleCredentials.objects.get(
            organization=organization,
            with_email=with_email
        )
        creds.delete()


    @classmethod
    def authenticate(cls, with_email, organization=None):
        """
        Authenticate with token or refresh token to start the service
        """
        if settings.DEBUG is True and organization is None:
            raise Exception("In production. Organization must be set")
        try:
            user_credentials = GoogleCredentials.objects.get(organization=organization, email=with_email)
            creds = Credentials(
                token_uri=cls.token_uri,
                client_id=cls.client_id,
                client_secret=cls.client_secret,
                token=user_credentials.token,
                refresh_token=user_credentials.refresh_token,
                expiry=user_credentials.expiry
            )
        except GoogleCredentials.DoesNotExist:
            creds = None

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                raise Exception("User needs to authenticate via frontend first")
        return cls(creds, organization)


    @classmethod
    def setup_installed_flow(cls):
        """
        NOTE: used for development and testing

        This sets up credentials via the installed-app oauth flow.

        """
        BASE_DIR = settings.BASE_DIR
        SECRETS = Path(BASE_DIR) / "api" / "secrets"
        CREDENTIALS_PATH = SECRETS / 'gmail_test_credentials.json'
        TOKENS_PATH = SECRETS / 'gmail_test_tokens.json'

        creds = None
        if os.path.exists(TOKENS_PATH):
            creds = Credentials.from_authorized_user_file(TOKENS_PATH, cls.scopes)
        # If there are no (valid) credentials available, let the user log in.
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(
                    CREDENTIALS_PATH, cls.scopes)
                creds = flow.run_local_server(port=0)
            # Save the credentials for the next run
            with open(TOKENS_PATH, 'w') as token:
                token.write(creds.to_json())
        logger.debug([type(creds.expiry), creds.expiry])
        return cls(creds)


    @classmethod
    def exchange_code(cls, flow_code, redirect_uri, organization):
        """
        The following will come from django.conf.settings:
        - client_id, client_secret, redirect_uris[],

        """
        flow = Flow.from_client_config(
            {
                "web": {
                    "client_id": cls.client_id,
                    "client_secret": cls.client_secret,
                    "redirect_uris": cls.redirect_uris,
                    "auth_uri": cls.auth_uri,
                    "token_uri": cls.token_uri,
                },
            },
            scopes=settings.GMAIL_CLIENT_SCOPES
        )
        flow.redirect_uri = redirect_uri
        flow.fetch_token(code=flow_code)

        creds = flow.credentials
        return cls(creds, organization)


    def send_email(self, message: dict):
        try:
            message = self.service.users().messages().send(userId='me', body=message).execute()
            return message
        except errors.HttpError as error:
            print('An error occurred: %s' % error)

