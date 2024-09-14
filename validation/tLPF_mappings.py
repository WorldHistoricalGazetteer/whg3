# tLPF_mappings.py

import re
import logging

logger = logging.getLogger('validation')

# Regex to capture toponyms and RFC 5646 language tags
pattern = re.compile(r'''
    ^(?P<toponym>[^\s@]+)
    (?:@(?P<language>
        (?:(?P<language_code>[A-Za-z]{2,3})(?:-(?P<language_code_ext>[A-Za-z]{3}(-[A-Za-z]{3}){0,2}))?|[A-Za-z]{4}|[A-Za-z]{5,8})
        (-(?P<script>[A-Za-z]{4}))?
        (-(?P<region>[A-Za-z]{2}|[0-9]{3}))?
        (-(?P<variant>[A-Za-z0-9]{5,8}|[0-9][A-Za-z0-9]{3}))*
        (-(?P<extension>[0-9A-WY-Za-wy-z](-[A-Za-z0-9]{2,8})+))?
    )?)$
''', re.VERBOSE)


def variant_conversion(x):
    if not x:
        return []

    variants = []
    for variant in (v.strip() for v in x.split(';') if v.strip()):
        match = pattern.match(variant)
        if match:
            groups = match.groupdict()
            toponym = groups.get('toponym', '')
            variant_entry = {
                'toponym': toponym,
                'language': groups.get('language', '')
            }

            lang_data = {k: v for k, v in groups.items() if k != 'toponym' and v}
            if lang_data:
                variant_entry['rfc5646'] = lang_data

            lang = lang_data.get('language_code', None)
            if lang:
                variant_entry['lang'] = lang

            variants.append(variant_entry)
        else:
            variants.append({
                'toponym': variant.strip()
            })

    logger.debug(variants)

    return variants


def safe_float_conversion(x):
    """Safely convert input to float, handling empty strings and None."""
    if x is None or str(x).strip() == "":
        return None
    try:
        return float(str(x).strip())
    except ValueError:
        return None


def str_x(x, split=False):
    """
    Convert to string and remove '.0' if it's a float ending with .0.
    pandas read_excel is very uncooperative with regard to forcing dtype, and infers type regardless of configuration
    """
    stripped = re.sub(r'\.0$', '', str(x).strip())  # Remove any trailing '.0'
    if not stripped:
        if split:
            return []
        return None
    elif split:
        return stripped.split(';')
    else:
        return stripped


tLPF_mappings = {
    'id': {
        'lpf': '@id',
        'converter': lambda x: str_x(x)
    },
    'title': {
        'lpf': 'names.0.toponym',
        'converter': lambda x: str_x(x)
    },
    'title_source': {
        'lpf': 'names.0.citations.0.label',
        'converter': lambda x: str_x(x)
    },
    'fclasses': {
        'lpf': 'properties.fclasses',
        'converter': lambda x: [item.strip() for item in str_x(x, True) if item.strip()] or None
    },
    'aat_types': {
        'lpf': 'types',
        'converter': lambda x: [{'identifier': f'aat:{item.strip()}'} for item in str_x(x, True) if
                                item.strip()] or None
    },
    'attestation_year': {
        'lpf': 'names.0.citations.0.year',
        'converter': lambda x: str_x(x)
    },
    'start': {
        'lpf': 'when.timespans.0.start.in',
        'converter': lambda x: str_x(x)
    },
    'end': {
        'lpf': 'when.timespans.0.end.in',
        'converter': lambda x: str_x(x)
    },
    'title_uri': {
        'lpf': 'names.0.citations.0.@id',
        'converter': lambda x: str_x(x)
    },
    'ccodes': {
        'lpf': 'properties.ccodes',
        'converter': lambda x: [item.strip() for item in str_x(x, True) if item.strip()] or None
    },
    'matches': {
        'lpf': 'links',
        'converter': lambda x: [{'type': 'exactMatch', 'identifier': item.strip()} for item in str_x(x, True) if
                                item.strip()] or None
    },
    'variants': {
        'lpf': 'additional_names',
        'converter': lambda x: variant_conversion(x)
    },
    'types': {
        'lpf': 'additional_types',
        'converter': lambda x: [{'label': item.strip()} for item in str_x(x, True) if item.strip()] or None
    },
    'parent_name': {
        'lpf': 'relations.0',
        'converter': lambda x: {'relationType': 'gvp:broaderPartitive', 'label': str_x(x)} if str_x(x) else None
    },
    'parent_id': {
        'lpf': 'relations.0.relationTo',
        'converter': lambda x: str_x(x)
    },
    'lon': {
        'lpf': 'geometry.coordinates.0',
        'converter': lambda x: safe_float_conversion(x)
    },
    'lat': {
        'lpf': 'geometry.coordinates.1',
        'converter': lambda x: safe_float_conversion(x)
    },
    'geowkt': {
        'lpf': 'geometry.geowkt',
        'converter': lambda x: str_x(x)
    },
    'geo_source': {
        'lpf': 'geometry.citations.0.label',
        'converter': lambda x: str_x(x)
    },
    'geo_id': {
        'lpf': 'geometry.citations.0.@id',
        'converter': lambda x: str_x(x)
    },
    'description': {
        'lpf': 'descriptions.0.value',
        'converter': lambda x: str_x(x)
    },
}
