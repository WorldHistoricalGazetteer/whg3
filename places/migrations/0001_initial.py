# Generated by Django 4.1.7 on 2023-04-09 14:50

import django.contrib.gis.db.models.fields
import django.contrib.postgres.fields
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='Place',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(max_length=255)),
                ('src_id', models.CharField(blank=True, max_length=2044)),
                ('ccodes', django.contrib.postgres.fields.ArrayField(base_field=models.CharField(max_length=2, null=True), blank=True, size=None)),
                ('minmax', django.contrib.postgres.fields.ArrayField(base_field=models.IntegerField(blank=True, null=True), blank=True, null=True, size=None)),
                ('timespans', models.JSONField(blank=True, null=True)),
                ('fclasses', django.contrib.postgres.fields.ArrayField(base_field=models.CharField(choices=[('A', 'Administrative divisions'), ('H', 'Hydrological features'), ('L', 'Landscape, regions'), ('P', 'Populated places (settlements)'), ('R', 'Roads, routes, transportation'), ('S', 'Sites (various)'), ('T', 'Topographical features'), ('U', 'Undersea features'), ('V', 'Vegetation landcover')], max_length=1), blank=True, null=True, size=None)),
                ('indexed', models.BooleanField(default=False)),
                ('flag', models.BooleanField(default=False)),
                ('review_wd', models.IntegerField(choices=[(0, 'Unreviewed'), (1, 'Reviewed'), (2, 'Deferred')], null=True)),
                ('review_tgn', models.IntegerField(choices=[(0, 'Unreviewed'), (1, 'Reviewed'), (2, 'Deferred')], null=True)),
                ('review_whg', models.IntegerField(choices=[(0, 'Unreviewed'), (1, 'Reviewed'), (2, 'Deferred')], null=True)),
            ],
            options={
                'db_table': 'places',
                'managed': True,
            },
        ),
        migrations.CreateModel(
            name='PlaceDepiction',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('src_id', models.CharField(default='', max_length=100)),
                ('jsonb', models.JSONField(blank=True, null=True)),
            ],
            options={
                'db_table': 'place_depiction',
                'managed': True,
            },
        ),
        migrations.CreateModel(
            name='PlaceDescription',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('src_id', models.CharField(default='', max_length=100)),
                ('jsonb', models.JSONField(blank=True, null=True)),
                ('task_id', models.CharField(blank=True, max_length=100, null=True)),
            ],
            options={
                'db_table': 'place_description',
                'managed': True,
            },
        ),
        migrations.CreateModel(
            name='PlaceGeom',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('src_id', models.CharField(default='', max_length=100)),
                ('jsonb', models.JSONField(blank=True, null=True)),
                ('task_id', models.CharField(blank=True, max_length=100, null=True)),
                ('geom', django.contrib.gis.db.models.fields.GeometryField(blank=True, null=True, srid=4326)),
                ('created', models.DateTimeField(auto_now_add=True, null=True)),
            ],
            options={
                'db_table': 'place_geom',
                'managed': True,
            },
        ),
        migrations.CreateModel(
            name='PlaceLink',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('src_id', models.CharField(default='', max_length=100)),
                ('jsonb', models.JSONField(blank=True, null=True)),
                ('task_id', models.CharField(blank=True, max_length=100, null=True)),
                ('review_note', models.CharField(blank=True, max_length=2044, null=True)),
                ('black_parent', models.IntegerField(blank=True, null=True)),
                ('created', models.DateTimeField(auto_now_add=True, null=True)),
            ],
            options={
                'db_table': 'place_link',
                'managed': True,
            },
        ),
        migrations.CreateModel(
            name='PlaceName',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('src_id', models.CharField(default='', max_length=100)),
                ('jsonb', models.JSONField(blank=True, null=True)),
                ('task_id', models.CharField(blank=True, max_length=100, null=True)),
                ('toponym', models.CharField(max_length=2044)),
            ],
            options={
                'db_table': 'place_name',
                'managed': True,
            },
        ),
        migrations.CreateModel(
            name='PlaceRelated',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('src_id', models.CharField(default='', max_length=100)),
                ('jsonb', models.JSONField(blank=True, null=True)),
            ],
            options={
                'db_table': 'place_related',
                'managed': True,
            },
        ),
        migrations.CreateModel(
            name='PlaceType',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('src_id', models.CharField(default='', max_length=100)),
                ('jsonb', models.JSONField(blank=True, null=True)),
                ('aat_id', models.IntegerField(blank=True, null=True)),
                ('fclass', models.CharField(choices=[('A', 'Administrative divisions'), ('H', 'Hydrological features'), ('L', 'Landscape, regions'), ('P', 'Populated places (settlements)'), ('R', 'Roads, routes, transportation'), ('S', 'Sites (various)'), ('T', 'Topographical features'), ('U', 'Undersea features'), ('V', 'Vegetation landcover')], max_length=1)),
            ],
            options={
                'db_table': 'place_type',
                'managed': True,
            },
        ),
        migrations.CreateModel(
            name='PlaceWhen',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('src_id', models.CharField(default='', max_length=100)),
                ('jsonb', models.JSONField(blank=True, null=True)),
                ('minmax', django.contrib.postgres.fields.ArrayField(base_field=models.IntegerField(blank=True, null=True), null=True, size=None)),
            ],
            options={
                'db_table': 'place_when',
                'managed': True,
            },
        ),
        migrations.CreateModel(
            name='Source',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('src_id', models.CharField(max_length=30, unique=True)),
                ('uri', models.URLField(blank=True, null=True)),
                ('label', models.CharField(max_length=255)),
                ('citation', models.CharField(blank=True, max_length=500, null=True)),
            ],
            options={
                'db_table': 'sources',
                'managed': True,
            },
        ),
        migrations.CreateModel(
            name='Type',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('aat_id', models.IntegerField(unique=True)),
                ('parent_id', models.IntegerField(blank=True, null=True)),
                ('term', models.CharField(max_length=100)),
                ('term_full', models.CharField(max_length=100)),
                ('note', models.TextField(max_length=3000)),
                ('fclass', models.CharField(blank=True, max_length=1, null=True)),
            ],
            options={
                'db_table': 'types',
                'managed': True,
            },
        ),
    ]