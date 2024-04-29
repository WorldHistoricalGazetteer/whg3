from django.contrib.auth.tokens import default_token_generator
from django.core import mail
from django.urls import reverse
from django.test import TestCase
from django.contrib.messages import get_messages
from django.contrib.auth import get_user_model
from django.utils.http import urlsafe_base64_encode
from django.utils.encoding import force_bytes
User = get_user_model()
from unittest.mock import patch
import re

from django.urls import reverse
from django.test import TestCase
from django.contrib.auth import get_user_model
from unittest.mock import patch
from django.contrib.auth.tokens import default_token_generator
from django.utils.http import urlsafe_base64_encode
from django.utils.encoding import force_bytes

from django.urls import reverse
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import default_token_generator
from django.utils.http import urlsafe_base64_encode
from django.utils.encoding import force_bytes
from unittest.mock import patch


# ./manage.py test tests.test_migration_pwd_change
class MigrationPwdTest(TestCase):
  def setUp(self):
    # Create a user with must_change_password set to True
    User = get_user_model()
    self.user = User.objects.create_user(
      username='testuser',
      email='test@example.com',
      password='TeStPaSsWoRd1234!',
      name='Test User',
      must_reset_password=True
    )
    # self.user.must_change_password = True
    self.user.save()

  def test_login_redirects_when_must_change_password(self):
    from django.contrib.auth import get_user_model
    User = get_user_model()
    db_user = User.objects.get(username='testuser')
    print("Database user must_change_password:", db_user.must_reset_password)

    # Simulate logging in
    response = self.client.post(reverse('accounts:login'),
                                {'username': 'testuser', 'password': 'TeStPaSsWoRd1234!'}, follow=True)
    print('response.redirect_chain', response.redirect_chain)

    # Check if the response redirected to the correct URL
    self.assertRedirects(response, reverse('accounts:password_reset'))

    # Check for the presence of the 'user' in the context if necessary
    response = self.client.get(reverse('accounts:password_reset'))
    self.assertIn('Our recent update to Version 3', response.content.decode())

  def test_normal_login(self):
    # Set must_change_password to False for normal login test
    self.user.must_reset_password = False
    self.user.save()

    # Fetch the user from the database
    User = get_user_model()
    db_user = User.objects.get(username='testuser')
    print("Database user must_change_password:", db_user.must_reset_password)

    # Simulate normal login
    response = self.client.post(reverse('accounts:login'),
                                {'username': 'testuser', 'password': 'TeStPaSsWoRd1234!'}, follow=True)
    self.assertRedirects(response, reverse('home'))

    # Optionally verify the user is authenticated
    self.assertTrue('_auth_user_id' in self.client.session)
