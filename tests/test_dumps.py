from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase
from datasets.models import Dataset
from places.models import Place, PlaceName
import os
import zipfile

class DumpDistinctToponymsCommandTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        # Create a user for the owner of the dataset
        User = get_user_model()
        test_user = User.objects.create_user(username='testuser', password='12345', email='testuser@foo.com')

        # Create a Dataset instance
        test_dataset = Dataset.objects.create(
            owner=test_user,
            label="dataset1",
            title="Dataset Title 1",
            description="A sample dataset for testing."
        )

        # Create Place instances and associate them with the dataset
        place1 = Place.objects.create(title="Place Title 1", src_id="src_id1", dataset=test_dataset, ccodes='{US}')
        place2 = Place.objects.create(title="Place Title 2", src_id="src_id2", dataset=test_dataset, ccodes='{US}')
        place3 = Place.objects.create(title="Place Title 3", src_id="src_id3", dataset=test_dataset, ccodes='{US}')

        # Create PlaceName instances and associate them with the Place instances
        # Assuming there's a ForeignKey or OneToOneField from PlaceName to Place
        PlaceName.objects.create(toponym="Toponym1", place=place1)
        PlaceName.objects.create(toponym="Toponym2", place=place2)
        PlaceName.objects.create(toponym="Toponym3", place=place3)


    def test_command_output_zip(self):
        # Path where the test ZIP file will be saved
        test_output_zip_path = 'temp_test_distinct_toponyms.zip'

        # Ensure any pre-existing test file is removed
        if os.path.exists(test_output_zip_path):
            os.remove(test_output_zip_path)

        # Call the management command with the test output path
        # Path where the test ZIP file will be saved
        test_output_zip_path = os.path.join('data_dumps', 'temp_test_distinct_toponyms.zip')
        call_command('dump_all_distinct_names', output=test_output_zip_path)

        # Check that the ZIP file was created
        self.assertTrue(os.path.exists(test_output_zip_path))

        # Verify the contents of the ZIP file
        with zipfile.ZipFile(test_output_zip_path, 'r') as zipf:
            namelist = zipf.namelist()
            # Assuming you're writing to a known filename within the zip
            self.assertIn('distinct_toponyms.txt', namelist)

            with zipf.open('distinct_toponyms.txt') as toponym_file:
                toponyms = toponym_file.read().decode('utf-8').splitlines()
                # Verify the expected number of toponyms
                self.assertEqual(len(toponyms), 3)
                # Optionally, verify the toponyms' content if it's deterministic
                self.assertIn('Toponym1', toponyms)

        # Cleanup: Remove the test ZIP file after the test
        os.remove(test_output_zip_path)
