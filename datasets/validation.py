import logging, codecs, json, os, re, sys
import math
from dateutil.parser import parse
from frictionless import validate as fvalidate
from jsonschema import draft7_format_checker, validate, ValidationError
from .exceptions import LPFValidationError, DelimValidationError
from django.db.models.functions import Lower
from areas.models import Area
from places.models import Type

aat_fclass = {}
for type_obj in Type.objects.all():
    # aat_fclass["aat:" + str(type_obj.aat_id)] = {
    aat_fclass[type_obj.aat_id] = {
        "fclass": type_obj.fclass,
        "term": type_obj.term
    }

def parse_validation_error(error):
    # Extract key parts of the error message
    # print('parse_validation_error()', error)
    data = error.instance
    message = error.message
    schema_path = " -> ".join([str(p) for p in error.absolute_schema_path])

    # Construct a user-friendly message
    user_message = f"Error in data: {data}. Reason: {message}. Schema path: {schema_path}"

    return user_message

#
# replaces validate_tsv()
#
def validate_delim(df):
	errors = []
	# TODO: get valid ccodes from db
	# Define required fields and patterns
	aliases = ["bnf", "cerl", "dbp", "gn", "gnd", "gov", "loc", "pl", "tgn", "viaf", "wd", "wp", "whg"]
	pattern = r"https?:\/\/.*\..*|(" + "|".join(aliases) + r"):\d+"
	valid_ccodes = [ccode.upper() for c in Area.objects.filter(type='country') for ccode in c.ccodes]
	fclass_list = Type.objects.annotate(lower_fclass=Lower('fclass')).values_list('lower_fclass', flat=True).distinct()

	# Define required fields and patterns
	required_fields = ['id', 'title', 'title_source', 'start']
	pattern_constraints = {
		'ccodes': "([a-zA-Z]{2};?)+",
		'matches': pattern,
		'parent_id': "(https?:\/\/.*\\..*|#\\d*)",
		'start': "(-?\\d{1,4}(-\\d{2})?(-\\d{2})?)(\/(-?\\d{1,4}(-\\d{2})?(-\\d{2})?))?",
		'end': "(-?\\d{1,4}(-\\d{2})?(-\\d{2})?)(\/(-?\\d{1,4}(-\\d{2})?(-\\d{2})?))?"
	}
	range_constraints = {
		'lon': (-180, 180),
		'lat': (-90, 90)
	}

	# Loop through rows for validation
	for index, row in df.iterrows():
		# Check required fields
		for field in required_fields:
			if field not in row:
				errors.append({"row": index + 1, "error": f"Required field missing: {field}"})

		# Check one of "start" or "attestation_year" is non-empty
		try:
			start = parse(row.get("start")) if row.get("start") else None
		except ValueError:
			start = None

		try:
			attestation_year = int(row.get("attestation_year")) if row.get("attestation_year") else None
		except ValueError:
			attestation_year = None

		if start is None and attestation_year is None:
			errors.append({"row": index + 1, "error": "Either start or attestation_year must be present in all rows"})

		# Check one of "start" or "attestation_year" is non-empty
		# if (row.get("start") is None or math.isnan(row.get("start"))) and \
		# 	(row.get("attestation_year") is None or math.isnan(row.get("attestation_year"))):
		# 	errors.append({"row": index + 1, "error": "Either start or attestation_year must be present in all rows"})

		# Check for invalid ccodes (if present)
		if 'ccodes' in row:
			ccodes = [c.strip() for c in str(row['ccodes']).split(';') if c]
			for ccode in ccodes:
				# print('ccode', ccode)
				if ccode.upper() not in valid_ccodes:
					errors.append({"row": index + 1, "error": f"Invalid ccode: {ccode}"})

		# Check for invalid fclasses (if present)
		if 'fclasses' in row:
			fclasses = [fc.strip() for fc in str(row['fclasses']).split(';') if fc]
			# print('fclasses', fclasses)
			for fclass in fclasses:
				if fclass.lower() not in fclass_list:
					print('invalid fclass', fclass)
					errors.append({"row": index + 1,
					               "error": f"Invalid fclass: {fclass}, must be one of A, P, H, S, R, T, L"})


		# Check for unsupported aat_types
		supported_aat_types = {aat_id for aat_id in aat_fclass}
		aat_types = [int(a.strip()) for a in str(row.get('aat_types', '')).split(';') if a]
		for aat_type in aat_types:
			if aat_type not in supported_aat_types:
				errors.append({
					"row": index + 1,
					"error": f"Unsupported aat_type: {aat_type}"
				})

		# Check pattern constraints
		for field, pattern in pattern_constraints.items():
			# Check if the field exists in the row
			if field in row:
				value = str(row[field])
				# If the field's value is an empty string or "nan" or it matches the pattern, continue to the next iteration
				if value in ('', 'nan') or bool(re.search(pattern, value)):
					continue
				if field == 'matches':
					errors.append({
					    "row": index + 1,
					    "error": (
					        f"Field {field} contains an unsupported alias or invalid URL. "
					        f"Please use supported alias(es): "
					        f"{', '.join([alias + ':' for alias in aliases])}, or a valid URL."
					    )
					})
				else:
					errors.append(
						{"row": index + 1, "error": f"Field {field} contains a value ({value}) that does not match its required pattern"}
					)

		# Check range constraints
		for field, (low, high) in range_constraints.items():
			if field in row and (float(row[field]) < low or float(row[field]) > high):
				errors.append({"row": index + 1, "error": f"Value in {field} ({row[field]}) is out of the allowed range"})

	if errors:
		raise DelimValidationError(errors)

	return errors

#
# validate Linked Places json-ld (w/jsonschema)
# format ['coll' (FeatureCollection) | 'lines' (json-lines)]
# TODO: 'format' will eventually support jsonlines
def validate_lpf(tempfn, format):
	logger = logging.getLogger('django')
	# print('in validate_lpf()...format', format)
	schema = json.loads(codecs.open('datasets/static/validate/schema_lpf_v1.2.json','r','utf8').read())

	# rename tempfn
	newfn = tempfn+'.jsonld'
	os.rename(tempfn,newfn)
	infile = codecs.open(newfn, 'r', 'utf8')
	result = {"format":"lpf", "errors":[]}

	# TODO: handle json-lines
	jdata = json.loads(infile.read())
	if len(set(['type', '@context', 'features'])-set(jdata.keys())) > 0 \
		or jdata['type'] != 'FeatureCollection' \
		or len(jdata['features']) == 0:
		print('not valid GeoJSON-LD')
	else:
		errors = []
		seen_error_paths = set()

		for countrows, feat in enumerate(jdata['features'], start=1):

			if len(errors) >= 3:  # Stop after collecting 3 errors
				break
			try:
				validate(
					instance=feat,
					schema=schema,
					format_checker=draft7_format_checker
				)
			except ValidationError as e:
				error_path = " -> ".join([str(p) for p in e.absolute_path])
				if error_path not in seen_error_paths:  # Check if this error type (path) has been seen before
					detailed_error = parse_validation_error(e)
					errors.append({"feat": countrows, 'error': detailed_error})
					seen_error_paths.add(error_path)

		print('errors in validate_lpf()', errors)
		if errors:
			aggregated_message = "; ".join([error['error'] for error in errors])
			if len(errors) == 3:
				aggregated_message += " ... Your uploaded file has more errors; these were the first three found."
			# print('aggregated_message',aggregated_message )
			raise LPFValidationError(errors)
			# raise LPFValidationError(aggregated_message)

		result['count'] = countrows
	return result

#
# DEPRECATED 2023-08 (uses frictionless.py 3.31.0)
# replaced by validate_delim()
#
def validate_tsv(fn, ext):
	# incoming csv or tsv; in cases converted from xlsx or ods via pandas
	# print('validate_tsv() fn', fn)
	# pull header for missing columns test below
	header = codecs.open(fn, 'r').readlines()[0][:-1]
	header = list(map(str.lower, header.split('\t' if '\t' in header else ',')))
	# header = header.split('\t' if '\t' in header else ',')
	list(map(str.lower, header))
	# print('header', header)
	result = {"format":"delimited", "errors":[], "columns":header}
	schema_lptsv = json.loads(codecs.open('datasets/static/validate/schema_tsv.json', 'r', 'utf8').read())
	try:
		report = fvalidate(fn, schema=schema_lptsv, sync_schema=True)
	except:
		err = sys.exc_info()
		result['errors'].append('File failed format validation. Error: '+err+'; '+str(err[1].args))
		print('error on fvalidate',err)
		print('error args',err[1].args)
		return result

	if len(report['tables']) > 0:
		rpt = report['tables'][0]
		result['count'] = rpt['stats']['rows']  # count
		print('rpt errors', rpt['errors'])

	req = ['id', 'title', 'title_source', 'start']
	missing = list(set(req) - set(header))

	# filter harmless errors
	# TODO: is filtering encoding-error here problematic?
	result['errors'] = [x['message'] for x in rpt['errors'] \
	                    if x['code'] not in ["blank-header", "missing-header", "encoding-error"]]
	if len(missing) > 0:
		result['errors'].insert(0,'Required column(s) missing or header malformed: '+
		                        ', '.join(missing))

	return result
