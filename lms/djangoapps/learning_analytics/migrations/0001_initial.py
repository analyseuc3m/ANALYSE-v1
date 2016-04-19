# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models
import xmodule_django.models


class Migration(migrations.Migration):

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='ConsumptionModule',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('student', models.CharField(max_length=32, db_index=True)),
                ('course_key', xmodule_django.models.CourseKeyField(max_length=255, db_index=True)),
                ('module_type', models.CharField(default='video', max_length=32, db_index=True, choices=[('problem', 'problem'), ('video', 'video')])),
                ('module_key', xmodule_django.models.LocationKeyField(max_length=255, db_index=True)),
                ('display_name', models.CharField(max_length=255, db_index=True)),
                ('total_time', models.FloatField(db_index=True)),
            ],
        ),
        migrations.CreateModel(
            name='CourseAccesses',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('student_id', models.IntegerField()),
                ('course_id', xmodule_django.models.CourseKeyField(max_length=255, db_index=True)),
                ('accesses', models.CharField(default='', max_length=10000)),
                ('last_calc', models.DateTimeField(auto_now=True)),
            ],
        ),
        migrations.CreateModel(
            name='CourseProbVidProgress',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('student_id', models.IntegerField()),
                ('course_id', xmodule_django.models.CourseKeyField(max_length=255, db_index=True)),
                ('progress', models.CharField(default='', max_length=20000)),
                ('type', models.CharField(default='PROB', max_length=32, choices=[('PROB', 'problem'), ('VID', 'video')])),
                ('start_time', models.DateTimeField(default=None, null=True)),
                ('end_time', models.DateTimeField(default=None, null=True)),
                ('delta', models.FloatField()),
                ('last_calc', models.DateTimeField(auto_now=True)),
            ],
        ),
        migrations.CreateModel(
            name='CourseStruct',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('course_id', xmodule_django.models.CourseKeyField(max_length=255, db_index=True)),
                ('module_state_key', xmodule_django.models.LocationKeyField(max_length=255, db_column='module_id')),
                ('name', models.CharField(max_length=255)),
                ('section_type', models.CharField(default='chapter', max_length=32, db_index=True, choices=[('chapter', 'chapter'), ('sequential', 'sequential'), ('vertical', 'vertical')])),
                ('index', models.IntegerField()),
                ('graded', models.BooleanField(default=False)),
                ('released', models.BooleanField(default=False)),
                ('father', models.ForeignKey(blank=True, to='learning_analytics.CourseStruct', null=True)),
            ],
        ),
        migrations.CreateModel(
            name='CourseTime',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('student_id', models.IntegerField()),
                ('course_id', xmodule_django.models.CourseKeyField(max_length=255, db_index=True)),
                ('time_spent', models.CharField(default='', max_length=10000)),
                ('last_calc', models.DateTimeField(auto_now=True)),
            ],
        ),
        migrations.CreateModel(
            name='DailyConsumption',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('student', models.CharField(max_length=32, db_index=True)),
                ('course_key', xmodule_django.models.CourseKeyField(max_length=255, db_index=True)),
                ('module_type', models.CharField(default='video', max_length=32, db_index=True, choices=[('problem', 'problem'), ('video', 'video')])),
                ('dates', models.TextField()),
                ('time_per_date', models.TextField()),
            ],
        ),
        migrations.CreateModel(
            name='LastKnownTrackingLog',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('event_id', models.IntegerField()),
                ('username', models.CharField(max_length=32, blank=True)),
                ('course_key', xmodule_django.models.CourseKeyField(max_length=255, db_index=True)),
                ('indicator', models.CharField(max_length=32, blank=True)),
                ('module_key', xmodule_django.models.LocationKeyField(default=None, max_length=255, db_index=True)),
            ],
            options={
                'db_table': 'learning_analytics_lastknowntrackinglog',
            },
        ),
        migrations.CreateModel(
            name='SortGrades',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('course_id', xmodule_django.models.CourseKeyField(max_length=255, db_index=True)),
                ('sort_type', models.CharField(default='GS', max_length=32, choices=[('GS', 'GRADED_SECTIONS'), ('WS', 'WEIGHT_SECTIONS')])),
                ('category', models.CharField(default='', max_length=255)),
                ('label', models.CharField(default='', max_length=255)),
                ('name', models.CharField(default='', max_length=255)),
                ('num_not', models.IntegerField()),
                ('num_fail', models.IntegerField()),
                ('num_pass', models.IntegerField()),
                ('num_prof', models.IntegerField()),
                ('last_calc', models.DateTimeField(auto_now=True)),
            ],
        ),
        migrations.CreateModel(
            name='StudentGrades',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('student_id', models.IntegerField()),
                ('course_id', xmodule_django.models.CourseKeyField(max_length=255, db_index=True)),
                ('grades', models.TextField(default='')),
                ('grade_group', models.CharField(default='FAIL', max_length=32, choices=[('PROF', 'Proficiency'), ('OK', 'Pass'), ('FAIL', 'Fail')])),
                ('last_calc', models.DateTimeField(auto_now=True)),
            ],
        ),
        migrations.CreateModel(
            name='TimeSchedule',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('student_id', models.IntegerField()),
                ('course_id', xmodule_django.models.CourseKeyField(max_length=255, db_index=True)),
                ('time_schedule', models.TextField(default='')),
                ('last_calc', models.DateTimeField(auto_now=True)),
            ],
        ),
        migrations.CreateModel(
            name='VideoEvents',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('student', models.CharField(max_length=32, db_index=True)),
                ('course_key', xmodule_django.models.CourseKeyField(max_length=255, db_index=True)),
                ('module_key', xmodule_django.models.LocationKeyField(max_length=255, db_index=True)),
                ('display_name', models.CharField(max_length=255, db_index=True)),
                ('play_events', models.TextField()),
                ('pause_events', models.TextField()),
                ('change_speed_events', models.TextField()),
                ('seek_from_events', models.TextField()),
                ('seek_to_events', models.TextField()),
            ],
        ),
        migrations.CreateModel(
            name='VideoIntervals',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('student', models.CharField(max_length=32, db_index=True)),
                ('course_key', xmodule_django.models.CourseKeyField(max_length=255, db_index=True)),
                ('module_key', xmodule_django.models.LocationKeyField(max_length=255, db_index=True)),
                ('display_name', models.CharField(max_length=255, db_index=True)),
                ('hist_xaxis', models.TextField()),
                ('hist_yaxis', models.TextField()),
                ('interval_start', models.TextField()),
                ('interval_end', models.TextField()),
                ('ids', models.TextField()),
            ],
        ),
        migrations.CreateModel(
            name='VideoTimeWatched',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('student', models.CharField(max_length=32, db_index=True)),
                ('course_key', xmodule_django.models.CourseKeyField(max_length=255, db_index=True)),
                ('module_key', xmodule_django.models.LocationKeyField(max_length=255, db_index=True)),
                ('display_name', models.CharField(max_length=255, db_index=True)),
                ('total_time', models.FloatField(db_index=True)),
                ('percent_viewed', models.FloatField(db_index=True, null=True, blank=True)),
                ('disjointed_start', models.TextField()),
                ('disjointed_end', models.TextField()),
            ],
        ),
        migrations.AlterUniqueTogether(
            name='videotimewatched',
            unique_together=set([('student', 'module_key')]),
        ),
        migrations.AlterUniqueTogether(
            name='videointervals',
            unique_together=set([('student', 'module_key')]),
        ),
        migrations.AlterUniqueTogether(
            name='videoevents',
            unique_together=set([('student', 'module_key')]),
        ),
        migrations.AlterUniqueTogether(
            name='timeschedule',
            unique_together=set([('student_id', 'course_id')]),
        ),
        migrations.AlterUniqueTogether(
            name='studentgrades',
            unique_together=set([('student_id', 'course_id')]),
        ),
        migrations.AlterUniqueTogether(
            name='sortgrades',
            unique_together=set([('label', 'course_id', 'sort_type')]),
        ),
        migrations.AlterUniqueTogether(
            name='dailyconsumption',
            unique_together=set([('student', 'course_key', 'module_type')]),
        ),
        migrations.AlterUniqueTogether(
            name='coursetime',
            unique_together=set([('student_id', 'course_id')]),
        ),
        migrations.AlterUniqueTogether(
            name='courseprobvidprogress',
            unique_together=set([('student_id', 'course_id', 'type')]),
        ),
        migrations.AlterUniqueTogether(
            name='courseaccesses',
            unique_together=set([('student_id', 'course_id')]),
        ),
        migrations.AlterUniqueTogether(
            name='consumptionmodule',
            unique_together=set([('student', 'module_key')]),
        ),
        migrations.AlterUniqueTogether(
            name='coursestruct',
            unique_together=set([('module_state_key', 'course_id')]),
        ),
    ]
