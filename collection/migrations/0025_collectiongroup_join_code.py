# Generated by Django 4.1.7 on 2024-01-10 15:34

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('collection', '0024_collectiongroup_collaboration'),
    ]

    operations = [
        migrations.AddField(
            model_name='collectiongroup',
            name='join_code',
            field=models.CharField(max_length=20, null=True, unique=True),
        ),
    ]
