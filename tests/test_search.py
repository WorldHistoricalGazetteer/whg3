from django.test import TestCase, Client
from django.urls import reverse
from search.views import SearchViewNew  # Adjust the import path as necessary

"""
{'size': 100, 
    'query': {'bool': {'must': [
     {'exists': {'field': 'whg_id'}}, 
     {'multi_match': {'query': 'abydos', 'fields': ['title^3', 'names.toponym', 'searchy']}}
 ]}}
}
{'size': 100, 
    'query': {'bool': {'must': [
    {'exists': {'field': 'whg_id'}}, 
    {'multi_match': {'query': 'abydos', 'fields': ['title^3', 'names.toponym', 'searchy']}}, 
    {'terms': {'ccodes': ['AU', 'NZ']}}
    ]}}
}
v2 fclasses, countries
==
{'size': 100, 
    'query': {'bool': {'must': [
        {'exists': {'field': 'whg_id'}}, 
        {'multi_match': {'query': 'Allepo', 'fields': ['title^3', 'names.toponym', 'searchy']}}, 
        {'terms': {'fclasses': ['X', 'P']}}
    ], 
    'filter': {'geo_shape': {'geoms.location': {'shape': {'type': 'MultiPolygon', 'coordinates': [[]]}, 'relation': 'intersects'}}}}}}
"""
class SearchViewNewTests(TestCase):

    def setUp(self):
        self.client = Client()

    def test_build_search_query_exact(self):
        params = {
            "qstr": "Abydos",
            "mode": "exact",
            # ... other params ...
        }
        query = SearchViewNew.build_search_query(params, params['mode'])
        expected_query = {
            # ... expected Elasticsearch query structure for 'starts' mode ...
        }
        self.assertEqual(query, expected_query)

    def test_build_search_query_starts(self):
        params = {
            "qstr": "Aby",
            "mode": "starts",
            # ... other params ...
        }
        query = SearchViewNew.build_search_query(params, params['mode'])
        expected_query = {
            # ... expected Elasticsearch query structure for 'starts' mode ...
        }
        self.assertEqual(query, expected_query)

    def test_build_search_query_in(self):
        params = {
            "qstr": "bydos",
            "mode": "in",
            # ... other params ...
        }
        query = SearchViewNew.build_search_query(params, params['mode'])
        expected_query = {
            # ... expected Elasticsearch query structure for 'starts' mode ...
        }
        self.assertEqual(query, expected_query)

    def test_build_search_query_fuzzy(self):
        params = {
            "qstr": "Abydos",
            "mode": "fuzzy",
            # ... other params ...
        }
        query = SearchViewNew.build_search_query(params, params['mode'])
        expected_query = {
            # ... expected Elasticsearch query structure for 'starts' mode ...
        }
        self.assertEqual(query, expected_query)

    def test_handle_request_get(self):
        response = self.client.get(reverse('your_view_name'), {'qstr': 'test', 'mode': 'in'})
        self.assertEqual(response.status_code, 200)
        # Additional assertions to check response content

    # ... additional test cases ...

