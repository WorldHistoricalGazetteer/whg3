# Generated by Django 4.1.7 on 2023-05-09 08:41

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('places', '0002_initial'),
        ('collection', '0012_alter_collection_places'),
        ('traces', '0003_traceannotation_archived_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='traceannotation',
            name='collection',
            field=models.ForeignKey(db_column='collection', on_delete=django.db.models.deletion.CASCADE, related_name='traces', to='collection.collection'),
        ),
        migrations.AlterField(
            model_name='traceannotation',
            name='place',
            field=models.ForeignKey(db_column='place', on_delete=django.db.models.deletion.CASCADE, related_name='traces', to='places.place'),
        ),
    ]
