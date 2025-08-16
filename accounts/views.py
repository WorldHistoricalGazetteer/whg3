import json
import secrets

from django.contrib.auth.decorators import login_required
from django.contrib.auth import get_user_model
from django.contrib.auth import views as auth_views
from django.http import HttpResponse, JsonResponse
from django.views.decorators.http import require_POST

User = get_user_model()
from django.conf import settings
from django.contrib import auth, messages
from django.core.signing import Signer, BadSignature
from django.db import transaction
from django.shortcuts import render, redirect, reverse, get_object_or_404

from accounts.forms import UserModelForm
from collection.models import Collection, CollectionGroupUser, CollectionUser  # CollectionGroup,
from datasets.models import Dataset, DatasetUser
import logging

logger = logging.getLogger(__name__)
import traceback
from urllib.parse import urljoin, urlencode
from whgmail.messaging import WHGmail


# def register(request):
#     if request.method == 'POST':
#         form = UserModelForm(request.POST)
#         if form.is_valid():
#             user = form.save(commit=False)
#             user.set_password(request.POST['password1'])
#             user.save()
#
#             signer = Signer()
#             token = signer.sign(user.pk)
#
#             WHGmail(request, {
#                 'template': 'register_confirm',
#                 'subject': 'Confirm your registration at World Historical Gazetteer',
#                 'confirm_url': urljoin(settings.URL_FRONT, reverse('accounts:confirm-email', args=[token])),
#                 'user': user,
#             })
#
#             return redirect('accounts:confirmation-sent')
#         else:
#             return render(request, 'register/register.html', {'form': form})
#     else:
#         form = UserModelForm()
#         return render(request, 'register/register.html', {'form': form})


def login(request):

    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '').strip()
        orcid_auth_url = request.POST.get('orcid_auth_url', '')

        # Check for missing fields
        if not username or not password:
            messages.error(request, "Both Username and Password are required.")
            return render(request, 'accounts/login.html')

        try:
            # Check if user exists
            user = User.objects.get(username=username)
            if user.must_reset_password:
                # User must reset their password; store username in session
                request.session['username_for_reset'] = username
                return redirect('accounts:password_reset')
            else:
                # Attempt to authenticate only if no password reset is required
                user = auth.authenticate(request, username=username, password=password)
                if user is not None:
                    auth.login(request, user)
                    # Redirect to the ORCiD authorisation URL if provided
                    if orcid_auth_url:
                        # Ensure the ORCiD URL is valid
                        if orcid_auth_url.startswith(settings.ORCID_BASE):
                            return redirect(orcid_auth_url)
                        else:
                            messages.error(request, "Invalid ORCiD authorisation URL.")
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
            messages.error(request, "Invalid username.")
            return redirect('accounts:login')  # Or render with an error message
    else:
        # Generate secure random state and nonce tokens
        state = secrets.token_urlsafe(32)
        nonce = secrets.token_urlsafe(32)

        # Store them in the session
        request.session['oidc_state'] = state
        request.session['oidc_nonce'] = nonce

        # Construct ORCiD authorization URL
        orcid_base_authorize_url = f"{settings.ORCID_BASE}/oauth/authorize"
        params = {
            "client_id": settings.ORCID_CLIENT_ID,
            "response_type": "code",
            "scope": "/authenticate email",
            "redirect_uri": request.build_absolute_uri("/orcid-callback/"),
            "state": state,
            "nonce": nonce,
        }
        orcid_auth_url = f"{orcid_base_authorize_url}?{urlencode(params)}"

        return render(request, 'accounts/login.html', context={"orcid_auth_url": orcid_auth_url})


def logout(request):
    if request.method == 'POST':
        request.session.pop('username_for_reset', None)
        auth.logout(request)
        return redirect('home')


def confirm_email(request, token):
    signer = Signer()
    try:
        user_id = signer.unsign(token)
        user = User.objects.get(pk=user_id)
        user.email_confirmed = True
        user.save()

        # Redirect to a success page
        return redirect('accounts:confirmation-success')
    except BadSignature:
        # Handle invalid token
        logger.error(f"Invalid token: {token}")
        traceback.print_exc()
        return render(request, 'register/invalid_token.html', {'error': 'Invalid token.'})
    except User.DoesNotExist:
        # Handle non-existent user
        logger.error(f"User does not exist for token: {token}")
        traceback.print_exc()
        return render(request, 'register/invalid_token.html', {'error': 'User does not exist.'})
    except Exception as e:
        # Handle any other exceptions
        logger.error(f"Exception while confirming email for token {token}: {str(e)}")
        traceback.print_exc()
        return render(request, 'register/invalid_token.html', {'error': str(e)})


def confirmation_sent(request):
    return render(request, 'register/confirmation_sent.html')


def confirmation_success(request):
    return render(request, 'register/confirmation_success.html')


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

    newly_created = request.session.pop("just_created_account", False)
    is_admin = request.user.groups.filter(name='whg_admins').exists()

    context = {
        'is_admin': is_admin,
        'newly_created': newly_created,
        'form': form,
    }
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
        return redirect('homepage')
    else:
        return redirect('profile')