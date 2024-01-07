from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from collection.models import Collection, CollPlace, TraceAnnotation
from datasets.models import Dataset, Place
from django.urls import reverse

class CollectionTestCase(TestCase):
    def setUp(self):
        # Create a User
        self.user = get_user_model().objects.create_user(name='Test User',
                                                         email='testuser@foo.com',
                                                         password='12345')

        # Create a test Dataset
        self.dataset = Dataset.objects.create(title='Test Dataset',
                                              label='test_dataset',
                                              description='Test Dataset Description',
                                              owner=self.user)

        # Create a few Place records with FK to that Dataset
        self.place1 = Place.objects.create(dataset=self.dataset,
                                           title='Place 1', src_id='12345', ccodes=['US', 'CA'],)
        self.place2 = Place.objects.create(dataset=self.dataset,
                                           title='Place 2', src_id='67890', ccodes=['US', 'CA'],)

        # Create a new Place Collection
        self.collection = Collection.objects.create(title='Test Collection',
                                                    description='Test Collection Description',
                                                    collection_class='place',
                                                    owner=self.user)

        # Create a test client
        self.client = Client()

    def test_add_places(self):
        # Login the test client
        self.client.login(username='testuser@foo.com', password='12345')

        # Call the add_places() function
        response = self.client.post(reverse('collection:collection-add-places'),
                                    {'collection': self.collection.id, 'place_list': [self.place1.id]})

        # Confirm appropriate TraceAnnotation and CollPlace records are created
        self.assertTrue(TraceAnnotation.objects.filter(collection=self.collection, place=self.place1).exists())
        self.assertTrue(CollPlace.objects.filter(collection=self.collection, place=self.place1).exists())


    # Similarly, you can modify the other test methods to call the function-based views
    def test_add_dataset_places(self):
        # Login the test client
        self.client.login(username='testuser@foo.com', password='12345')

        response = self.client.post(reverse('collection:add-dsplaces',
                                            kwargs={'coll_id': self.collection.id, 'ds_id': self.dataset.id}))

        # Confirm appropriate TraceAnnotation and CollPlace records are created
        self.assertTrue(TraceAnnotation.objects.filter(collection=self.collection,
                                                       place__in=[self.place1, self.place2]).exists())
        self.assertTrue(CollPlace.objects.filter(collection=self.collection,
                                                 place__in=[self.place1, self.place2]).exists())


    def test_remove_dataset(self):
        # Run the remove_dataset() function
        self.collection.remove_dataset(self.dataset.id)

        # Confirm CollDataset record is gone
        self.assertFalse(self.collection.datasets.filter(id=self.dataset.id).exists())

        # Confirm CollPlace records are gone
        self.assertFalse(CollPlace.objects.filter(collection=self.collection, place__in=[self.place1, self.place2]).exists())

        # Confirm TraceAnnotation.archived==True
        self.assertTrue(TraceAnnotation.objects.filter(collection=self.collection, place__in=[self.place1, self.place2], archived=True).exists())

    def test_archive_traces(self):
        # Run the archive_traces() function
        self.collection.archive_traces([self.place1.id])

        # Confirm CollPlace record is gone
        self.assertFalse(CollPlace.objects.filter(collection=self.collection, place=self.place1).exists())

        # Confirm TraceAnnotation.archived==True
        self.assertTrue(TraceAnnotation.objects.filter(collection=self.collection, place=self.place1, archived=True).exists())