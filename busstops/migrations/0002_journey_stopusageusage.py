# -*- coding: utf-8 -*-
# Generated by Django 1.10.5 on 2017-02-13 19:10
from __future__ import unicode_literals

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('busstops', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='Journey',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('datetime', models.DateTimeField()),
                ('destination', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='busstops.StopPoint')),
                ('service', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='busstops.Service')),
            ],
        ),
        migrations.CreateModel(
            name='StopUsageUsage',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('datetime', models.DateTimeField()),
                ('order', models.PositiveIntegerField()),
                ('journey', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='busstops.Journey')),
                ('stop', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='busstops.StopPoint')),
            ],
        ),
    ]
