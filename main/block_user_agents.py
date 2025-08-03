from django.conf import settings
from django.http import HttpResponseForbidden

BLOCKED_USER_AGENT_SUBSTRINGS = getattr(settings, 'BLOCKED_USER_AGENT_SUBSTRINGS', [])


class BlockUserAgentsMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user_agent = request.META.get('HTTP_USER_AGENT', '')
        if any(blocked in user_agent for blocked in BLOCKED_USER_AGENT_SUBSTRINGS):
            return HttpResponseForbidden("Forbidden: Bot access denied.")
        return self.get_response(request)
