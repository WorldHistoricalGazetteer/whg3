# Generated by Django 4.1.7 on 2024-09-30 15:41

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('sitemap', '0003_rename_uniquetoponym_toponym'),
    ]

    operations = [
        migrations.RenameField(
            model_name='toponym',
            old_name='timespans',
            new_name='yearspans',
        ),
    ]