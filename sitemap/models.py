from django.db import models

class Toponym(models.Model):
    name = models.CharField(max_length=255, unique=True)
    ccodes = models.JSONField(default=list, db_index=True)
    yearspans = models.JSONField(default=list, db_index=True)
    instance_count = models.IntegerField(default=1, db_index=True)

    def __str__(self):
        return self.name

    class Meta:
        db_table = 'toponyms'
