# /metrics/admin.py
import csv
from datetime import date, timedelta, datetime, time

from django.contrib import admin
from django.db.models import Sum, Min, Count, F
from django.db.models.functions import TruncDate
from django.http import HttpResponse
from django.shortcuts import render
from django.utils import timezone

from .models import RequestCount, DailyVisitor


class RequestCountAdmin(admin.ModelAdmin):
    list_display = ("date", "url", "user_type", "count")
    change_list_template = "admin/metrics_dashboard.html"

    def get_urls(self):
        from django.urls import path
        urls = super().get_urls()
        custom_urls = [
            path("metrics-dashboard/", self.admin_site.admin_view(self.metrics_dashboard), name="metrics-dashboard"),
            path("download-all-data/", self.admin_site.admin_view(self.download_all_data), name="download-all-data"),
        ]
        return custom_urls + urls

    def metrics_dashboard(self, request):
        today = timezone.now().date()
        periods = {
            "24-hours": today - timedelta(days=1),
            "30-days": today - timedelta(days=30),
            "all-time": None
        }

        # --- Prepare per-URL stats ---
        url_data_raw = []
        urls = RequestCount.objects.values_list("url", flat=True).distinct()

        for url in urls:
            row = {"url": url}
            for period_name, period_date in periods.items():
                qs = RequestCount.objects.filter(url=url)
                if period_date:
                    qs = qs.filter(date__gte=period_date)

                total = qs.aggregate(total=Sum("count"))["total"] or 0
                auth = qs.filter(user_type="authenticated").aggregate(total=Sum("count"))["total"] or 0
                row[f"{period_name}_total"] = total
                row[f"{period_name}_auth"] = auth
                row[f"{period_name}_anon"] = total - auth
                row[f"{period_name}_label"] = f"{total} reqs ({round((auth / total * 100) if total else 0)}% auth)"
            url_data_raw.append(row)

        max_counts = {p: max([row[f"{p}_total"] for row in url_data_raw] or [0]) for p in periods}
        url_data = []
        for row in url_data_raw:
            new_row = {"url": row["url"]}
            for period_name in periods:
                total = row[f"{period_name}_total"]
                max_count = max_counts[period_name]
                pct = (total / max_count * 100) if max_count else 0
                auth_count = row[f"{period_name}_auth"]
                anon_count = row[f"{period_name}_anon"]
                new_row[f"{period_name}_auth_pct"] = round((auth_count / total * pct) if total else 0, 2)
                new_row[f"{period_name}_anon_pct"] = round((anon_count / total * pct) if total else 0, 2)
                new_row[f"{period_name}_label"] = row[f"{period_name}_label"]
            url_data.append(new_row)

        # --- Helper functions ---
        def build_hourly_series(start, end):
            qs = DailyVisitor.objects.filter(timestamp__gte=start, timestamp__lte=end).annotate(
                hour=F('timestamp__hour')).values('hour').annotate(count=Count('visitor_hash', distinct=True))
            counts = {r['hour']: r['count'] for r in qs}
            return [counts.get(h, 0) for h in range(24)]

        def build_daily_series(start, end):
            qs = DailyVisitor.objects.filter(timestamp__date__gte=start, timestamp__date__lte=end).values(
                "timestamp__date").annotate(count=Count("visitor_hash", distinct=True))
            counts = {r["timestamp__date"]: r["count"] for r in qs}
            day_count = (end - start).days + 1
            return [counts.get(start + timedelta(days=i), 0) for i in range(day_count)]

        first_visits_qs = DailyVisitor.objects.values('visitor_hash').annotate(first_visit=Min('timestamp'))

        # --- Build aggregate_data ---
        aggregate_data = []
        for period_name, period_date in periods.items():
            row = {"period": period_name.capitalize()}
            if period_name == "24-hours":
                start_dt = datetime.combine(today - timedelta(days=1), time.min)
                end_dt = datetime.combine(today, time(23, 59, 59))
                unique_series = build_hourly_series(start_dt, end_dt)
                new_series = [first_visits_qs.filter(first_visit__gte=start_dt + timedelta(hours=h),
                                                     first_visit__lt=start_dt + timedelta(hours=h + 1)).count() for h in
                              range(24)]
                unique_count = sum(unique_series)
                new_count = sum(new_series)
            elif period_name == "30-days":
                start_date = today - timedelta(days=29)
                end_date = today
                unique_series = build_daily_series(start_date, end_date)
                new_series = [first_visits_qs.filter(first_visit__date=start_date + timedelta(days=i)).count() for i in
                              range(30)]
                unique_count = sum(unique_series)
                new_count = sum(new_series)
            else:  # all-time
                try:
                    start_date = DailyVisitor.objects.earliest("timestamp").timestamp.date()
                except DailyVisitor.DoesNotExist:
                    start_date = None
                end_date = today
                if start_date:
                    unique_series = build_daily_series(start_date, end_date)
                    new_series = [first_visits_qs.filter(first_visit__date=start_date + timedelta(days=i)).count() for i
                                  in range((end_date - start_date).days + 1)]
                    unique_count = sum(unique_series)
                    new_count = sum(new_series)
                else:
                    unique_series = new_series = []
                    unique_count = new_count = 0

            row.update({
                "unique_count": unique_count,
                "new_count": new_count,
                "unique_sparkline_data": unique_series,
                "new_sparkline_data": new_series
            })
            aggregate_data.append(row)

        return render(request, "admin/metrics_dashboard.html",
                      {"url_data": url_data, "aggregate_data": aggregate_data, "periods": list(periods.keys())})

    def download_all_data(self, request):
        response = HttpResponse(content_type='text/csv; charset=utf-8')
        response['Content-Disposition'] = 'attachment; filename="metrics.csv"'

        writer = csv.writer(response)

        writer.writerow(['date', 'url', 'user_type', 'count'])

        for row in RequestCount.objects.all().order_by('date', 'url'):
            writer.writerow([
                row.date,
                row.url,
                row.user_type,
                row.count,
            ])

        return response

admin.site.register(RequestCount, RequestCountAdmin)
