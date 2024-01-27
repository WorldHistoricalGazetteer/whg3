from django.test import TestCase
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core import mail
User = get_user_model()
from datasets.models import Dataset
# ./manage.py test --settings=tests.settings tests.test_emailing.EmailerTestCase

class EmailerTestCase(TestCase):
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

  def test_new_dataset_email(self):
    """ dataset is created """
    initial_outbox_length = len(mail.outbox)
    print('in test_new_dataset_email, initial_outbox_length', initial_outbox_length)

    # outbox was cleared; should be 1 from new dataset
    self.assertEqual(len(mail.outbox), 1)

    # Check subject of the last email
    self.assertEqual(mail.outbox[0].subject, 'New Dataset Created')

    # Check the recipient of the email
    self.assertEqual(mail.outbox[0].to, settings.EMAIL_TO_ADMINS)

  # def test_dataset_wdcomplete_email(self):
  #   """ reconciliation to wikidata complete: 'wd-complete' """
  #   print('test_dataset_wdcomplete_email')
  #   initial_outbox_length = len(mail.outbox)
  #
  #   # Set the dataset to private
  #   self.dataset.status = 'wd-complete'
  #   self.dataset.save()
  #
  #   # email sent?
  #   self.assertEqual(len(mail.outbox), initial_outbox_length + 1)
  #
  #   # Check subject
  #   self.assertEqual(mail.outbox[-1].subject, 'WHG reconciliation review complete')
  #
  #   # recipient is dataset owner
  #   self.assertIn(self.user.email, mail.outbox[-1].to)
  #
  # def test_dataset_published_email(self):
  #   """ dataset published (public set to True) """
  #   print('in test_dataset_published_email')
  #   initial_outbox_length = len(mail.outbox)
  #
  #   # Set the dataset to public
  #   self.dataset.public = True
  #   self.dataset.save()
  #
  #   # email sent?
  #   self.assertEqual(len(mail.outbox), initial_outbox_length + 1)
  #
  #   # Check subject
  #   self.assertEqual(mail.outbox[-1].subject, 'Your WHG dataset has been published')
  #
  #   # recipient is dataset owner
  #   self.assertIn(self.user.email, mail.outbox[-1].to)
  #
  # def test_dataset_unpublished_email(self):
  #   """ Test email is sent when a dataset public set to False."""
  #   print('in test_dataset_published_email')
  #   initial_outbox_length = len(mail.outbox)
  #
  #   # Set the dataset to private
  #   self.dataset.public = False
  #   self.dataset.save()
  #
  #   # Check if an email was sent
  #   self.assertEqual(len(mail.outbox), initial_outbox_length + 1)
  #
  #   # Check the subject of the email
  #   self.assertEqual(mail.outbox[-1].subject, 'Your WHG dataset has been unpublished')
  #
  #   # Check the recipient of the email
  #   self.assertIn(self.user.email, mail.outbox[-1].to)
  #
  # def test_dataset_indexed_email(self):
  #   """ Test email is sent when a dataset is indexed."""
  #   print('test_dataset_indexed_email')
  #   initial_outbox_length = len(mail.outbox)
  #
  #   # Set the dataset status to 'indexed'
  #   self.dataset.ds_status = 'indexed'
  #   self.dataset.save()
  #
  #   # email sent?
  #   self.assertEqual(len(mail.outbox), initial_outbox_length + 1)
  #
  #   # Check subject
  #   self.assertEqual(mail.outbox[-1].subject, 'Your WHG dataset is fully indexed')
  #
  #   # recipient is dataset owner
  #   self.assertIn(self.user.email, mail.outbox[-1].to)

  # def tearDown(self):
  #   # Clean up any objects you created in setUp().
  #   self.user.delete()
