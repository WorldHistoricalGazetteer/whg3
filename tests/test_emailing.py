# ./manage.py test --settings=tests.settings tests.test_emailing.ContactFormTestCase
# ./manage.py test --settings=tests.settings tests.test_emailing.NewUserTestCase
# ./manage.py test --settings=tests.settings tests.test_emailing.DatasetSignalTestCase

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.gis.geos import Point
from django.core import mail
from django.db import transaction
from django.test import TestCase
from django.urls import reverse
from datasets.models import Dataset
from places.models import Place, PlaceGeom
from unittest.mock import patch
import sys
import pdb

User = get_user_model()
# from datasets.tasks import align_idx
# from datasets.tasks import align_wdlocal

# CASES for new_emailer()
# ======================
# /welcome, new_user: user.email_confirmed = True; name, id
# /contact_form, contact_reply: contact form submitted

# DATASET SIGNALS
# ===============
# /new_dataset: new dataset created
# /dataset_published: public=True
# /dataset_unpublished: public=False
# /wikidata_complete: ds_status='wd-complete' -> to editorial
# /dataset_indexed: ds_status='indexed'

# TASKS
# =====
# not testable at this time (can't simulate recon task); but they work
# recon_task_success: reconciliation task SUCCESS (wdlocal or idx)
# recon_task_failed: reconciliation task FAILURE (wdlocal or idx)
# recon_task_test: test index reconciliation task SUCCESS


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


class DatasetSignalTestCase(TestCase):
    def setUp(self):
      with transaction.atomic():
        # Create a user, dataset, place and placegeom for testing
        self.user = User.objects.create_user(username='testuser', name="Test User", email='testuser@example.com',
                                             password='testpass')
        self.dataset = Dataset.objects.create(owner=self.user, title='Test Dataset',
                                              label='test_dataset', ds_status=None)
        print('dataset id', self.dataset.id)
        print('settings.CELERY_ALWAYS_EAGER', settings.CELERY_ALWAYS_EAGER == True)

        self.place = Place.objects.create(
          src_id='abc123',
          dataset=self.dataset,
          title='Test Place',
          ccodes=['TH'],
        )
        self.place_geom = PlaceGeom.objects.create(
          place=self.place,
          geom=Point(0, 0),
        )
        print(self.place_geom.geom)

    def test_send_new_dataset_email(self):
        self.dataset.ds_status = 'uploaded'
        self.dataset.save()

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
      print('dataset id', self.dataset.id)
      # pdb.set_trace()

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

    # def test_handle_indexed(self):
    #   # Clear the outbox
    #   mail.outbox = []
    #
    #   # Change the ds_status of the dataset
    #   self.dataset.ds_status = 'indexed'
    #   self.dataset.save()
    #
    #   # Check if an email was sent
    #   self.assertGreaterEqual(len(mail.outbox), 1)
    #
    #   # Check the subject of the email
    #   self.assertEqual(mail.outbox[0].subject, 'Your WHG dataset is fully indexed')
    #
    #   # Check recipient is owner
    #   self.assertIn(self.user.email, mail.outbox[0].to)

