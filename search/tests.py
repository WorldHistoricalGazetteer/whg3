# We will use this file to test our search function
# not unit tests, but just to test the search_type variations
import json
from django.conf import settings
from search.views import SearchViewNew, suggester
es = settings.ES_CONN
import jsonlines

def suggestion_item_modes(s):
    h = s['hit']
    unique_children = list(set(h['children']))
    item = {
        "title": h['title'],
        "variants": [n for n in h['searchy'] if n != h['title']],
        "fclasses": h['fclasses'],
    }
    return item

def test_search_modes(qstr, search_type):
    # Call the build_search_query function
    params = {
        "qstr": qstr,
        "idx": "whg",
        "fclasses": None,
        "start": None,
        "end": None,
        "undated": None,
        "bounds": None,
        "countries": None,
        "method": "GET",
        "mode": search_type
    }
    query = SearchViewNew.build_search_query(params, search_type)

    # Call the suggester function
    results = suggester(query, [params["idx"]])
    suggestions = [suggestion_item_modes(s) for s in results]

    # for suggestion in suggestions:
    #     print(suggestion)

    # Print the results in jsonlines format
    with jsonlines.open('search/testoutput.jsonl', mode='w') as writer:
        for suggestion in suggestions:
            writer.write(suggestion)

# Test the function: in, starts, fuzzy, default
# test_search_modes("Abydos", "exact")
# test_search_modes("Abydos", "in")
# test_search_modes("Abyd", "starts")
test_search_modes("Abydos", "fuzzy")