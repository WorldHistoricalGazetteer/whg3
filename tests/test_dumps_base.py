# tests/base.py
from django.test import TestCase

class BaseCommandTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        # Set up common test data here
      pass

    def call_command(self, command_name, **options):
        # Utility method to call a command
        pass
    def tearDown(self):
        # Clean up any files or other resources created during tests
        pass