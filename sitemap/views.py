from urllib.parse import quote

from django.contrib.sitemaps import Sitemap
from django.urls import reverse

from .models import Toponym

import logging

logger = logging.getLogger(__name__)


class StaticViewSitemap(Sitemap):
    priority = 0.9
    changefreq = 'monthly'
    alternates = []
    lastmod = None

    def items(self):
        return [
            'home',
            'about',
            'teaching',
            'credits',
            'datasets:dataset-gallery',
            'publications',
            'usingapi',
            'documentation',
            'workbench',
            'announcements-list'
        ]

    def location(self, item):
        return reverse(item)


class ToponymSitemap(Sitemap):
    priority = 0.6
    changefreq = 'monthly'
    alternates = []
    lastmod = None

    def items(self):
        return Toponym.objects.filter(instance_count__gt=1).exclude(ccodes=[]).exclude(yearspans=[]).order_by(
            '-instance_count')

    def location(self, obj):
        return f'https://whgazetteer.org/search/{quote(obj.name)}'

    def get_urls(self, page=1, site=None, protocol=None):
        items = self.items()

        urls = []
        for item in items:
            urls.append({
                'location': self.location(item),
                'lastmod': self.lastmod,
                'changefreq': self.changefreq,
                'priority': self.priority,
                'alternates': self.alternates
            })

        return urls
