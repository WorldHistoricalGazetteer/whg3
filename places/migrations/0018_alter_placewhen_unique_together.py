# Generated by Django 4.1.7 on 2024-05-27 17:54

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('places', '0017_alter_placelink_unique_together'),
    ]

    operations = [
        migrations.AlterUniqueTogether(
            name='placewhen',
            unique_together={('place', 'src_id', 'jsonb')},
        ),
    ]
