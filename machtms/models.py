# Re-export all models from backend for Django discovery
from machtms.backend import (
    # Auth
    CustomUserManager,
    OrganizationAPIKey,
    Organization,
    OrganizationUser,
    UserProfile,
    # Addresses
    BaseAddress,
    Address,
    AddressUsageAccumulate,
    AddressUsageByCustomerAccumulate,
    # Carriers
    Carrier,
    Driver,
    # Customers
    Customer,
    CustomerRepresentative,
    CustomerAP,
    # Loads
    LoadStatus,
    BillingStatus,
    TrailerType,
    Load,
    # Legs
    Leg,
    ShipmentAssignment,
    # Routes
    Stop,
    # DocumentManager
    DocumentContext,
    DocumentQueue,
    S3UploadImage,
    DocumentResults,
    DirectUpload,
    PostShipmentDocument,
    SessionUploadLog,
    UploadLog,
    # GmailAPI
    GoogleCredentials,
    GmailBillingConfig,
    GmailInvoiceLog,
    AccountRep,
    AccountsPayableContact,
    FactoringContact,
    FactoringDefaultSettings,
)

__all__ = [
    # Auth
    'CustomUserManager',
    'OrganizationAPIKey',
    'Organization',
    'OrganizationUser',
    'UserProfile',
    # Addresses
    'BaseAddress',
    'Address',
    'AddressUsageAccumulate',
    'AddressUsageByCustomerAccumulate',
    # Carriers
    'Carrier',
    'Driver',
    # Customers
    'Customer',
    'CustomerRepresentative',
    'CustomerAP',
    # Loads
    'LoadStatus',
    'BillingStatus',
    'TrailerType',
    'Load',
    # Legs
    'Leg',
    'ShipmentAssignment',
    # Routes
    'Stop',
    # DocumentManager
    'DocumentContext',
    'DocumentQueue',
    'S3UploadImage',
    'DocumentResults',
    'DirectUpload',
    'PostShipmentDocument',
    'SessionUploadLog',
    'UploadLog',
    # GmailAPI
    'GoogleCredentials',
    'GmailBillingConfig',
    'GmailInvoiceLog',
    'AccountRep',
    'AccountsPayableContact',
    'FactoringContact',
    'FactoringDefaultSettings',
]
