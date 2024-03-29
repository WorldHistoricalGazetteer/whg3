# Generated by Django 4.1.7 on 2024-02-10 11:33

from django.db import migrations, models
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ('main', '0009_alter_tileset_collection_alter_tileset_dataset'),
    ]

    operations = [
        migrations.CreateModel(
            name='Announcement',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('content', models.CharField(help_text='A short announcement text.', max_length=255)),
                ('link', models.URLField(help_text='Link to the full announcement on the external blog.')),
                ('created_at', models.DateTimeField(default=django.utils.timezone.now, help_text='Creation date of the announcement.')),
                ('active', models.BooleanField(default=True, help_text='Whether the announcement is currently active.')),
            ],
        ),
    ]
