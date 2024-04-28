from django.test import TestCase, Client
from django.contrib import auth
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.core import mail

User = get_user_model()

# ./manage.py test tests.test_authentication.AuthenticationActionsTestCase.test_registration
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

    def test_password_reset(self):
      pass
        # TODO: Implement password reset test

    def test_password_change(self):
      pass
        # TODO: Implement password change test pass