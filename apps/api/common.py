"""JSON API boundary: strict inputs, bounded pages and stable safe errors."""
import io
import re
from collections.abc import Mapping
from urllib.parse import unquote, urlsplit

from django.core.exceptions import (ValidationError as DjangoValidationError,
    RequestDataTooBig, TooManyFieldsSent, SuspiciousOperation)
from rest_framework import generics, serializers
from rest_framework.authentication import SessionAuthentication
from rest_framework.exceptions import APIException, ErrorDetail, ValidationError, ParseError
from rest_framework.pagination import PageNumberPagination
from rest_framework.parsers import JSONParser
from rest_framework.permissions import AllowAny
from rest_framework.renderers import JSONRenderer
from rest_framework.views import APIView, exception_handler as drf_exception_handler


class ApiError(APIException):
    def __init__(self, code, message, status_code=400, details=None):
        self.status_code = status_code
        self.api_code = code
        self.api_details = details
        self.detail = ErrorDetail(message, code=code)


def exception_handler(exc, context):
    if isinstance(exc, RequestDataTooBig):
        exc = ApiError('payload_too_large', 'The request body exceeds the supported limit.', 413)
    elif isinstance(exc, TooManyFieldsSent):
        exc = ApiError('validation_error', 'Too many request parameters.', 400)
    elif isinstance(exc, SuspiciousOperation):
        exc = ApiError('invalid_request', 'The request is invalid.', 400)
    if isinstance(exc, DjangoValidationError):
        exc = ValidationError(getattr(exc, 'message_dict', None) or exc.messages)
    response = drf_exception_handler(exc, context)
    if response is None:
        # A programming/database failure must never expose tracebacks or credentials.
        import logging
        logging.getLogger('apps.api').error('Unhandled API failure: %s', type(exc).__name__)
        from rest_framework.response import Response
        return Response({'error': {'code': 'internal_error',
            'message': 'The request could not be completed.', 'details': None}}, status=500)
    if isinstance(exc, ApiError):
        code, message, details = exc.api_code, str(exc.detail), exc.api_details
    elif isinstance(exc, ValidationError):
        code, message, details = 'validation_error', 'Invalid request parameters.', exc.detail
    else:
        detail = getattr(exc, 'detail', None)
        code = getattr(detail, 'code', None) or {
            400: 'parse_error', 403: 'permission_denied', 404: 'not_found',
            405: 'method_not_allowed', 406: 'not_acceptable',
            415: 'unsupported_media_type', 429: 'throttled',
        }.get(response.status_code, 'request_error')
        message = str(detail) if isinstance(detail, str) else 'The request was rejected.'
        details = None
    response.data = {'error': {'code': code, 'message': message, 'details': details}}
    return response


class StrictSerializer(serializers.Serializer):
    def to_internal_value(self, data):
        if not isinstance(data, Mapping):
            raise ValidationError({'non_field_errors': ['Expected a JSON object.']})
        unknown = sorted(set(data) - set(self.fields))
        if unknown:
            raise ValidationError({key: ['Unknown parameter.'] for key in unknown})
        return super().to_internal_value(data)


class EmptyQuerySerializer(StrictSerializer):
    pass


class PaginationQuerySerializer(EmptyQuerySerializer):
    page = serializers.IntegerField(min_value=1, max_value=1000000, required=False, default=1)
    page_size = serializers.IntegerField(min_value=1, max_value=100, required=False, default=25)


class ListQuerySerializer(PaginationQuerySerializer):
    search = serializers.CharField(max_length=100, required=False, allow_blank=True, default='')


class StrictQueryMixin:
    query_serializer_class = EmptyQuerySerializer

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        duplicate = {key: ['Specify this parameter once.'] for key in request.query_params
                     if len(request.query_params.getlist(key)) != 1}
        if duplicate:
            raise ValidationError(duplicate)
        serializer_class = getattr(self, 'query_serializer_classes', {}).get(request.method, self.query_serializer_class)
        serializer = serializer_class(data=request.query_params.dict())
        serializer.is_valid(raise_exception=True)
        self.query = serializer.validated_data

    def get_query(self):
        return self.query


class BoundedPagination(PageNumberPagination):
    page_size = 25
    page_size_query_param = 'page_size'
    max_page_size = 100


class BoundedJSONParser(JSONParser):
    def parse(self, stream, media_type=None, parser_context=None):
        data = stream.read(131073)
        if len(data) > 131072:
            raise ApiError('payload_too_large', 'JSON body must not exceed 128 KiB.', 413)
        try:
            return super().parse(io.BytesIO(data), media_type, parser_context)
        except RecursionError:
            raise ParseError('JSON nesting exceeds the supported limit.') from None


class ApiView(StrictQueryMixin, APIView):
    authentication_classes = [SessionAuthentication]
    permission_classes = [AllowAny]
    parser_classes = [BoundedJSONParser]
    renderer_classes = [JSONRenderer]


class ApiListView(StrictQueryMixin, generics.ListAPIView):
    authentication_classes = [SessionAuthentication]
    permission_classes = [AllowAny]
    parser_classes = [BoundedJSONParser]
    renderer_classes = [JSONRenderer]
    pagination_class = BoundedPagination
    query_serializer_class = ListQuerySerializer


class ApiDetailView(StrictQueryMixin, generics.RetrieveAPIView):
    authentication_classes = [SessionAuthentication]
    permission_classes = [AllowAny]
    parser_classes = [BoundedJSONParser]
    renderer_classes = [JSONRenderer]


def safe_source_url(value):
    """Only plain HTTPS source locations; raw query tokens/person identifiers stay private."""
    if not isinstance(value, str) or re.search(r'[\s\x00-\x1f\x7f\\]', value):
        return None
    try:
        parsed = urlsplit(value)
        decoded_path = parsed.path
        for _ in range(3):
            decoded_path = unquote(decoded_path)
        if re.search(r'[\s\x00-\x1f\x7f\\<>"\x27]', decoded_path) or '%' in parsed.netloc:
            return None
        if (parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password
                or parsed.query or parsed.fragment or re.search(r'(?<![0-9])[0-9]{12}(?![0-9])', decoded_path)):
            return None
        return value
    except ValueError:
        return None
