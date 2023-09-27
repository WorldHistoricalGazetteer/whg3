# Generated by Django 4.1.7 on 2023-09-03 00:17

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('areas', '0005_alter_area_type'),
    ]

    operations = [
        migrations.AlterField(
            model_name='area',
            name='type',
            field=models.CharField(choices=[('copied', 'CopyPasted GeoJSON'), ('predefined', 'World Regions'), ('drawn', 'User drawn'), ('ccodes', 'Country codes'), ('search', 'Region/Polity record')], max_length=20),
        ),
    ]