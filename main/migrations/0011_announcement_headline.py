# Generated by Django 4.1.7 on 2024-02-10 12:37

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('main', '0010_announcement'),
    ]

    operations = [
        migrations.AddField(
            model_name='announcement',
            name='headline',
            field=models.CharField(default='', help_text='Appears linked to the full announcement.', max_length=255),
            preserve_default=False,
        ),
    ]
