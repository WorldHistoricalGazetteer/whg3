# ./manage.py test --settings=tests.settings tests.test_emailing.ContactFormTestCase
# ./manage.py test --settings=tests.settings tests.test_emailing.EmailerTestCase
# ./manage.py test --settings=tests.settings tests.test_emailing.DatasetSignalTestCase

from django.test import TestCase
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core import mail
from django.urls import reverse
from datasets.models import Dataset
from places.models import Place
from unittest.mock import patch
import sys

User = get_user_model()
from datasets.tasks import align_idx
from datasets.tasks import align_wdlocal

# Set up any necessary preconditions for your task here.
# setUp: dataset, places, user, etc.
""" {'ds': 22,
    'dslabel': 'diamonds10',
    'owner': 2,
    'user': 2,
    'bounds': {'type': ['userarea'], 'id': ['0']},
    'aug_geom': 'on',
    'scope': 'all',
    'lang': 'en',
    'test': 'on',
    'collection_id': ''}
"""

class TestAlignIdx(TestCase):
    def setUp(self):
        # Create a User instance
        self.user = User.objects.create_user(username='testuser', email='testuser@example.com', password='testpass')

        # Create a Dataset instance
        self.dataset = Dataset.objects.create(label='diamonds10',
                                              title='Diamonds 10',
                                              description='Test description',
                                              owner=self.user)

        # Create several Place instances associated with the Dataset
        self.place1 = Place.objects.create(dataset=self.dataset.label, src_id='p1', title='Place 1')
        self.place2 = Place.objects.create(dataset=self.dataset.label, src_id='p2', title='Place 2')
        # Add more Place instances as needed...

        # Set up the kwargs for the align_idx task
        self.kwargs = {
            'ds': self.dataset.id,
            'dslabel': self.dataset.label,
            'owner': self.user.id,
            'user': self.user.id,
            'bounds': {'type': ['userarea'], 'id': ['0']},
            'aug_geom': 'on',
            'scope': 'all',
            'lang': 'en',
            'test': 'on',
            'collection_id': ''
        }

    @patch('utils.emailing.new_emailer')
    def test_align_idx_sends_email(self, mock_new_emailer):
        # Run the task synchronously within your test case.
        align_idx.apply(kwargs=self.kwargs)

        # Check that new_emailer was called with the correct arguments.
        mock_new_emailer.assert_called_once_with(
            email_type='align_idx',
            subject='WHG alignment task complete',
            from_email='your_from_email@example.com',
            to_email=[self.user.email],
            name=self.user.username,
            tid='your_task_id',
            dslabel=self.dataset.label,
            email=self.user.email,
            counthit='your_count_hit',
            totalhits='your_total_hits',
            test='on'
        )


class ContactFormTestCase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='testuser', email='testuser@example.com',
                                             password='testpass')
        self.client.login(username='testuser', password='testpass')

    @patch("captcha.fields.CaptchaField.clean")
    def test_contact_form_email(self, validate_method):
      print('test in sus.argv?', 'test' in sys.argv)

      data = {
          'name': 'Test User',
          'username': 'testuser',
          'subject': 'Test Subject',
          'from_email': 'testuser@example.com',
          'message': 'Test Message',
          'captcha': 'XXX'
      }
      validate_method.return_value = True
      response = self.client.post(reverse('contact'), data=data)

      # if response.status_code != 200:
      if response.status_code != 302:
        print("Form errors:", response.context['form'].errors)

      self.assertEqual(response.status_code, 302)  # form submission was successful
      self.assertEqual(len(mail.outbox), 2) # 2 emails? (1 to user, 1 to admins)

      self.assertEqual(mail.outbox[0].to, settings.EMAIL_TO_ADMINS)
      self.assertEqual(mail.outbox[0].subject, 'Contact form submission')
      self.assertIn('on the subject of', mail.outbox[0].body )

      self.assertEqual(mail.outbox[1].to, ['testuser@example.com'])
      self.assertEqual(mail.outbox[1].subject, 'Message to WHG received')
      self.assertIn('We received your message',mail.outbox[1].body)

class NewUserTestCase(TestCase):
  def setUp(self):
    """ Create a user and dataset to test with."""
    self.user = User.objects.create_user(username='testuser',
                                         name='Test User',
                                         email='test@example.com',
                                         password='testpassword')
    self.user.save()

    self.dataset = Dataset.objects.create(
      title='Test Dataset',
      label='test_dataset',
      description='Test description',
      owner=self.user,
      ds_status='uploaded'
    )
    self.dataset.save()
    ds = self.dataset
    print('user created in setUp', self.user.email)
    print('dataset created in setUp', self.dataset.label)

  def test_new_user_emails(self):
    """ Test that two emails are sent when a new user registers."""
    self.user.email_confirmed = True
    self.user.save()
    print('user.email_confirmed', self.user.email_confirmed)
    # 1 from added dataset, 2 from new user
    self.assertEqual(len(mail.outbox), 3)

    # check subjects
    self.assertEqual(mail.outbox[0].subject, 'New Dataset Created')
    self.assertEqual(mail.outbox[1].subject, 'Welcome to WHG')
    self.assertEqual(mail.outbox[2].subject, 'New User Registered')

    # check bodies
    self.assertIn('has created a new dataset', mail.outbox[0].body)
    self.assertIn('Thank you for registering', mail.outbox[1].body)
    self.assertIn('just registered', mail.outbox[2].body)

    # check recipient
    self.assertIn(self.user.email, mail.outbox[1].to)
    self.assertEqual(mail.outbox[2].to, settings.EMAIL_TO_ADMINS)

    mail.outbox.clear()

class DatasetSignalTestCase(TestCase):
    def setUp(self):
        # Create a user and a dataset for testing
        self.user = User.objects.create_user(username='testuser', name="Test User", email='testuser@example.com', password='testpass')
        self.dataset = Dataset.objects.create(owner=self.user, title='Test Dataset', label='test_dataset')

    def test_send_new_dataset_email(self):
        # Check if an email was sent
        self.assertEqual(len(mail.outbox), 1)

        # Check the subject of the email
        self.assertEqual(mail.outbox[0].subject, 'New Dataset Created')

        # Check recipient is admins
        self.assertEqual(mail.outbox[0].to, settings.EMAIL_TO_ADMINS)

        # Clear the outbox
        mail.outbox = []

    def test_handle_public_true(self):
      # Clear the outbox
      mail.outbox = []

      # Change the public status of the dataset
      self.dataset.public = True
      self.dataset.save()

      # Check if an email was sent
      self.assertEqual(len(mail.outbox), 1)

      # Check the subject of the email
      self.assertEqual(mail.outbox[0].subject, 'Your WHG dataset has been published')

      # Check recipient is owner
      self.assertIn(self.user.email, mail.outbox[0].to)

    def test_handle_public_false(self):
      # Clear the outbox
      mail.outbox = []

      # set public True, clear outbox, then set False
      self.dataset.public = True
      self.dataset.save()
      mail.outbox = []
      self.dataset.public = False
      self.dataset.save()

      # Check if an email was sent
      self.assertEqual(len(mail.outbox), 1)

      # Check the subject of the email
      self.assertEqual(mail.outbox[0].subject, 'Your WHG dataset has been unpublished')

      # Check recipient is owner
      self.assertIn(self.user.email, mail.outbox[0].to)


    def test_handle_wdcomplete(self):
      # Clear the outbox
      mail.outbox = []

      # Change the ds_status of the dataset
      self.dataset.ds_status = 'wd-complete'
      self.dataset.save()

      # Check if an email was sent
      self.assertGreaterEqual(len(mail.outbox), 1)

      # Check the subject of the email
      self.assertEqual(mail.outbox[0].subject, 'WHG reconciliation review complete')

      # Check recipient is admins
      self.assertEqual(mail.outbox[0].to, [settings.EMAIL_TO_ADMINS])

    def test_handle_indexed(self):
      # Clear the outbox
      mail.outbox = []

      # Change the ds_status of the dataset
      self.dataset.ds_status = 'indexed'
      self.dataset.save()

      # Check if an email was sent
      self.assertGreaterEqual(len(mail.outbox), 1)

      # Check the subject of the email
      self.assertEqual(mail.outbox[0].subject, 'Your WHG dataset is fully indexed')

      # Check recipient is owner
      self.assertIn(self.user.email, mail.outbox[0].to)
