from django.db import models


class RequestCount(models.Model):
    date = models.DateField(auto_now_add=True)  # date of the request
    url = models.TextField()  # store request.path
    user_type = models.CharField(max_length=20, choices=[
        ("authenticated", "Authenticated"),
        ("anonymous", "Anonymous"),
    ])
    count = models.BigIntegerField(default=0)

    class Meta:
        indexes = [
            models.Index(fields=["date", "url", "user_type"]),
        ]

    def __str__(self):
        return f"{self.date} {self.url} ({self.user_type}): {self.count}"


class DailyVisitor(models.Model):
    request_count = models.ForeignKey(RequestCount, on_delete=models.CASCADE, related_name="visitors")
    visitor_hash = models.CharField(max_length=64)  # SHA256 hash
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("request_count", "visitor_hash")
        indexes = [
            models.Index(fields=["visitor_hash"]),
        ]
