from django.test import TestCase
from datasets.models import Dataset
from places.models import Place, PlaceGeom, PlaceLink
from django.contrib.auth import get_user_model

User = get_user_model()
# ./manage.py test tests.test_reconciliation.PlaceGeomPlaceLinkTest

# testing reviewr field in PlaceGeom and PlaceLink
class PlaceGeomPlaceLinkTest(TestCase):
  def setUp(self):
    self.user = User.objects.create(
        username='testuser',
        password='12345',
        email='testuser@foo.com'
    )
    test_dataset = Dataset.objects.create(
        owner=self.user,
        label="dataset1",
        title="Dataset Title 1",
        description="A sample dataset for testing."
    )
    self.place = Place.objects.create(
      dataset=test_dataset,
      src_id='test_src_id',
      title='Test Place',
      ccodes='{ES}'
    )

  def test_create_placegeom_with_task_id_without_reviewer(self):
    with self.assertRaises(ValueError):
      PlaceGeom.objects.create(
        place=self.place,
        task_id='test_task_id',
        src_id='test_src_id'
      )

  def test_create_placelink_with_task_id_without_reviewer(self):
    with self.assertRaises(ValueError):
      PlaceLink.objects.create(
        place=self.place,
        task_id='test_task_id',
        src_id='test_src_id'
      )

  def test_create_placegeom_with_task_id(self):
    placegeom = PlaceGeom.objects.create(
      place=self.place,
      task_id='test_task_id',
      src_id='test_src_id',
      reviewer=self.user
    )
    self.assertEqual(placegeom.reviewer, self.user)

  def test_create_placelink_with_task_id(self):
    placelink = PlaceLink.objects.create(
      place=self.place,
      task_id='test_task_id',
      src_id='test_src_id',
      reviewer=self.user
    )
    self.assertEqual(placelink.reviewer, self.user)

