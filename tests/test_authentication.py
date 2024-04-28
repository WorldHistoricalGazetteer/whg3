from django.test import TestCase
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.urls import reverse
from django.test import Client
from django.core import mail

class AuthenticationActionsTestCase(TestCase):
  def setUp(self):
    pass