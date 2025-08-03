from django.conf import settings
from django.http import HttpResponseForbidden

BLOCKED_USER_AGENT_SUBSTRINGS = getattr(settings, 'BLOCKED_USER_AGENT_SUBSTRINGS', [])


class BlockUserAgentsMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Must be after UserAgentMiddleware
        if hasattr(request, 'user_agent'):
            agent_string = request.user_agent.string or ""
            if any(sub in agent_string for sub in BLOCKED_USER_AGENT_SUBSTRINGS):
                return HttpResponseForbidden("Forbidden: Bot access denied.")
        return self.get_response(request)
