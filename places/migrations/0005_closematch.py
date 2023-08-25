# Generated by Django 4.1.7 on 2023-08-03 07:11

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('places', '0004_alter_placegeom_s2'),
    ]

    operations = [
        migrations.CreateModel(
            name='CloseMatch',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('place1', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='close_match1', to='places.place')),
                ('place2', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='close_match2', to='places.place')),
            ],
        ),
    ]