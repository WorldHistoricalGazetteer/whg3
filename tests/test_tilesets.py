from django.test import LiveServerTestCase
from django.test import TestCase
from unittest.mock import patch
from main.views import send_tileset_request
from django.conf import settings
import json


class TestSendTilesetRequestIntegration(LiveServerTestCase):
    def test_send_tileset_request(self):
        # Call the function with a dataset_id
        result = send_tileset_request(dataset_id=9)

        # Assert the function returned a success status
        self.assertEqual(result['status'], 'success')

        # Optionally, you could also check that a tileset was actually created
        # on the server. The details of how to do this would depend on your
        # specific application.
class TestSendTilesetRequest(TestCase):
    @patch('main.views.requests.post')
    def test_send_tileset_request(self, mock_post):
        # Mock the response from the POST request
        mock_response = mock_post.return_value
        mock_response.status_code = 200
        mock_response.json.return_value = {"status": "success", "data": {}}

        # Call the function with a dataset_id
        result = send_tileset_request(dataset_id=9)

        # Assert the function returned the expected result
        self.assertEqual(result, {"status": "success", "data": {}})

        # Assert the POST request was called with the expected arguments
        mock_post.assert_called_once_with(
            settings.TILER_URL,
            headers={"Content-Type": "application/json"},
            data=json.dumps({
                "geoJSONUrl": "https://dev.whgazetteer.org/datasets/9/mapdata/?variant=tileset",
                "tilesetType": "normal",
            })
        )