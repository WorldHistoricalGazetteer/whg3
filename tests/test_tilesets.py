from django.test import LiveServerTestCase
from django.test import TestCase
from parameterized import parameterized
from unittest.mock import patch
from main.views import send_tileset_request
from django.conf import settings
import requests
import json


class TestSendTilesetRequestIntegration(LiveServerTestCase):
    @parameterized.expand([
        ("datasets", 13, False),  # category, id, expect_failure
        ("collections", "4", False),
        ("datasets", "invalid_id", True),
        ("invalid_category", 9, True),
    ])
    def test_send_tileset_request(self, category, id, expect_failure):
        # Call the function with provided arguments
        result = send_tileset_request(category, id)
        
        print(result.json())

        if expect_failure: # Check if the response includes 'status': 'failure'
            self.assertEqual(result.json()['status'], 'failure')
            # Add additional assertions as needed for failure cases

        else:
            self.assertEqual(result.json()['status'], 'success')
            
            # Check that tileset can be found on the server
            url = settings.TILER_URL
            data = {
                "getTilesets": {
                    "type": category,
                    "id": id,
                }
            }
            response = requests.post(url, headers={"Content-Type": "application/json"}, data=json.dumps(data))
            print(response.json())
            response_data = response.json()

            if response.status_code == 200: # Successful response
                tilesets = response_data.get("tilesets", [])
                self.assertTrue(tilesets)  # Assert that tilesets array is not empty
                self.assertIn(f"{category}-{id}", tilesets)
                
                # If result['newtileset'] exists and is True, delete the tileset(s)
                if 'newtileset' in result.json() and result.json()['newtileset'] == True:
                    data = { "deleteTileset":tilesets[0] }
                    delete_response = requests.post(url, headers={"Content-Type": "application/json"}, data=json.dumps(data))
                    print(delete_response.json())
                    self.assertEqual(delete_response.status_code, 200)
                
            elif response.status_code == 400: # Bad Request
                error_message = response_data.get("error", "Invalid request")
                self.fail("Bad request: {}".format(error_message))                
            else:
                self.fail("Failed to retrieve tileset: {}".format(response_data))            
        
class TestSendTilesetRequest(TestCase):
    '''
    This is redundant because the range of possible responses is too complex to be reasonably simulated
    '''
    @parameterized.expand([
        (200, {"status": "success", "data": {}}, 9, "normal", "datasets"),
        (404, {"status": "failure", "message": "Dataset not found"}, 9, "normal", "datasets"),
        # Add more test cases as needed
    ])
    @patch('main.views.requests.post')
    def test_send_tileset_request(self, status_code, response_data, dataset_id, tiletype, category, mock_post):
        # Mock the response from the POST request
        mock_response = mock_post.return_value
        mock_response.status_code = status_code
        mock_response.json.return_value = response_data

        # Call the function with provided arguments
        result = send_tileset_request(dataset_id=dataset_id, tiletype=tiletype)
        
        # Construct the expected URL
        expected_url = f"https://dev.whgazetteer.org/{category}/{dataset_id}/mapdata/?variant=tileset"

        # Assert the function returned the expected result
        self.assertEqual(result, response_data)

        # Assert the POST request was called with the expected arguments
        mock_post.assert_called_once_with(
            settings.TILER_URL, 
            headers={"Content-Type": "application/json"},
            data=json.dumps({
                "geoJSONUrl": expected_url,
                "tilesetType": tiletype,
            })
        )              
        
# class TestSendTilesetRequest(TestCase):
#     @patch('main.views.requests.post')
#     def test_send_tileset_request(self, mock_post):
#         # Mock the response from the POST request
#         mock_response = mock_post.return_value
#         mock_response.status_code = 200
#         mock_response.json.return_value = {"status": "success", "data": {}}
#
#         # Call the function with a dataset_id
#         result = send_tileset_request(dataset_id=9)
#
#         # Assert the function returned the expected result
#         self.assertEqual(result, {"status": "success", "data": {}})
#
#         # Assert the POST request was called with the expected arguments
#         mock_post.assert_called_once_with(
#             settings.TILER_URL,
#             headers={"Content-Type": "application/json"},
#             data=json.dumps({
#                 "geoJSONUrl": "https://dev.whgazetteer.org/datasets/9/mapdata/?variant=tileset",
#                 "tilesetType": "normal",
#             })
#         )