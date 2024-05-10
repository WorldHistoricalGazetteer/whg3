# ./manage.py test tests.test_nogeonames.TestESLookupWDLocal

from unittest.mock import patch, MagicMock
from django.test import TestCase
from datasets.tasks import es_lookup_wdlocal  # Adjusted import path

from unittest.mock import patch, MagicMock
from django.test import TestCase
import datasets.tasks
from datasets.tasks import es_lookup_wdlocal

from unittest.mock import patch, MagicMock
from django.test import TestCase
from datasets.tasks import es_lookup_wdlocal


class TestExcludeGeonames(TestCase):
    @patch('datasets.tasks.settings.ES_CONN.search')
    def test_exclude_geonames_effectiveness(self, mock_search):
        # Dynamically adjust the mock return based on the query contents
        def search_effect(*args, **kwargs):
            query = kwargs.get('body')
            # Check if 'must_not' contains the geonames exclusion
            must_not_conditions = query['query']['bool'].get('must_not', [])
            if any(d['term']['dataset'] == 'geonames' for d in must_not_conditions):
                # Return only wikidata if geonames is correctly excluded
                return {
                    'hits': {
                        'total': {'value': 1},
                        'hits': [
                            {'_id': '2', '_source': {'name': 'Place B', 'dataset': 'wikidata'}}
                        ]
                    }
                }
            else:
                # Return both datasets otherwise
                return {
                    'hits': {
                        'total': {'value': 2},
                        'hits': [
                            {'_id': '1', '_source': {'name': 'Place A', 'dataset': 'geonames'}},
                            {'_id': '2', '_source': {'name': 'Place B', 'dataset': 'wikidata'}}
                        ]
                    }
                }

        mock_search.side_effect = search_effect

        # Call the function with exclude_geonames set to True
        result = es_lookup_wdlocal(
            {'title': 'Test Query', 'place_id': 'test123', 'variants': [], 'placetypes': [], 'countries': [],
             'authids': [], 'fclasses': []},
            bounds={'type': ['userarea'], 'id': ['0']},
            geonames='on'  # Assuming this toggles the flag
        )

        print("Function result:", result)
        geonames_hits = [hit for hit in result['hits'] if hit['_source']['dataset'] == 'geonames']
        wikidata_hits = [hit for hit in result['hits'] if hit['_source']['dataset'] == 'wikidata']

        self.assertEqual(len(geonames_hits), 0)  # No geonames hits should be present
        self.assertTrue(len(wikidata_hits) > 0)  # At least one wikidata hit should be present

