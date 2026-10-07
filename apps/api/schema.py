"""OpenAPI contract shared by all versioned API views."""
from drf_spectacular.extensions import OpenApiAuthenticationExtension
from drf_spectacular.openapi import AutoSchema
from rest_framework import serializers


class ErrorBodySerializer(serializers.Serializer):
    code = serializers.CharField()
    message = serializers.CharField()
    details = serializers.JSONField(allow_null=True)


class ErrorEnvelopeSerializer(serializers.Serializer):
    error = ErrorBodySerializer()


class ApiAutoSchema(AutoSchema):
    def get_override_parameters(self):
        parameters = super().get_override_parameters()
        query = getattr(self.view, 'query_serializer_classes', {}).get(self.method,
            getattr(self.view, 'query_serializer_class', None))
        if query is not None and query().fields and query not in parameters:
            parameters = [*parameters, query]
        return parameters

    def get_operation(self, *args, **kwargs):
        operation = super().get_operation(*args, **kwargs)
        if operation is None:
            return operation
        errors = self.resolve_serializer(ErrorEnvelopeSerializer, 'response').ref
        descriptions = {'400': 'Invalid request or query parameters.',
            '403': 'Session, role or CSRF check failed.', '404': 'Saved resource/version not found.',
            '405': 'Method not allowed.', '406': 'Only JSON responses are supported.',
            '413': 'JSON request body exceeds the supported limit.',
            '415': 'Only JSON request bodies are supported.', '429': 'Request limit exceeded.',
            '500': 'Request could not be completed; internal details are not returned.'}
        for status, description in descriptions.items():
            operation['responses'].setdefault(status, {'description': description,
                'content': {'application/json': {'schema': errors}}})
        if self.method in {'POST', 'PUT', 'PATCH', 'DELETE'}:
            operation.setdefault('parameters', []).append({'name': 'X-CSRFToken', 'in': 'header',
                'required': True, 'schema': {'type': 'string'},
                'description': 'Token from the same-origin session bootstrap, with csrftoken/session cookies.'})
        return operation


class LoginCsrfScheme(OpenApiAuthenticationExtension):
    target_class = 'apps.api.auth.LoginSessionAuthentication'
    name = 'csrfHeader'

    def get_security_definition(self, auto_schema):
        return {'type': 'apiKey', 'in': 'header', 'name': 'X-CSRFToken',
            'description': 'Login requires a matching Django csrftoken cookie, including anonymous login.'}
