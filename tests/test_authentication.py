from django.test import TestCase, Client
from django.contrib import auth
from django.contrib.auth import get_user_model
from django.core import mail
from django.urls import reverse
from django.utils.http import urlsafe_base64_encode
from django.utils.encoding import force_bytes
import re

User = get_user_model()


# ./manage.py test tests.test_authentication.AuthenticationActionsTestCase.test_registration
# ./manage.py test tests.test_authentication.UserPasswordResetTest

class UserPasswordResetTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='testuser', email='test@example.com', password='old_password')

    def test_password_reset(self):
      # Access and submit the password reset form
      self.client.get(reverse('accounts:password_reset'))
      self.client.post(reverse('accounts:password_reset'), {'email': 'test@example.com'})

      # Extract token and uidb64 from the email
      email_body = mail.outbox[2].body
      uidb64, token = re.search(r'/reset/(\w+)/(\w+-\w+)/', email_body).groups()

      # Access the password reset confirmation page
      response = self.client.get(reverse('accounts:password_reset_confirm', kwargs={'uidb64': uidb64, 'token': token}),
                                 follow=True)

      # Extract CSRF token
      csrf_token = re.search(r'csrfmiddlewaretoken" value="([^"]+)"', response.content.decode()).group(1)

      # Submit the new password form
      new_password = '84Hfdh@LFNP8iLe'
      response = self.client.post(
        reverse('accounts:password_reset_confirm', kwargs={'uidb64': uidb64, 'token': token}),
        {
          'csrfmiddlewaretoken': csrf_token,
          'new_password1': new_password,
          'new_password2': new_password
        },
        follow=True
      )

      # Check for form errors
      if 'form' in response.context:
        form_errors = response.context['form'].errors
        if form_errors:
          print("Form errors:", form_errors)
          self.fail(f"Password reset form submission failed with errors: {form_errors}")

      # Refresh user instance and check the password
      self.user.refresh_from_db()
      self.assertTrue(self.user.check_password(new_password), "Password update failed.")


class AuthenticationActionsTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        self.user_data = {
            'username': 'testuser',
            'password': 'testpassword123',
            'email': 'testuser@example.com',
            'affiliation': 'test affiliation',
            'name': 'Test User',
            'role': 'normal',
        }
        self.user = User.objects.create_user(**self.user_data)

    def test_registration(self):
      # Define the registration data
      registration_data = {
        'username': 'newuser',
        'password1': 'newpassword123',
        'password2': 'newpassword123',
        'email': 'newuser@example.com',
        'affiliation': 'new affiliation',
        'name': 'New User',
        'role': 'normal',
      }

      # Send a POST request to the registration view
      response = self.client.post(reverse('accounts:register'), registration_data)

      # Check that the response is a redirect
      self.assertEqual(response.status_code, 302)

      # Retrieve the new user
      new_user = User.objects.get(username=registration_data['username'])

      # Check the new user's attributes
      self.assertEqual(new_user.email, registration_data['email'])
      self.assertEqual(new_user.affiliation, registration_data['affiliation'])
      self.assertEqual(new_user.name, registration_data['name'])
      self.assertEqual(new_user.role, registration_data['role'])

    def test_login(self):
      # Define the login data
      login_data = {
        'username': self.user_data['username'],
        'password': self.user_data['password'],
      }

      # Send a POST request to the login view
      response = self.client.post(reverse('accounts:login'), login_data)

      # Check that the response is a redirect (login successful)
      self.assertEqual(response.status_code, 302)

      # Check that the user is authenticated
      user = auth.get_user(self.client)
      self.assertTrue(user.is_authenticated)

    def test_logout(self):
      # Log in the user
      self.client.login(username=self.user_data['username'], password=self.user_data['password'])

      # Check that the user is authenticated
      user = auth.get_user(self.client)
      self.assertTrue(user.is_authenticated)

      # Send a POST request to the logout view
      response = self.client.post(reverse('accounts:logout'))

      # Check that the response is a redirect (logout successful)
      self.assertEqual(response.status_code, 302)

      # Check that the user is not authenticated
      user = auth.get_user(self.client)
      self.assertFalse(user.is_authenticated)


    # test fails after 37 adjustments but password reset works perfectly in the browser
    # def test_password_reset(self):
    #   # Request the password reset page
    #   response = self.client.get(reverse('accounts:password_reset'))
    #   self.assertEqual(response.status_code, 200)
    #
    #   # Submit the password reset form
    #   response = self.client.post(reverse('accounts:password_reset'), {'email': self.user_data['email']})
    #   self.assertEqual(response.status_code, 302)
    #
    #   # Check that an email was sent
    #   self.assertEqual(len(mail.outbox), 3)
    #
    #   # Extract the token from the email
    #   email_body = mail.outbox[2].body
    #   print('email_body', email_body)
    #   url_match = re.search(
    #     r'/accounts/reset/(?P<uidb64>[0-9A-Za-z_\-]+)/(?P<token>[0-9A-Za-z]{1,13}-[0-9A-Za-z]{1,32})/', email_body,
    #     re.DOTALL)
    #   if url_match:
    #     uidb64 = url_match.group('uidb64')
    #     token = url_match.group('token')
    #   else:
    #     self.fail("Token not found in email body")
    #
    #   response = self.client.get(
    #     reverse('accounts:password_reset_confirm', kwargs={'uidb64': uidb64, 'token': token}))
    #   self.assertEqual(response.status_code, 302)
    #
    #
    #   # Submit the new password
    #   new_password = 'newpassword123'
    #   print('token @ 2', token)
    #   response = self.client.post(reverse('accounts:confirm-email', kwargs={'token': token}), {
    #     'new_password1': new_password,
    #     'new_password2': new_password,
    #   })
    #   print('Redirect location:', response['Location'])
    #   self.assertEqual(response.status_code, 302)
    #
    #   # Check that the password was changed
    #   self.user.refresh_from_db()
    #   self.assertTrue(self.user.check_password(new_password))

    def test_password_change(self):
      pass
        # TODO: Implement password change test pass