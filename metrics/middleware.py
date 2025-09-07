import datetime
import hashlib
import re
from django.utils.deprecation import MiddlewareMixin
from django.db.models import F

from whg import settings
from .models import RequestCount, DailyVisitor

METRIC_URL_PATTERNS = [
    r"^/$",
    r"^/api/(?!teaching/|area_list/?$).*$",
    r"^/search/$",
    r"^/teaching/$",
    r"^/workbench/$",
    r"^/datasets/\d+/.*$",
    r"^/collections/\d+/.*$",
]

VISITOR_SALT = getattr(settings, "METRICS_VISITOR_SALT")


class MetricsMiddleware(MiddlewareMixin):
    def process_response(self, request, response):
        url = request.path
        if not any(re.match(pattern, url) for pattern in METRIC_URL_PATTERNS):
            return response

        user_type = "authenticated" if request.user.is_authenticated else "anonymous"
        today = datetime.date.today()

        obj, created = RequestCount.objects.get_or_create(
            date=today,
            url=url,
            user_type=user_type,
            defaults={"count": 0}
        )

        # Increment total request count
        if created:
            obj.count = 1
            obj.save(update_fields=["count"])
        else:
            RequestCount.objects.filter(
                date=today, url=url, user_type=user_type
            ).update(count=F("count") + 1)

        # Compute anonymised visitor hash
        visitor_str = f"{request.META.get('REMOTE_ADDR','')}{request.META.get('HTTP_USER_AGENT','')}{VISITOR_SALT}"
        visitor_hash = hashlib.sha256(visitor_str.encode("utf-8")).hexdigest()

        # Track unique visitor
        DailyVisitor.objects.get_or_create(
            request_count=obj, visitor_hash=visitor_hash
        )

        return response
