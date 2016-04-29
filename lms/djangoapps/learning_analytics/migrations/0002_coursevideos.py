# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('learning_analytics', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='CourseVideos',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('video_name', models.CharField(max_length=255)),
                ('video_module_ids', models.CharField(max_length=255)),
                ('video_duration', models.IntegerField()),
            ],
            options={
                'db_table': 'learning_analytics_coursevideos',
            },
        ),
    ]
