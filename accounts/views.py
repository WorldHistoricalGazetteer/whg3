from django.contrib.auth.decorators import login_required
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.contrib.auth.views import PasswordResetView, PasswordResetConfirmView
from django.core.validators import validate_email
from django.core.exceptions import ValidationError

User = get_user_model()
from django.conf import settings
from django.contrib import auth, messages
from django.core.mail import EmailMultiAlternatives
from django.core.signing import Signer
from django.core.mail import send_mail
from django.db import transaction
from django import forms
from django.shortcuts import render, redirect, reverse, get_object_or_404

from accounts.forms import UserModelForm
from collection.models import Collection, CollectionGroup, CollectionGroupUser, CollectionUser
from datasets.models import Dataset, DatasetUser


def register(request):
  if request.method == 'POST':
    if request.POST['password1'] == request.POST['password2']:
      try:
        User.objects.get(username=request.POST['username'])
        return render(request, 'register/register.html',
                      {'error': 'That username is already taken. Try another, please.'})
      except User.DoesNotExist:
        print('request.POST', request.POST)
        user = User.objects.create_user(
          # request.POST['email'],
          request.POST['username'],
          password=request.POST['password1'],
          email=request.POST['email'],
          affiliation=request.POST['affiliation'],
          name=request.POST['name'],
          role='normal',
        )
        user.email_confirmed = False
        user.save()

        signer = Signer()
        token = signer.sign(user.pk)

        confirm_url = request.build_absolute_uri(reverse('accounts:confirm-email', args=[token]))

        subject = 'Confirm your registration at World Historical Gazetteer'
        text_content = f'Please click the link to confirm your WHG registration:\n\n {confirm_url}'
        html_content = f'Please click the link to <a href="{confirm_url}">confirm your WHG registration</a>.'

        email = EmailMultiAlternatives(subject, text_content, settings.DEFAULT_FROM_EMAIL, [user.email])
        email.attach_alternative(html_content, "text/html")
        email.send(fail_silently=False)

        # send_mail(
        #   'Confirm your registration at World Historical Gazetteer',
        #   f'Please click the link to confirm your WHG registration: <br/>{confirm_url}',
        #   settings.DEFAULT_FROM_EMAIL,
        #   [user.email],
        #   fail_silently=False,
        # )

        return redirect('accounts:confirmation-sent')

    else:
      return render(request, 'register/register.html', {'error': 'Sorry, password mismatch!'})

  else:
    return render(request, 'register/register.html')


def confirm_email(request, token):
  signer = Signer()
  try:
    user_id = signer.unsign(token)
    user = User.objects.get(pk=user_id)
    user.email_confirmed = True
    user.save()

    # Redirect to a success page
    return redirect('accounts:confirmation-success')
  except:
    # Handle invalid or expired token
    return render(request, 'accounts:invalid_token.html')


def confirmation_sent(request):
  return render(request, 'register/confirmation_sent.html')


def confirmation_success(request):
  return render(request, 'register/confirmation_success.html')

from django.contrib.auth import views as auth_views
from django.urls import reverse

class CustomPasswordResetView(auth_views.PasswordResetView):
    template_name = 'register/password_reset_form.html'
    def get_success_url(self):
        return reverse('accounts:password_reset_done')

class CustomPasswordResetDoneView(auth_views.PasswordResetDoneView):
    template_name = 'register/password_reset_done.html'

class CustomPasswordResetConfirmView(auth_views.PasswordResetConfirmView):
    template_name = 'register/password_reset_confirm.html'
    def get_success_url(self):
        return reverse('accounts:password_reset_complete')

class CustomPasswordResetCompleteView(auth_views.PasswordResetCompleteView):
    template_name = 'register/password_reset_complete.html'
#
# class CustomPasswordResetView(PasswordResetView):
#     def get_success_url(self):
#         return reverse('accounts:password_reset_done')
#
# class CustomPasswordResetConfirmView(PasswordResetConfirmView):
#     def get_success_url(self):
#         return reverse('accounts:password_reset_complete')

def login(request):
  if request.method == 'POST':
    user = auth.authenticate(username=request.POST['username'], password=request.POST['password'])
    if user is not None:
      auth.login(request, user, backend='django.contrib.auth.backends.ModelBackend')
      return redirect('home')
    else:
      messages.error(request, "Sorry, that username is not recognized.")
      return redirect('accounts:login')
  else:
    return render(request, 'accounts/login.html')


# def login(request):
#   if request.method == 'POST':
#     user = auth.authenticate(username=request.POST['username'], password=request.POST['password'])
#     # user = auth.authenticate(email=request.POST['email'],password=request.POST['password'])
#     if user is not None:
#       auth.login(request, user, backend='django.contrib.auth.backends.ModelBackend')
#       return redirect('home')
#     else:
#       raise forms.ValidationError("Sorry, that login was invalid. Please try again.")
#   else:
#     return render(request, 'accounts/login.html')


def logout(request):
  if request.method == 'POST':
    auth.logout(request)
    return redirect('home')


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
    user = request.user
    user.name = request.POST.get('name')
    user.affiliation = request.POST.get('affiliation')
    user.save()
    return redirect('profile-edit')

  is_admin = request.user.groups.filter(name='whg_admins').exists()
  context = {'is_admin': is_admin}
  return render(request, 'accounts/profile.html', context=context)


@login_required
@transaction.atomic
def update_profile(request):
  print('update_profile() request.method', request.method)
  context = {}
  if request.method == 'POST':
    user_form = UserModelForm(request.POST, instance=request.user)
    # profile_form = ProfileModelForm(request.POST, instance=request.user.profile)
    if user_form.is_valid():
      # if user_form.is_valid() and profile_form.is_valid():
      user_form.save()
      # profile_form.save()
      messages.success(request, ('Your profile was successfully updated!'))
      return redirect('accounts:profile')
    else:
      print()
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

# class ValidationErrorList(Exception):
#   def __init__(self, errors):
#     self.errors = errors

# def validate_usersfile(tempfn, cg):
#   User = get_user_model()
#   result = {"status": 'validated', "errors": [], "create_add": [], 'just_add': [], 'already': []}
#   import csv
#   email_set = set()  # Set to store emails for checking duplicates
#   with open(tempfn, newline='') as csvfile:
#     reader = csv.reader(csvfile, delimiter=',', skipinitialspace=True)
#     for i, row in enumerate(reader):
#       if len(row) < 2:
#         result['errors'].append('row #' + str(i + 1) + ' does not have enough columns')
#       else:
#         email = row[0]
#         try:
#           validate_email(email)  # Use Django's validate_email function
#         except ValidationError:
#           result['errors'].append('invalid email on row #' + str(i + 1) + ': ' + email)
#         if email in email_set:  # Check if email is already in the set
#           result['errors'].append('Duplicate email on row #' + str(i + 1) + ': ' + email)
#         else:
#           email_set.add(email)  # Add email to the set
#         if row[1] == '':
#           result['errors'].append('no name for row #' + str(i + 1))
#     if len(result['errors']) > 0:
#       result['status'] = 'failed'
#       return result
#     else:
#       user = User.objects.filter(email=email)
#       members = [u.user_id for u in cg.members.all()]
#       if user.exists():
#         in_group = user[0].id in members
#         if in_group:
#           result['already'].append(row)
#         else:
#           result['just_add'].append(row)
#       else:
#         result['create_add'].append(row)
#   return result
#
#
# # add users to a CollectionGroup, or create new users and add them
# @login_required
# def addusers(request):
#   if request.method == 'POST':
#     action = request.POST['action']
#     cgid = request.POST['cgid']
#     cg = get_object_or_404(CollectionGroup, id=cgid)
#     created_count = 0
#     only_joined_count = 0
#     new_members = []
#
#     if action == 'upload':
#       file = request.FILES['file']
#       mimetype = file.content_type
#       tempf, tempfn = tempfile.mkstemp()
#
#       try:
#         for chunk in file.chunks():
#           os.write(tempf, chunk)
#       except IOError:
#         return JsonResponse({"status": "failed", "errors": "Problem opening/writing input file"}, safe=False)
#       finally:
#         os.close(tempf)
#
#       try:
#         result = validate_usersfile(tempfn, cg)
#       except Exception as e:
#         return JsonResponse({"status": "failed", "errors": str(e)}, safe=False)
#
#     elif action == 'addem':
#       try:
#         create_add = json.loads(request.POST['create_add']) or None
#         just_add = json.loads(request.POST['just_add']) or None
#
#         with transaction.atomic():
#           if create_add:
#             for u in create_add:
#               email, name = u
#               try:
#                 validate_email(email)
#               except ValidationError:
#                 result = {'status': 'failed', 'errors': 'Invalid email address: ' + email}
#                 return JsonResponse(result, safe=False)
#               if email not in existing_users:
#                 temp_password = User.objects.make_random_password()
#                 new_user = User.objects.create(email=email,
#                                                name=name, password=temp_password, must_change_password=True)
#                 add_to_group(cg, new_user)
#
#                 # TODO: wire new_emailer from v2
#                 print('emailing new user', email, temp_password)
#                 # new_emailer(email, temp_password)
#
#                 created_count += 1
#                 new_members.append([email, name, new_user.id])
#
#           if just_add:
#             for u in just_add:
#               email, name = u
#               validate_email(email)
#               user = User.objects.get(email=email)
#               add_to_group(cg, user)
#               only_joined_count += 1
#               new_members.append([email, name, user.id])
#
#         total = created_count + only_joined_count
#         result = {
#           'status': 'added', 'errors': [],
#           'newmembers': new_members,
#           'msg': f'<p>Created {created_count} new WHG users</p><p>Added <b>{total}</b> new group members</p>'
#         }
#
#       except ValidationError as e:
#         result = {'status': 'failed', 'errors': str(e), 'msg': 'Invalid email address!'}
#
#     return JsonResponse(result, safe=False)
#
