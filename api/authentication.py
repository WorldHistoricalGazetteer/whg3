# api/authentication.py

from django.utils import timezone
from rest_framework.authentication import BaseAuthentication, SessionAuthentication
from rest_framework.exceptions import AuthenticationFailed
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from .models import APIToken, UserAPIProfile

class TokenQueryOrBearerAuthentication(BaseAuthentication):
    """
    Token authentication via URL parameter (?token=...) or Bearer header
    Integrates with existing APIToken and UserAPIProfile models
    """

    def authenticate(self, request):
        """
        Authenticate using the same logic as AuthenticatedViewMixin
        """
        key = None

        # 1. Check Authorization header
        auth = request.headers.get("Authorization", "")
        if auth.lower().startswith("bearer "):
            key = auth.split(" ", 1)[1].strip()

        # 2. Check token from URL query param
        if not key:
            key = request.GET.get("token")

        # 3. Fall back to session/CSRF auth
        if not key:
            return None

        try:
            token = APIToken.objects.select_related("user").get(key=key)
        except APIToken.DoesNotExist:
            raise AuthenticationFailed("Invalid API token")

        user = token.user

        # Ensure UserAPIProfile exists
        profile, _ = UserAPIProfile.objects.get_or_create(user=user)

        # Check daily limit before increment
        if profile.daily_limit and profile.daily_count >= profile.daily_limit:
            raise AuthenticationFailed(
                f"Daily API limit ({profile.daily_limit} calls) exceeded"
            )

        # Increment usage after validation
        profile.increment_usage()

        # Update token last used (lightweight throttling: only if >60s since last)
        now = timezone.now()
        if not token.last_used or (now - token.last_used).total_seconds() > 60:
            token.last_used = now
            token.save(update_fields=["last_used"])

        # Return user and token key (not the full object)
        return (user, key)

    def authenticate_header(self, request):
        """
        Indicate that this endpoint uses Bearer auth for 401 challenges.
        """
        return 'Bearer realm="api"'


class AuthenticatedAPIView(APIView):
    """
    Base API view with token/session authentication
    """
    authentication_classes = [
        TokenQueryOrBearerAuthentication,
        SessionAuthentication,
    ]
    permission_classes = [IsAuthenticated]
