# Generated by Django 4.1.7 on 2024-05-02 10:30

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('collection', '0032_alter_collplace_sequence'),
    ]

    operations = [
        migrations.AlterField(
            model_name='colldataset',
            name='date_added',
            field=models.DateTimeField(auto_now_add=True, null=True),
        ),
    ]
