# find/sitemaps.py

from django.contrib.sitemaps import Sitemap
from django.urls import reverse
from elasticsearch import Elasticsearch
from django.conf import settings

class ElasticSitemap(Sitemap):
    changefreq = "monthly"
    priority = 0.8
    limit = 50000  # Maximum number of URLs per sitemap file

    def __init__(self):
        super().__init__()
        self.es = Elasticsearch(settings.ELASTICSEARCH_DSL['default']['hosts'])

    def items(self):
        # Elasticsearch query to retrieve all unique toponyms
        body = {
            "size": 0,
            "aggs": {
                "unique_toponyms": {
                    "terms": {
                        "field": "toponym.keyword",
                        "size": 100000  # Adjust based on expected number of toponyms
                    }
                }
            }
        }
        response = self.es.search(index='toponyms', body=body)
        toponyms = [bucket['key'] for bucket in response['aggregations']['unique_toponyms']['buckets']]
        return toponyms

    def location(self, item):
        # Build URLs for toponym disambiguation pages
        return reverse('find:resolve_toponym', args=[item])
