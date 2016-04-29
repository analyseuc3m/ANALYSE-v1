# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('learning_analytics', '0002_coursevideos'),
    ]

    operations = [
        migrations.AlterField(
            model_name='coursevideos',
            name='video_duration',
            field=models.TextField(),
        ),
    ]
