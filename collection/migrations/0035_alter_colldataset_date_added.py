# Generated by Django 4.1.7 on 2024-05-02 11:12

from django.db import migrations, models
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ('collection', '0034_alter_collplace_sequence'),
    ]

    operations = [
        migrations.AlterField(
            model_name='colldataset',
            name='date_added',
            field=models.DateTimeField(default=django.utils.timezone.now, null=True),
        ),
    ]
