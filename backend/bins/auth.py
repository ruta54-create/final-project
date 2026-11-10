"""Devices (ESP32) authenticate with their bin's API key in the 'X-API-KEY' header."""

from django.contrib.auth.models import AnonymousUser
from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed
from rest_framework.permissions import BasePermission

from .models import Bin


class DeviceKeyAuthentication(BaseAuthentication):
    def authenticate(self, request):
        key = request.headers.get("X-API-KEY")
        if not key:
            return None
        try:
            bin = Bin.objects.get(api_key=key)
        except Bin.DoesNotExist:
            raise AuthenticationFailed("Invalid device API key")
        return AnonymousUser(), bin

    def authenticate_header(self, request):
        return "X-API-KEY"


class IsDevice(BasePermission):
    message = "Send the bin API key in the X-API-KEY header."

    def has_permission(self, request, view):
        return isinstance(request.auth, Bin)
