# Generated by Django 4.1.7 on 2024-05-28 08:56

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('places', '0019_alter_placetype_unique_together'),
    ]

    operations = [
        migrations.AlterUniqueTogether(
            name='placerelated',
            unique_together={('place', 'src_id', 'jsonb')},
        ),
    ]
