# metrics/management/commands/spoof_data.py
import datetime
import random
import hashlib

from django.core.management.base import BaseCommand
from django.db import transaction

from metrics.models import RequestCount, DailyVisitor


class Command(BaseCommand):
    help = "Clears old metrics and spoofs historical data to test the dashboard sparklines."

    """
    
    IMPORTANT: REMOVE auto_now_add=True from DailyVisitor timestamp field in models.py before running this command!
    
    """

    def handle(self, *args, **options):
        self.stdout.write("Clearing old metrics data...")
        RequestCount.objects.all().delete()
        DailyVisitor.objects.all().delete()

        self.stdout.write("Spoofing data for the last 75 days...")

        urls = [
            "/",
            "/search/",
            "/teaching/",
            "/api/places/123/",
            "/datasets/456/",
            "/collections/789/",
        ]
        user_types = ["authenticated", "anonymous"]

        # Stable pool of visitor hashes
        total_visitors = 5000
        all_visitors = [
            hashlib.sha256(f"visitor_{i}".encode("utf-8")).hexdigest()
            for i in range(total_visitors)
        ]

        with transaction.atomic():
            for i in range(75, 0, -1):  # 75 days history
                date = datetime.date.today() - datetime.timedelta(days=i)
                self.stdout.write(f"  > Creating data for {date.isoformat()}")

                # Random sample of visitors active today
                num_visitors = random.randint(50, 200)
                visitor_hashes = random.sample(all_visitors, num_visitors)

                for url in urls:
                    for user_type in user_types:
                        count = random.randint(20, 200)

                        rc = RequestCount.objects.create(
                            date=date, url=url, user_type=user_type, count=count
                        )

                        # DailyVisitor entries
                        for hash in random.sample(visitor_hashes, k=random.randint(5, 15)):
                            timestamp = datetime.datetime.combine(
                                date,
                                datetime.time(
                                    hour=random.randint(0, 23),
                                    minute=random.randint(0, 59),
                                ),
                            )
                            DailyVisitor.objects.create(
                                request_count=rc,
                                visitor_hash=hash,
                                timestamp=timestamp,
                            )

        self.stdout.write(self.style.SUCCESS("Successfully cleared and spoofed historical data!"))
