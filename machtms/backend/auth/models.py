from rest_framework_api_key.models import AbstractAPIKey
from django.contrib.auth.models import (
    BaseUserManager,
    AbstractUser)
from django.db import models
from django.utils.translation import gettext_lazy as _
import random

from django.conf import settings
from machtms.core.base.models import TMSModel


class CustomUserManager(BaseUserManager):
    """
    Custom user model manager where email is the unique identifiers
    for authentication instead of usernames.
    """
    def create_user(self, email, password, **extra_fields):
        """
        Create and save a User with the given email and password.
        """
        if not email:
            raise ValueError(_('The Email must be set'))
        user = self.model(email=email.lower(), **extra_fields)
        user.set_password(password)
        user.save()
        return user


    # TODO - make sure user with userprofile is created
    def create_user_atomic(self, email, password, **kwargs):
        if not email:
            raise ValueError(_('The Email must be set'))
        email = self.normalize_email(email)
        user = self.model(email=email, **kwargs)
        user.set_password(password)
        return user


    def create_superuser(self, email, password, **extra_fields):
        """
        Create and save a SuperUser with the given email and password.
        """
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_active', True)

        if extra_fields.get('is_staff') is not True:
            raise ValueError(_('Superuser must have is_staff=True.'))
        if extra_fields.get('is_superuser') is not True:
            raise ValueError(_('Superuser must have is_superuser=True.'))
        return self.create_user(email, password, **extra_fields)


class OrganizationAPIKey(AbstractAPIKey):
    organization = models.ForeignKey(
        'Organization',
        on_delete=models.CASCADE,
        related_name='api_keys'
    )


    def __str__(self):
        return self.organization.company_name


class Organization(models.Model):
    load_set: "QuerySet[Load]"
    company_name = models.CharField(max_length=50)
    street_address = models.CharField(max_length=100, blank=True, default="")
    phone = models.CharField(max_length=14)
    email = models.EmailField(_("email address"))
    invoice_id = models.IntegerField(default=30100)
    logo_src = models.URLField(blank=True)
    invoice_remit_message = models.CharField(max_length=200, blank=True)

    CUTOFF = [
        ('SUNDAY',    ((0, 'SUN'),)),
        ('MONDAY',    ((1, 'MON'),)),
        ('TUESDAY',   ((2, 'TUE'),)),
        ('WEDNESDAY', ((3, 'WED'),)),
        ('THURSDAY',  ((4, 'THU'),)),
        ('FRIDAY',    ((5, 'FRI'),)),
        ('SATURDAY',  ((6, 'SAT'),)),
    ]
    payroll_cutoff = models.IntegerField(choices=CUTOFF, default=4)


    @property
    def assign_invoice_id(self):
        ids = [ 30000, 30100, 40000, 40100, ]
        return random.choice(ids)


    def __str__(self):
        return f"[{self.pk}] {self.company_name}"


    def save(self, *args, **kwargs):
        if not self.pk:
            # assign an initial invoiceId
            self.invoice_id = self.assign_invoice_id
        super(Organization, self).save(*args, **kwargs)



class OrganizationUser(AbstractUser) :
    userprofile: "UserProfile"
    username = None
    email = models.EmailField(_('email address'), unique=True)

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['first_name',
                       'last_name',
                       'password',
                       ]
    objects: BaseUserManager = CustomUserManager()


    def get_full_name(self):
        return f'{self.first_name} {self.last_name}'



class UserProfile(TMSModel):
    ''' Role: Manager, Dispatcher, Specialist '''
    user = models.OneToOneField('OrganizationUser', on_delete=models.CASCADE)
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, null=settings.DEBUG, blank=settings.DEBUG)
    load_list_index = models.IntegerField(default=0)
    activePath = models.CharField(
        max_length=1056,
        blank=True,
        default='/api/loads/same_day')

    class Meta:
        verbose_name = "UserProfile"

    def __str__(self):
        return f"{self.user.first_name} {self.user.last_name} - {self.user.email} // {self.organization.company_name}"
