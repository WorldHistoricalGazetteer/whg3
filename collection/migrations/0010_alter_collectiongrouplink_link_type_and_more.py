# Generated by Django 4.1.7 on 2023-05-01 14:35

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('collection', '0009_alter_collectiongroup_file_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='collectiongrouplink',
            name='link_type',
            field=models.CharField(choices=[('webpage', "<i title class='fas fa-window-maximize'></i>"), ('image', '<img src="/static/images/noun-photo.svg" width="16"/>'), ('pdf', "<i title class='far fa-file-pdf linky'></i>")], default='page', max_length=10),
        ),
        migrations.AlterField(
            model_name='collectionlink',
            name='link_type',
            field=models.CharField(choices=[('webpage', "<i title class='fas fa-window-maximize'></i>"), ('image', '<img src="/static/images/noun-photo.svg" width="16"/>'), ('pdf', "<i title class='far fa-file-pdf linky'></i>")], default='webpage', max_length=10),
        ),
    ]
