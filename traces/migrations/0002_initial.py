# Generated by Django 4.1.7 on 2023-04-09 14:50

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('traces', '0001_initial'),
        ('places', '0002_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='traceannotation',
            name='owner',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='annotations', to=settings.AUTH_USER_MODEL),
        ),
        migrations.AddField(
            model_name='traceannotation',
            name='place',
            field=models.ForeignKey(db_column='place', on_delete=django.db.models.deletion.CASCADE, related_name='places', to='places.place'),
        ),
        migrations.AddIndex(
            model_name='traceannotation',
            index=models.Index(fields=['collection'], name='trace_annot_collect_b0d79b_idx'),
        ),
        migrations.AddIndex(
            model_name='traceannotation',
            index=models.Index(fields=['place'], name='trace_annot_place_e86cee_idx'),
        ),
    ]
