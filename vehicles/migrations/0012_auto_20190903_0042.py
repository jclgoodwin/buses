# Generated by Django 2.2.4 on 2019-09-02 23:42

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('vehicles', '0011_auto_20190829_2037'),
    ]

    operations = [
        migrations.AlterIndexTogether(
            name='vehiclelocation',
            index_together=set(),
        ),
        migrations.CreateModel(
            name='Call',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('visit_number', models.PositiveSmallIntegerField()),
                ('aimed_arrival_time', models.DateTimeField()),
                ('expected_arrival_time', models.DateTimeField()),
                ('aimed_departure_time', models.DateTimeField()),
                ('expected_departure_time', models.DateTimeField()),
                ('journey', models.ForeignKey(editable=False, on_delete=django.db.models.deletion.CASCADE, to='vehicles.VehicleJourney')),
            ],
        ),
        migrations.RemoveField(
            model_name='vehiclelocation',
            name='current',
        ),
    ]
