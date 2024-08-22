# Generated by Django 4.1.7 on 2024-08-22 09:06

import django.core.validators
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('persons', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='EmailAddress',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('address', models.EmailField(max_length=254, unique=True, validators=[django.core.validators.EmailValidator(message='Enter a valid email address.')])),
            ],
            options={
                'verbose_name': 'Email Address',
                'verbose_name_plural': 'Email Addresses',
            },
        ),
        migrations.RemoveField(
            model_name='person',
            name='email',
        ),
        migrations.AddConstraint(
            model_name='person',
            constraint=models.UniqueConstraint(fields=('family', 'given', 'orcid'), name='unique_person'),
        ),
        migrations.AddField(
            model_name='person',
            name='emails',
            field=models.ManyToManyField(blank=True, related_name='persons', to='persons.emailaddress'),
        ),
    ]