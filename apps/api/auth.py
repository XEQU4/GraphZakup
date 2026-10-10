"""Same-origin session bootstrap/login/logout for the React client."""
from django.contrib.auth import authenticate, login, logout
from django.middleware.csrf import get_token, rotate_token
from drf_spectacular.utils import extend_schema
from rest_framework import serializers
from rest_framework.authentication import SessionAuthentication
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from .throttling import AuthenticationThrottle

from .common import ApiError, ApiView, StrictSerializer


class SessionUserSerializer(serializers.Serializer):
    id = serializers.IntegerField(allow_null=True)
    username = serializers.CharField(allow_null=True)
    email = serializers.CharField(allow_null=True, allow_blank=True)
    role = serializers.ChoiceField(choices=['anonymous', 'user', 'staff'])


class CapabilitiesSerializer(serializers.Serializer):
    can_save_views = serializers.BooleanField()
    can_start_jobs = serializers.BooleanField()


class SessionSerializer(serializers.Serializer):
    user = SessionUserSerializer()
    csrf_token = serializers.CharField()
    capabilities = CapabilitiesSerializer()


class LoginSerializer(StrictSerializer):
    username = serializers.CharField(max_length=150)
    password = serializers.CharField(max_length=128, trim_whitespace=False, write_only=True)


def session_result(request):
    user = request.user
    authenticated = user.is_authenticated
    return {'user': {'id': user.pk if authenticated else None,
        'username': user.get_username() if authenticated else None,
        'email': user.email if authenticated else None,
        'role': 'staff' if authenticated and user.is_staff else 'user' if authenticated else 'anonymous'},
        'csrf_token': get_token(request._request),
        'capabilities': {'can_save_views': bool(authenticated),
            'can_start_jobs': bool(authenticated and user.is_staff)}}


class LoginSessionAuthentication(SessionAuthentication):
    def authenticate(self, request):
        # Standard SessionAuthentication skips CSRF for anonymous users; login must not.
        self.enforce_csrf(request)
        return super().authenticate(request)


class SessionView(ApiView):
    @extend_schema(responses=SessionSerializer, description='Get current role and a CSRF token. '
        'The response sets a csrftoken cookie. Send X-CSRFToken and session cookies on writes.')
    def get(self, request):
        return Response(session_result(request), headers={'Cache-Control': 'no-store'})


class LoginView(ApiView):
    authentication_classes = [LoginSessionAuthentication]
    throttle_classes = [AuthenticationThrottle]
    throttle_scope = 'api_login'

    @extend_schema(request=LoginSerializer, responses=SessionSerializer, description='CSRF-protected '
        'Django session login. Bootstrap CSRF with GET /api/v1/session/ first.')
    def post(self, request):
        data = LoginSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        user = authenticate(request=request._request, **data.validated_data)
        if user is None:
            raise ApiError('invalid_credentials', 'Invalid username or password.', 403)
        login(request._request, user)
        # Refresh DRF request user after Django rotates the login session/CSRF secret.
        request.user = user
        return Response(session_result(request), headers={'Cache-Control': 'no-store'})


class LogoutView(ApiView):
    permission_classes = [IsAuthenticated]

    @extend_schema(request=None, responses={204: None}, description='End this authenticated session. '
        'Requires CSRF. Bootstrap again before a subsequent login.')
    def post(self, request):
        if request.data:
            raise ApiError('validation_error', 'Logout does not accept a request body.')
        logout(request._request)
        rotate_token(request._request)
        return Response(status=204, headers={'Cache-Control': 'no-store'})
