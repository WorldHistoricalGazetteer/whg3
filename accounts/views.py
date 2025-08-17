import secrets

from django.contrib.auth import get_user_model
from django.contrib.auth import views as auth_views
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_POST

User = get_user_model()
from django.conf import settings
from django.contrib import auth, messages
from django.core.signing import Signer, BadSignature
from django.shortcuts import render, redirect, reverse

from accounts.forms import UserModelForm
from collection.models import CollectionGroupUser  # CollectionGroup,
import logging

logger = logging.getLogger('authentication')
import traceback
from urllib.parse import urlencode


def build_orcid_authorize_url(request):
    state = secrets.token_urlsafe(24)
    nonce = secrets.token_urlsafe(24)

    request.session["oidc_state"] = state
    request.session["oidc_nonce"] = nonce

    params = {
        "client_id": settings.ORCID_CLIENT_ID,
        "response_type": "code",
        "scope": "/read-limited",
        "redirect_uri": request.build_absolute_uri(reverse("orcid-callback")),
        "state": state,
        "nonce": nonce,
    }
    return f"{settings.ORCID_BASE}/oauth/authorize?{urlencode(params)}"


def login(request):
    if request.method == 'POST':
        # Legacy WHG Login -> ORCiD
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '').strip()
        orcid_auth_url = request.POST.get('orcid_auth_url', '')

        # Check for missing fields
        if not username or not password:
            messages.error(request, "Both Username and Password are required.")
            return redirect("accounts:login")

        try:
            # Check if user exists
            user = User.objects.get(username=username)
            if user.must_reset_password:
                # User must reset their password; store username in session
                request.session['username_for_reset'] = username
                return redirect('accounts:password_reset')
            else:
                # Attempt to authenticate using legacy backend only if no password reset is required
                user = auth.authenticate(request, username=username, password=password, backend='django.contrib.auth.backends.ModelBackend')
                if user is not None:
                    auth.login(request, user)
                    # Redirect to the ORCiD authorisation URL if provided
                    if orcid_auth_url:
                        # Ensure the ORCiD URL is valid
                        if orcid_auth_url.startswith(settings.ORCID_BASE):
                            return redirect(orcid_auth_url)
                        else:
                            logger.error("Invalid ORCiD authorisation URL.")
                            return redirect('accounts:login')
                    else:
                        # No ORCiD URL provided, redirect to home
                        return redirect('home')
                else:
                    # Authentication fails
                    messages.error(request, "Invalid password.")
                    return redirect('accounts:login')
        except User.DoesNotExist:
            # User not found
            messages.error(request, "<h4><i class='fas fa-triangle-exclamation'></i> Invalid WHG username.</h4><p>Please correct this and try again.</p>")
            return redirect('accounts:login')
    else:
        # Prevent login page view if user is already authenticated
        if request.user.is_authenticated:
            return redirect('home')

        # GET request, render the login page with ORCiD auth URL
        return render(
            request,
            'accounts/login.html',
            context={"orcid_auth_url": build_orcid_authorize_url(request)}
        )


def logout(request):
    if request.method == 'POST':
        request.session.pop('username_for_reset', None)
        auth.logout(request)
        return redirect('home')


class CustomPasswordResetView(auth_views.PasswordResetView):
    template_name = 'register/password_reset_form.html'

    def get_success_url(self):
        return reverse('accounts:password_reset_done')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        username = self.request.session.get('username_for_reset')
        context['user'] = username
        return context


class CustomPasswordResetDoneView(auth_views.PasswordResetDoneView):
    template_name = 'register/password_reset_done.html'


class CustomPasswordResetConfirmView(auth_views.PasswordResetConfirmView):
    template_name = 'register/password_reset_confirm.html'

    def form_valid(self, form):
        # This method is called when the form is successfully submitted and valid
        response = super().form_valid(form)
        # Here, `form.user` is accessible because it's typically set in `PasswordResetConfirmView`
        user = form.user
        if hasattr(user, 'must_reset_password'):
            user.must_reset_password = False
            user.save()
        return response

    def get_success_url(self):
        return reverse('accounts:password_reset_complete')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Assume `self.user` is the user object, depending on your URL config
        context['user'] = self.user
        return context


class CustomPasswordResetCompleteView(auth_views.PasswordResetCompleteView):
    template_name = 'register/password_reset_complete.html'

    def get(self, request, *args, **kwargs):
        # clear the username from the session, set for v3 password reset
        request.session.pop('username_for_reset', None)
        # Call the original get method to continue normal processing
        return super().get(request, *args, **kwargs)


class CustomPasswordChangeView(auth_views.PasswordChangeView):
    template_name = 'register/password_change_form.html'

    def get_success_url(self):
        return reverse('accounts:password_change_done')


class CustomPasswordChangeDoneView(auth_views.PasswordChangeDoneView):
    template_name = 'register/password_change_done.html'

    def get(self, request, *args, **kwargs):
        # clear the username from the session, set for v3 password reset
        request.session.pop('username_for_reset', None)
        # Call the original get method to continue normal processing
        return super().get(request, *args, **kwargs)


def add_to_group(cg, member):
    cguser = CollectionGroupUser.objects.create(
        role='member',
        collectiongroup=cg,
        user=member
    )
    cguser.save()


@login_required
def profile_edit(request):
    form = UserModelForm(instance=request.user)

    context = {
        'is_admin': request.user.groups.filter(name='whg_admins').exists(),
        'needs_news_check': request.session.pop("_needs_news_check", False),
        'form': form,
        'ORCID_BASE': settings.ORCID_BASE,
    }

    logger.debug(context)

    return render(request, 'accounts/profile.html', context=context)


@login_required
def profile_download(request):
    user = request.user
    data = {
        'username': user.username,
        'email': user.email,
        'given_name': getattr(user, 'given_name', ''),
        'surname': getattr(user, 'surname', ''),
        'orcid': getattr(user, 'orcid', ''),
        'affiliation': getattr(user, 'affiliation', ''),
        'web_page': getattr(user, 'web_page', ''),
        'news_permitted': getattr(user, 'news_permitted', False),
    }
    response = JsonResponse(data)
    response['Content-Disposition'] = 'attachment; filename="user_data.json"'
    return response


@login_required
@require_POST
def profile_news_toggle(request):
    user = request.user
    news_permitted = request.POST.get('news_permitted') == 'on'
    user.news_permitted = news_permitted
    user.save()
    return JsonResponse({'status': 'success', 'news_permitted': news_permitted})


@login_required
def profile_delete(request):
    if request.method == 'POST':
        user = request.user
        user.delete()
        messages.success(request, "Your account has been deleted.")
        return redirect('home')
    else:
        return redirect('profile-edit')
