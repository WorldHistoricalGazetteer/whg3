from django.http import HttpResponseForbidden
from functools import wraps
from django.contrib.auth.decorators import login_required

def user_is_allowed(user):
    return user.username == 'whgadmin'

def uber_user_required(view_func):
    @wraps(view_func)
    @login_required
    def _wrapped_view(request, *args, **kwargs):
        if user_is_allowed(request.user):
            return view_func(request, *args, **kwargs)
        return HttpResponseForbidden("<h2 style='margin-top:100px;margin-left:100px;'>Sorry, you do not have access to this page :^( </h2>")
    return _wrapped_view