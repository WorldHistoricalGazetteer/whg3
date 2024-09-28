# find/views.py
from django.conf import settings
from django.shortcuts import render
from django.http import JsonResponse
from django.urls import reverse
from django.views import View
import requests

from api.views import collector


class ToponymResolveView(View):
    template_name = 'find/toponym.html'  # Ensure the correct path

    def get(self, request, *args, **kwargs):
        # Extracting 'toponym' from the URL parameters (kwargs)
        name = kwargs.get('toponym', None)

        # Ensure 'name' parameter is provided
        if not name:
            return JsonResponse({
                'error': 'Query requires a "toponym" parameter',
                'instructions': 'Please provide a valid name to resolve.'
            }, status=400)

        # Construct an Elasticsearch query
        q = {
            "size": 100,
            "query": {
                "bool": {
                    "must": [
                        {"exists": {"field": "whg_id"}},
                        {"multi_match": {
                            "query": name,
                            "fields": ["title^3", "names.toponym", "searchy"]
                        }},
                        {"exists": {"field": "ccodes"}},  # Ensure ccodes exist
                        {"exists": {"field": "timespans"}}  # Ensure timespans exist
                    ]
                }
            }
        }

        # Run the query
        response = collector(q, settings.ES_WHG)
        print(response)
        places = response.get('items', [])


        # Aggregate unique variants, countries, and time periods
        unique_variants = {variant for place in places for variant in place.get('hit', {}).get('searchy', [])}
        unique_countries = {cc for place in places for cc in place.get('hit', {}).get('ccodes', [])}
        unique_time_periods = {(timespan['gte'], timespan['lte']) for place in places for timespan in place.get('hit', {}).get('timespans', [])}

        # Sort the unique lists
        sorted_variants = sorted(unique_variants)
        sorted_countries = sorted(unique_countries)
        sorted_time_periods = sorted(unique_time_periods, key=lambda x: (x[0], x[1]))

        # Convert sorted_time_periods back to a list of dicts for rendering
        sorted_time_periods_dicts = [{'gte': gte, 'lte': lte} for gte, lte in sorted_time_periods]

        # Extract earliest and latest dates from sorted time periods
        earliest_date = min(gte for gte, lte in sorted_time_periods) if sorted_time_periods else None
        latest_date = max(lte for gte, lte in sorted_time_periods) if sorted_time_periods else None

        # Prepare aggregated context
        context = {
            'name': name,
            'unique_variants': sorted_variants,
            'unique_countries': sorted_countries,
            'unique_time_periods': sorted_time_periods_dicts,
            'earliest_date': earliest_date,
            'latest_date': latest_date,
        }

        # Render the result using toponym.html template
        return render(request, self.template_name, context)
