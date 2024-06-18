from unittest.mock import patch, MagicMock
from django.test import TestCase
from places.models import Place, CloseMatch
from datasets.models import Dataset
from datasets.tasks import maxID
from datasets.views import indexMatch
from django_celery_results.models import TaskResult
from django.conf import settings
from django.contrib.auth import get_user_model

User = get_user_model()

class IndexMatchTestCase(TestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Mock the Elasticsearch settings once for all tests
        settings.ES_CONN = MagicMock()
        settings.ES_WHG = 'test_index'

    def setUp(self):
        # Ensure the user is created
        self.user, _ = User.objects.get_or_create(
            username='test_user',
            defaults={
                'email': 'user@useme.com',
                'given_name': 'Test',
                'password': 'testpassword',
                'surname': 'User'
            }
        )
        self.task = TaskResult.objects.create(task_name='test_task')

        self.test_dataset = Dataset.objects.create(
            title='Test Dataset',
            owner=self.user,
            label='test_dataset',
            description='Test description'
        )

    def tearDown(self):
        # Clean up any created objects (if necessary)
        TaskResult.objects.all().delete()
        Dataset.objects.all().delete()
        Place.objects.all().delete()
        CloseMatch.objects.all().delete()
        User.objects.all().delete()

    def test_index_match(self):
        # Create a mock place
        place = Place.objects.create(
            src_id='abc123',
            dataset=self.test_dataset,
            ccodes=['BR']
        )
        place_id = place.id

        # Mock Elasticsearch response for place_id
        es_response_no_hits = {
            'hits': {
                'total': {'value': 0},
                'hits': []
            }
        }

        es_response_hit = {
            'hits': {
                'total': {'value': 1},
                'hits': [{
                    '_id': 'parent_id',
                    '_source': {
                        'relation': {'name': 'parent'},
                        'place_id': 'parent_place_id',
                        'children': []
                    }
                }]
            }
        }

        # Mock the maxID function
        def mock_maxID(es, idx):
            return 1000

        with patch('datasets.views.es.search', side_effect=[es_response_no_hits, es_response_hit]), \
             patch('datasets.tasks.maxID', side_effect=mock_maxID), \
             patch('datasets.views.es.index'), \
             patch('datasets.views.es.update_by_query'):

            # Test case: No match found, create new parent
            indexMatch(place_id, user=self.user, task=self.task)
            new_parent = Place.objects.get(id=place_id)
            self.assertEqual(new_parent.relation['name'], 'parent')
            self.assertEqual(CloseMatch.objects.filter(place_a_id=new_parent.id).count(), 0)

            # Test case: Match found, create new child and update parent
            another_place = Place.objects.create(src_id='def456', dataset=self.test_dataset)
            another_place_id = another_place.id
            indexMatch(another_place_id, hit_pid='parent_place_id', user=self.user, task=self.task)

            new_child = Place.objects.get(id=another_place_id)
            self.assertEqual(new_child.relation['name'], 'child')
            self.assertTrue(CloseMatch.objects.filter(place_a_id='parent_place_id', place_b_id=new_child.id).exists())

# To run the tests
if __name__ == '__main__':
    from django.core.management import call_command
    call_command('test', __name__)