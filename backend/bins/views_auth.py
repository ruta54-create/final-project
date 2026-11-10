from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.middleware.csrf import get_token
from rest_framework import permissions
from rest_framework.authentication import SessionAuthentication
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response


def user_payload(user):
    return {"authenticated": True, "id": user.id, "username": user.username, "is_staff": user.is_staff,
            "name": user.get_full_name() or user.username}


@api_view(["GET"])
@permission_classes([permissions.AllowAny])
def csrf(request):
    """Sets the csrftoken cookie that the React app sends back in X-CSRFToken."""
    get_token(request._request)
    return Response({"ok": True})


@api_view(["POST"])
@permission_classes([permissions.AllowAny])
def login_view(request):
    SessionAuthentication().enforce_csrf(request)
    user = authenticate(request, username=request.data.get("username"), password=request.data.get("password"))
    if user is None:
        return Response({"detail": "Wrong username or password.", "code": "bad_credentials"}, status=400)
    login(request, user)
    return Response(user_payload(user))


@api_view(["POST"])
def logout_view(request):
    logout(request)
    return Response({"ok": True})


@api_view(["GET"])
@permission_classes([permissions.AllowAny])
def me(request):
    # 200 + authenticated=false (not 401): "nobody logged in" is a normal answer,
    # so the browser console does not show a red error on the login page
    if not request.user.is_authenticated:
        return Response({"authenticated": False})
    return Response(user_payload(request.user))


@api_view(["POST"])
def change_password(request):
    user = request.user
    if not user.check_password(request.data.get("old_password", "")):
        return Response({"detail": "Current password is wrong.", "code": "wrong_password"}, status=400)
    new = request.data.get("new_password", "")
    if len(new) < 8:
        return Response({"detail": "New password must have at least 8 characters.", "code": "too_short"}, status=400)
    user.set_password(new)
    user.save()
    update_session_auth_hash(request, user)
    return Response({"ok": True})
