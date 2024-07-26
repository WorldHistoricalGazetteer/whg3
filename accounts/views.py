from django.contrib.auth.decorators import login_required
from django.contrib.auth import get_user_model
from django.contrib.auth import views as auth_views

User = get_user_model()
from django.conf import settings
from django.contrib import auth, messages
from django.core.mail import EmailMultiAlternatives
from django.core.signing import Signer, BadSignature
from django.db import transaction
from django.shortcuts import render, redirect, reverse, get_object_or_404

from accounts.forms import UserModelForm
from collection.models import Collection, CollectionGroupUser, CollectionUser  # CollectionGroup,
from datasets.models import Dataset, DatasetUser
import logging
logger = logging.getLogger(__name__)
import traceback
from urllib.parse import urljoin
from whgmail.messaging import WHGmail

def register(request):
    if request.method == 'POST':
        form = UserModelForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            user.set_password(request.POST['password1'])
            user.save()

            signer = Signer()
            token = signer.sign(user.pk)
            
            context = {
                'subject': 'Confirm your registration at World Historical Gazetteer',
                'confirm_url': urljoin(settings.URL_FRONT, reverse('accounts:confirm-email', args=[token])),
                'user': user,
            }
              
            WHGmail(request, {
                'template': 'register_confirm'
            })
            
            return redirect('accounts:confirmation-sent')
        else:
            return render(request, 'register/register.html', {'form': form})
    else:
        form = UserModelForm()
        return render(request, 'register/register.html', {'form': form})


def login(request):
  if request.method == 'POST':
    username = request.POST['username']
    password = request.POST['password']

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
    return render(request, 'accounts/login.html')


def logout(request):
  if request.method == 'POST':
    request.session.pop('username_for_reset', None)
    auth.logout(request)
    return redirect('home')

def confirm_email(request, token):
  print('token in confirm_email()', token)
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
  print('add_to_group', cg, member)
  cguser = CollectionGroupUser.objects.create(
    role='member',
    collectiongroup=cg,
    user=member
  )
  cguser.save()


@login_required
def profile_edit(request):
    if request.method == 'POST':
        print('request.FILES', request.FILES)
        form = UserModelForm(request.POST, request.FILES, instance=request.user)
        if form.is_valid():
            form.save()
            return redirect('profile-edit')
        else:
            print("Form Errors:", form.errors)
            print("Cleaned Data:", form.cleaned_data)
    else:
        form = UserModelForm(instance=request.user)

    is_admin = request.user.groups.filter(name='whg_admins').exists()
    context = {'is_admin': is_admin, 'form': form}
    return render(request, 'accounts/profile.html', context=context)

@login_required
@transaction.atomic
def update_profile(request):
  print('update_profile() request.method', request.method)
  context = {}
  if request.method == 'POST':
    print('update_profile() POST', request.POST)
    user_form = UserModelForm(request.POST, instance=request.user)
    # profile_form = ProfileModelForm(request.POST, instance=request.user.profile)
    if user_form.is_valid():
      # if user_form.is_valid() and profile_form.is_valid():
      user_form.save()
      # profile_form.save()
      messages.success(request, ('Your profile was successfully updated!'))
      return redirect('accounts:profile')
    else:
      print('error, user_form', user_form.cleaned_data)
      # print('error, profile_form',profile_form.cleaned_data)
      messages.error(request, ('Please correct the error below.'))
  else:
    user_form = UserModelForm(instance=request.user)
    # profile_form = ProfileModelForm(instance=request.user.profile)
    id_ = request.user.id
    u = get_object_or_404(User, id=id_)
    ds_owned = [[ds.id, ds.title, 'owner'] for ds in Dataset.objects.filter(owner=u).order_by('title')]
    ds_collabs = [[dc.dataset_id.id, dc.dataset_id.title, dc.role] for dc in DatasetUser.objects.filter(user_id_id=id_)]
    # groups = u.groups.values_list('name', flat=True)
    groups_owned = u.groups.all()
    group_leader = 'group_leaders' in u.groups.values_list('name', flat=True)  # True or False

    context['ds_owned'] = ds_owned
    context['ds_collabs'] = ds_collabs
    # TODO: context object for collections - place or dataset, owned or collaborated on
    context['coll_owned'] = Collection.objects.filter(owner=u, collection_class='place')
    context['coll_collab'] = CollectionUser.objects.filter(user=u)
    # context['collections'] = Collection.objects.filter(owner=u)
    context['groups_owned'] = groups_owned
    context['mygroups'] = [g.collectiongroup for g in CollectionGroupUser.objects.filter(user=u)]
    context['group_leader'] = group_leader
    context['comments'] = 'get comments associated with projects I own'

    return render(request, 'accounts/profile.html', {
      'user_form': user_form,
      # 'profile_form': profile_form,
      'context': context
    })
