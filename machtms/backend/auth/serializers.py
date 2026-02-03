from django.contrib.auth import authenticate, get_user_model
from rest_framework import serializers
from machtms.backend.auth.models import OrganizationAPIKey, OrganizationUser, UserProfile, Organization


User = get_user_model()

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ('id', 'email',)


class OrganizationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Organization
        fields = ('logo_src',
                  'invoice_remit_message',
                  'street_address',
                  'company_name',
                  'phone', 'email',)


class OrganizationAPIKeySerializer(serializers.ModelSerializer):
    class Meta:
        model   = OrganizationAPIKey
        fields  = ('__all__')


class UserProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserProfile
        fields = ('__all__')


class RegisterSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = (
            'id', 
            'email',
            'password', 
            'first_name',
            'last_name',
        )
        extra_kwargs = { 'password':
                        {'write_only': True} }

    def create(self, vd):
        email, pw = (vd.pop('email', None),
                     vd.pop('password', None))
        user = User\
            .objects\
            .create_user(email, pw, **vd)
        return user




class LoginSerializer(serializers.Serializer):
    email = serializers.CharField()
    password = serializers.CharField()

    def validate(self, data):
        msg = "Invalid credentials"

        email = data.pop('email', None)
        if email is None:
            raise serializers.ValidationError(msg)

        user = authenticate(email=email.lower(), **data)
        if user and user.is_active:
            return user
        raise serializers.ValidationError(msg)
