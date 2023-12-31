# Generated by Django 4.1.7 on 2023-05-01 14:35

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('resources', '0002_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='resource',
            name='regions',
            field=models.CharField(blank=True, choices=[(72, 'Antarctica'), (73, 'Asiatic Russia'), (74, 'Australia/New Zealand'), (75, 'Caribbean'), (76, 'Central America'), (77, 'Central Asia'), (78, 'Eastern Africa'), (79, 'Eastern Asia'), (80, 'Eastern Europe'), (81, 'European Russia'), (82, 'Melanesia'), (83, 'Micronesia'), (84, 'Middle Africa'), (85, 'Northern Africa'), (86, 'Northern America'), (87, 'Northern Europe'), (88, 'Polynesia'), (89, 'South America'), (90, 'Southeastern Asia'), (91, 'Southern Africa'), (92, 'Southern Asia'), (93, 'Southern Europe'), (94, 'Western Africa'), (95, 'Western Asia'), (96, 'Western Europe'), (99, 'Global')], max_length=24, null=True),
        ),
    ]
