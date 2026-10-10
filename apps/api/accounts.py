"""CSRF-protected self-service account operations; no domain-data orchestration."""
from django.contrib.auth import get_user_model, login, update_session_auth_hash
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError, transaction
from django.middleware.csrf import rotate_token
from drf_spectacular.utils import extend_schema
from rest_framework import serializers
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle

from .auth import LoginSessionAuthentication, SessionSerializer, session_result
from .common import ApiError, ApiView, StrictSerializer
from .common import ApiListView, PaginationQuerySerializer
from apps.graph.models import GraphViewState


def username_value(value):
    User = get_user_model()
    value = User.normalize_username(value.strip())
    if not value or len(value) > 150:
        raise serializers.ValidationError('Enter a username of 1 to 150 characters.')
    try:
        for validator in User._meta.get_field('username').validators:
            validator(value)
    except DjangoValidationError as error:
        raise serializers.ValidationError(error.messages) from None
    return value


def password_value(value, user, field):
    try:
        validate_password(value, user=user)
    except DjangoValidationError as error:
        raise serializers.ValidationError({field: error.messages}) from None


def identity_conflict(error, *, username, email=None, exclude_pk=None):
    """Called outside the failed atomic block; never return SQL or submitted secrets."""
    users = get_user_model().objects.all()
    if exclude_pk is not None:
        users = users.exclude(pk=exclude_pk)
    details = {}
    if users.filter(username__iexact=username).exists():
        details['username'] = ['This username is already in use.']
    if email is not None and users.filter(email__iexact=email).exists():
        details['email'] = ['This email address is already in use.']
    if details:
        raise serializers.ValidationError(details) from None
    # Non-identity database failures remain safe internal errors at the API boundary.
    raise error


class RegisterSerializer(StrictSerializer):
    username = serializers.CharField(max_length=150)
    email = serializers.EmailField(max_length=254)
    password = serializers.CharField(min_length=8, max_length=128, trim_whitespace=False, write_only=True)
    password_confirm = serializers.CharField(max_length=128, trim_whitespace=False, write_only=True)

    def validate_username(self, value):
        value = username_value(value)
        if get_user_model().objects.filter(username__iexact=value).exists():
            raise serializers.ValidationError('This username is already in use.')
        return value

    def validate_email(self, value):
        value = value.strip().lower()
        if get_user_model().objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError('This email address is already in use.')
        return value

    def validate(self, attrs):
        if attrs['password'] != attrs['password_confirm']:
            raise serializers.ValidationError({'password_confirm': ['Passwords do not match.']})
        candidate = get_user_model()(username=attrs['username'], email=attrs['email'])
        password_value(attrs['password'], candidate, 'password')
        return attrs


class ProfileSerializer(serializers.Serializer):
    username = serializers.CharField()
    email = serializers.CharField(allow_blank=True)
    role = serializers.ChoiceField(choices=['user', 'staff'])
    date_joined = serializers.DateTimeField()


class UsernameSerializer(StrictSerializer):
    username = serializers.CharField(max_length=150)

    def validate_username(self, value):
        value = username_value(value)
        user = self.context['user']
        if get_user_model().objects.exclude(pk=user.pk).filter(username__iexact=value).exists():
            raise serializers.ValidationError('This username is already in use.')
        return value


class PasswordSerializer(StrictSerializer):
    current_password = serializers.CharField(max_length=128, trim_whitespace=False, write_only=True)
    new_password = serializers.CharField(min_length=8, max_length=128, trim_whitespace=False, write_only=True)
    new_password_confirm = serializers.CharField(max_length=128, trim_whitespace=False, write_only=True)

    def validate(self, attrs):
        if attrs['new_password'] != attrs['new_password_confirm']:
            raise serializers.ValidationError({'new_password_confirm': ['Passwords do not match.']})
        return attrs


def profile_result(user):
    return {'username': user.get_username(), 'email': user.email,
            'role': 'staff' if user.is_staff else 'user', 'date_joined': user.date_joined}


class AccountGraphViewSerializer(serializers.ModelSerializer):
    cluster_uuid = serializers.UUIDField(source='cluster.uuid')
    cluster_name = serializers.CharField(source='cluster.name')
    cluster_is_active = serializers.BooleanField(source='cluster.is_active')
    saved_snapshot_version = serializers.IntegerField(source='snapshot.version')
    current_snapshot_version = serializers.IntegerField(source='cluster.current_snapshot.version', allow_null=True)

    class Meta:
        model = GraphViewState
        fields = ['cluster_uuid', 'cluster_name', 'cluster_is_active',
                  'saved_snapshot_version', 'current_snapshot_version', 'revision', 'updated_at']


class AccountGraphViewList(ApiListView):
    permission_classes = [IsAuthenticated]
    query_serializer_class = PaginationQuerySerializer
    serializer_class = AccountGraphViewSerializer

    @extend_schema(parameters=[PaginationQuerySerializer], responses=AccountGraphViewSerializer(many=True),
        description='List only the current account\'s saved graph layouts, newest save first. '
        'Returns navigation metadata without coordinates, identifiers of users or graph regeneration.')
    def get(self, request, *args, **kwargs):
        response = super().get(request, *args, **kwargs)
        response['Cache-Control'] = 'no-store'
        return response

    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            return GraphViewState.objects.none()
        return (GraphViewState.objects.filter(user=self.request.user).exclude(payload={})
            .select_related('cluster__current_snapshot', 'snapshot').order_by('-updated_at', '-pk'))


class RegisterView(ApiView):
    authentication_classes = [LoginSessionAuthentication]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'api_register'

    @extend_schema(request=RegisterSerializer, responses={201: SessionSerializer},
        description='Register an ordinary account and sign in. Requires anonymous CSRF bootstrap. '
        'Email is a contact address, not an email-verification result. Email and username are unique ignoring case.')
    def post(self, request):
        if request.user.is_authenticated:
            raise ApiError('already_authenticated', 'Sign out before creating another account.', 409)
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        try:
            with transaction.atomic():
                user = get_user_model().objects.create_user(username=data['username'], email=data['email'],
                    password=data['password'], is_staff=False, is_superuser=False)
        except IntegrityError as error:
            identity_conflict(error, username=data['username'], email=data['email'])
        login(request._request, user, backend='django.contrib.auth.backends.ModelBackend')
        request.user = user
        return Response(session_result(request), status=201, headers={'Cache-Control': 'no-store'})


class ProfileView(ApiView):
    permission_classes = [IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'api_account'

    @extend_schema(responses=ProfileSerializer, description='Read only the current account profile.')
    def get(self, request):
        return Response(profile_result(request.user), headers={'Cache-Control': 'no-store'})

    @extend_schema(request=UsernameSerializer, responses=ProfileSerializer,
        description='Change the current username. Email, permissions and other accounts cannot be edited.')
    def patch(self, request):
        serializer = UsernameSerializer(data=request.data, context={'user': request.user})
        serializer.is_valid(raise_exception=True)
        username = serializer.validated_data['username']
        try:
            with transaction.atomic():
                user = get_user_model().objects.select_for_update().get(pk=request.user.pk)
                user.username = username
                user.save(update_fields=['username'])
        except IntegrityError as error:
            identity_conflict(error, username=username, exclude_pk=request.user.pk)
        request.user = user
        return Response(profile_result(user), headers={'Cache-Control': 'no-store'})


class PasswordView(ApiView):
    permission_classes = [IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'api_password'

    @extend_schema(request=PasswordSerializer, responses=SessionSerializer,
        description='Check the current password and save a validated new password. Keep this session, '
        'invalidate other sessions and rotate CSRF. No email is sent.')
    def post(self, request):
        serializer = PasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        with transaction.atomic():
            user = get_user_model().objects.select_for_update().get(pk=request.user.pk)
            if not user.check_password(data['current_password']):
                raise serializers.ValidationError({'current_password': ['The current password is incorrect.']})
            password_value(data['new_password'], user, 'new_password')
            user.set_password(data['new_password'])
            user.save(update_fields=['password'])
        update_session_auth_hash(request._request, user)
        rotate_token(request._request)
        request.user = user
        return Response(session_result(request), headers={'Cache-Control': 'no-store'})
