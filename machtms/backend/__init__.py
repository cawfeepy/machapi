# Import all models from backend submodules for Django discovery

# Auth models
from machtms.backend.auth import (
    CustomUserManager,
    OrganizationAPIKey,
    Organization,
    OrganizationUser,
    UserProfile,
)

# Address models
from machtms.backend.addresses import (
    BaseAddress,
    Address,
    AddressUsageAccumulate,
    AddressUsageByCustomerAccumulate,
)

# Carrier models
from machtms.backend.carriers import (
    Carrier,
    Driver,
)

# Customer models
from machtms.backend.customers import (
    Customer,
    CustomerRepresentative,
    CustomerAP,
)

# Load models
from machtms.backend.loads import (
    LoadStatus,
    BillingStatus,
    TrailerType,
    Load,
)

# Leg models
from machtms.backend.legs import (
    Leg,
    ShipmentAssignment,
)

# Route models
from machtms.backend.routes import (
    Stop,
)

# DocumentManager models
from machtms.backend.DocumentManager import (
    DocumentContext,
    DocumentQueue,
    S3UploadImage,
    DocumentResults,
    DirectUpload,
    PostShipmentDocument,
    SessionUploadLog,
    UploadLog,
)

# GmailAPI models
from machtms.backend.GmailAPI import (
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
