# validate tsv/csv and lpf uploads
from django.contrib.auth import get_user_model
from django.test import TestCase

import pandas as pd
import unittest

from datasets.exceptions import DelimValidationError, DelimInsertError, LPFValidationError
from datasets.insert import ds_insert_delim
from datasets.models import Dataset
from datasets.validation import validate_delim

from django.test import TestCase, Client
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

class DatasetCreateViewTest(TestCase):
    def setUp(self):
        # Create a User instance
        User = get_user_model()
        self.user = User.objects.create_user(email='test@test.com', password='12345')

        # Create a Dataset instance
        self.dataset = Dataset.objects.create(owner=self.user, label='test_dataset',
                                              title='Test Dataset',
                                              description='Test Dataset Description')

        # Define test files and expected error messages
        # TODO: invalid ccode, duplicate id
        self.validate_test_files = [
            # ('tests/data/valid_file.tsv', None),  # No errors expected
            ('tests/data/missing_field.tsv', ['Required field missing']),  # Expected error message
            ('tests/data/missing_start_value.tsv', ["Either start or attestation_year"]),  # Expected error message
            ('tests/data/missing_start_column.tsv', ["Required field missing", "Either start or attestation_year"]),  # Expected error message
            ('tests/data/unsupported_aat.tsv', ["Unsupported aat_type"]),  # Expected error message
            ('tests/data/unsupported_alias.tsv', ["unsupported alias"]),  # Expected error message
            ('tests/data/out_of_range.tsv', ["out of the allowed range"]),  # Expected error message
            ('tests/data/mixed_errors.tsv', [
              'Required field missing',
              "Either start or attestation_year",
              "unsupported alias",
              "out of the allowed range",
              "does not match the required pattern",
             ]),
        ]
        self.insert_test_files = [
            ('tests/data/invalid_geowkt.tsv', ['Error converting WKT for place']),
            ('tests/data/start_gt_end.tsv', ['Start date is greater than end date']),
            ('tests/data/invalid_ccode.tsv', ['Invalid ccode']),
            ('tests/data/invalid fclasses.tsv', ['Invalid fclass']),
        ]


    def test_validate_delim(self):
        for filename, expected_errors in self.validate_test_files:
            print('testing file:', filename)
            # Load the file and make a DataFrame
            df = pd.read_csv(filename, sep='\t')
            print(df)
            print('expected_errors:', expected_errors)
            try:
                validate_delim(df)
            except DelimValidationError as e:
                # If validate_delim() raises a DelimValidationError, check that the error messages are as expected
                if expected_errors is not None:
                    for error in e.errors:
                        self.assertTrue(any(expected_error in error["error"] for expected_error in expected_errors),
                                        f"Error message '{error['error']}' does not contain any of the expected error messages")
            else:
                # If validate_delim() does not raise a DelimValidationError, and no error was expected, the test passes
                if expected_errors is None:
                    self.assertEqual(expected_errors, None, "validate_delim() did not raise DelimValidationError as expected")
                else:
                    self.fail("validate_delim() did not raise DelimValidationError when it was expected")

    def test_ds_insert_delim(self):
        for filename, expected_errors in self.insert_test_files:
            print('processing file:', filename)
            # Load the file and make a DataFrame
            df = pd.read_csv(filename, sep='\t')

            try:
                ds_insert_delim(df, self.dataset.pk)
            except DelimInsertError as e:
                # Check that the error messages from ds_insert_delim() are as expected
                for error in e.errors:
                    self.assertIn(error["error"], expected_errors)

    def test_end_to_end(self):
        # Define the form data
        form_data = {
            'owner': self.user.pk,
            'label': 'test_dataset',
            'title': 'Test Dataset',
            'description': 'Test Dataset Description',
        }

        # Create a test file
        test_file = SimpleUploadedFile('test_file.tsv', b'id\ttitle\tstart\tend\n1\tTest\t2000\t2001\n')

        # Add the test file to the form data
        form_data['file_field_name'] = test_file

        # Send a POST request to the form URL
        response = self.client.post(reverse('datasets:dataset-create'), form_data)

        # Check the response for the expected error messages
        self.assertContains(response, 'Expected error message 1')
        self.assertContains(response, 'Expected error message 2')
        # ... Add more assertions for each expected error message ...


if __name__ == '__main__':
    unittest.main()

# class DatasetCreateTestCase(TestCase):
#     def setUp(self):
#         # Create a User instance
#         User = get_user_model()
#         self.user = User.objects.create_user(email='test@test.com', password='12345')
#
#         # Create a Dataset instance
#         self.dataset = Dataset.objects.create(owner=self.user, label='test_dataset',
#                                               title='Test Dataset',
#                                               description='Test Dataset Description')
#
#         # Define test files and expected error messages
#         self.test_files = [
#             ('tests/data/valid_file.tsv', None),  # No errors expected
#             ('tests/data/missing_field.tsv', ['Required field missing']),  # Expected error message
#             ('tests/data/missing_start_value.tsv', ["Either start or attestation_year"]),  # Expected error message
#             ('tests/data/missing_start_column.tsv', ["Required field missing", "Either start or attestation_year"]),  # Expected error message
#             ('tests/data/unsupported_aat.tsv', ["Unsupported aat_type"]),  # Expected error message
#             ('tests/data/unsupported_alias.tsv', ["unsupported alias"]),  # Expected error message
#             ('tests/data/out_of_range.tsv', ["out of the allowed range"]),  # Expected error message
#             ('tests/data/mixed_errors.tsv', [
#               'Required field missing',
#               "Either start or attestation_year",
#               "unsupported alias",
#               "out of the allowed range",
#               "does not match the required pattern",
#              ])
#         ]
#
#     def test_validate_delim(self):
#         for filename, expected_errors in self.test_files:
#             print('testing file:', filename)
#             # Load the file and make a DataFrame
#             df = pd.read_csv(filename, sep='\t')
#             print(df)
#             print('expected_errors:', expected_errors)
#             try:
#                 validate_delim(df)
#             except DelimValidationError as e:
#                 # If validate_delim() raises a DelimValidationError, check that the error messages are as expected
#                 if expected_errors is not None:
#                     for error in e.errors:
#                         self.assertTrue(any(expected_error in error["error"] for expected_error in expected_errors),
#                                         f"Error message '{error['error']}' does not contain any of the expected error messages")
#             else:
#                 # If validate_delim() does not raise a DelimValidationError, and no error was expected, the test passes
#                 if expected_errors is None:
#                     self.assertEqual(expected_errors, None, "validate_delim() did not raise DelimValidationError as expected")
#                 else:
#                     self.fail("validate_delim() did not raise DelimValidationError when it was expected")    # def test_validate_delim(self):
#
#     def test_ds_insert_delim(self):
#         for filename, expected_error in self.test_files:
#             # Only test files that are expected to be valid
#             if expected_error is None:
#                 # Load the file and make a DataFrame
#                 df = pd.read_csv(filename)
#
#                 # Submit the DataFrame and the Dataset instance to ds_insert_delim()
#                 try:
#                     ds_insert_delim(df, self.dataset.pk)
#                 except Exception as e:
#                     # If ds_insert_delim() raises an error, fail the test
#                     self.fail(f"ds_insert_delim() raised {type(e).__name__} when no error was expected")




# circa Jan 2021
# class ValidateDelimited(SimpleTestCase):
#   # saves spreadsheet as TSV to ./temp, runs validate_tsv() on it
#   # TODO: save both spreadsheet and tsv version?
#   def testValidateSpreadsheet(self):
#     import pandas as pd
#     os.chdir('/Users/karlg/Documents/repos/_whgazetteer/')
#     dd = '/Users/karlg/Documents/repos/_whgazetteer/_testdata/'
#     #files_ok = ['bdda34_xlsx.xlsx','bdda34_ods.ods']
#     files = ['bdda34_err_xlsx.xlsx','bdda34_err_ods.ods','bdda34_xlsx.xlsx','bdda34_ods.ods','bdda34_ods_extra-col.ods']
#     def get_encoding_excel(file):
#       fin = codecs.open(file, 'r')
#       return fin.encoding
#
#     errors = []
#     for f in files:
#       fn = dd+f
#       mimetype = mimetypes.guess_type(fn, strict=True)[0]
#       valid_mime = mimetype in mthash_plus.mimetypes
#       if not valid_mime:
#         errors.append({"file":f, "msg": "incorrect mimetype: "+mimetype})
#         pass
#       else:
#         if 'spreadsheet' in mimetype:
#           encoding = get_encoding_excel(fn)
#
#       if encoding and encoding.lower().startswith('utf-8'):
#         ext = mthash_plus.mimetypes[mimetype]
#
#         fnout = dd+'/_temp/'+f
#         fout=codecs.open(fnout, 'w', encoding='utf8')
#         df = pd.read_excel(fn,converters={'id': str, 'start':str, 'end':str, 'aat_types': str, 'lon': float, 'lat': float})
#         header = list(df.columns.values)
#
#         table=df.to_csv(sep='\t', index=False).replace('\nan','')
#         fout.write(table)
#         fout.close()
#         result = validate_tsv(fnout, 'tsv')
#
#         errors.append({"file":f, "msg":result['errors']})
#       else:
#         errors.append({"file":f, "msg": "incorrect encoding: "+str(encoding)})
#       print(f, mimetype, encoding)
#     print(errors)
#
#     # errors
#     self.assertIn('constraint "required" is "True"', errors[0]['msg'][0])
#     self.assertIn('constraint "pattern" is', errors[0]['msg'][1])
#     self.assertIn('Required field(s) missing', errors[1]['msg'][0])
#     self.assertIn('constraint "required" is "True"', errors[1]['msg'][1])
#     self.assertIn('constraint "pattern" is', errors[1]['msg'][2])
#     # no errors
#     self.assertEquals(errors[2]['msg'],[])
#     self.assertEquals(errors[3]['msg'],[])
#     self.assertEquals(errors[4]['msg'],[]) # extra column, no errors
#
#   # ok, 4 Jan 2021
#   def testValidateTSV(self):
#     os.chdir('/Users/karlg/Documents/repos/_whgazetteer/')
#     dd = '/Users/karlg/Documents/repos/_whgazetteer/_testdata/'
#     #files_ok = ['diamonds135.tsv', 'croniken20.tsv', 'bdda34.csv']
#     #files_err = ['bdda34_errors.tsv','bdda34_extra-col.csv','bdda34_missing-col.csv', 'bdda34_utf16.tsv']
#     files_err = ['priest_1line.tsv']
#
#     def get_encoding_type(file):
#       with open(file, 'rb') as f:
#         rawdata = f.read()
#       return detect(rawdata)['encoding']
#
#     def get_encoding_excel(file):
#       fin = codecs.open(file, 'r')
#       return fin.encoding
#
#     errors = []
#     #for f in files:
#     for f in files_err:
#       fn = dd+f
#       mimetype = mimetypes.guess_type(fn, strict=True)[0]
#       valid_mime = mimetype in mthash_plus.mimetypes
#       if not valid_mime:
#         errors.append({"file":f, "msg": "incorrect mimetype: "+mimetype})
#         pass
#       else:
#         if mimetype.startswith('text/'):
#           encoding = get_encoding_type(fn)
#         elif 'spreadsheet' in mimetype:
#           encoding = get_encoding_excel(fn)
#
#       if encoding and encoding.lower().startswith('utf-8'):
#         ext = mthash_plus.mimetypes[mimetype]
#         result = validate_tsv(fn, ext)
#         errors.append({"file":f, "msg":result['errors']})
#         # validate_tsv() adds extension; strip it
#         os.rename(fn+'.'+ext,fn)
#       else:
#         errors.append({"file":f, "msg": "incorrect encoding: "+str(encoding)})
#
#       print(f, mimetype, encoding)
#     print(errors)
#
#     # tests
#     self.assertIn('constraint "required"', errors[0]['msg'][0]) # missing 'start'
#     self.assertIn('constraint "pattern"', errors[0]['msg'][1]) # malformed ccodes (commas)
#     self.assertEquals(errors[1]['msg'],[])
#     self.assertIn('Required field(s) missing', errors[2]['msg'][0])
#     self.assertIn('incorrect encoding', errors[3]['msg'])
#
  
# TODO: validate_lpf(filepath,'coll')

# DatasetCreateModelForm ->
# class CallViews(SimpleTestCase):
#   def testViews(self):
#     responses = []
#     urls = ['dashboard', 'datasets:dataset-create']
#     param_urls = ['datasets:ds_summary', 'datasets:dataset-delete']
#     client = Client()
#     for url in urls:
#       responses.append( client.get(reverse(url)).status_code )
#
#     for url in param_urls:
#       responses.append( HttpResponseRedirect(reverse(url, args=(99999,))).status_code )
#
#     self.assertEquals(list(set(responses)), [302])
