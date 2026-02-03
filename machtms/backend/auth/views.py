from knox.models import AuthToken
from rest_framework import generics, permissions, exceptions, status
from django.conf import settings
from environments import env
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from machtms.backend.auth.models import OrganizationAPIKey, UserProfile
from machtms.backend.auth.serializers import LoginSerializer, UserSerializer, RegisterSerializer
from knox.views import LogoutView
from machtms.core.auth.authentication import TMSAuthentication

IS_SECURE = getattr(settings, 'IS_SECURE', False)


@api_view(['POST'])
@permission_classes([permissions.AllowAny])
def check_auth(request):
    if(request.user.is_authenticated):
        return Response(status=status.HTTP_200_OK)
    response = Response(status=status.HTTP_401_UNAUTHORIZED)
    response.delete_cookie('auth_token')
    return response


# Login View
class LoginView(generics.GenericAPIView):
    serializer_class = LoginSerializer
    permission_classes = [
        permissions.AllowAny,
    ]

    def handle_exception(self, exc):
        return self.post(self.request)

    def post(self, request):
        try:
            serializer = self.get_serializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            user = serializer.validated_data

            token = AuthToken.objects.create(user)
            response = Response({
                "user": UserSerializer(
                    user, context=self.get_serializer_context()
                ).data
            })
            response.set_cookie(
                'auth_token',
                token[1],
                samesite='Lax',
                httponly=True,
                secure=IS_SECURE,
                domain=f".{env('HOST')}"
            )
            return response
        except exceptions.ValidationError:
            return Response(status=status.HTTP_401_UNAUTHORIZED)


class ObtainAPIKey(generics.GenericAPIView):
    serializer_class = LoginSerializer
    permission_classes = [
        permissions.AllowAny,
    ]

    def handle_exception(self, exc):
        return self.post(self.request)

    def post(self, request):
        # logger = logging.getLogger("mylogger")
        # logger.info(request.headers)
        try:
            serializer = self.get_serializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            user_pk = serializer.validated_data.pk
            organization = UserProfile.objects.get(user=user_pk).organization
            _, key = OrganizationAPIKey.objects.create_key(
                name="_clientapi_key", organization=organization)
            response = Response({
                "api_key": key
            }, status=status.HTTP_200_OK)
            return response
        except exceptions.ValidationError:
            return Response(status=status.HTTP_401_UNAUTHORIZED)


class TMSLogoutView(LogoutView):
    permission_classes = [permissions.IsAuthenticated]
    authentication_classes = [TMSAuthentication]

    def post(self, request):
        response = Response()
        response.delete_cookie('auth_token')
        super().post(request)
        return response


class RegisterView(generics.GenericAPIView):
    """
    Organization signing up.
    Required:
        - a User model with email and password.
        - Organization post form to assign this user
    """
    serializer_class = RegisterSerializer
    permission_classes = [permissions.AllowAny]

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        token = AuthToken.objects.create(user)
        return Response({
            "user": UserSerializer(
                user,
                context=self.get_serializer_context()
            ).data,
            "token": token[1]
        })


class MainUser(generics.RetrieveAPIView):
    permission_classes = [
        permissions.IsAuthenticated,
    ]

    serializer_class = UserSerializer

    def get_object(self):
        return self.request.user
