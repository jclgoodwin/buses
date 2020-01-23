import re
from math import ceil
from urllib.parse import quote
from webcolors import html5_parse_simple_color
from datetime import timedelta
from django.utils import timezone
from django.contrib.gis.db import models
from django.contrib.postgres.fields import JSONField
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.db.models import Index, Q
from django.urls import reverse
from django.utils.html import escape, format_html
from busstops.models import Operator, Service, StopPoint, DataSource, SIRISource


def get_css(colours, direction=None, horizontal=False, angle=None):
    if len(colours) == 1:
        return colours[0]
    if direction is None:
        direction = 180
    background = 'linear-gradient('
    if horizontal:
        background += 'to top'
    elif direction < 180:
        if angle:
            background += f'{360-angle}deg'
        else:
            background += 'to left'
    elif angle:
        background += f'{angle}deg'
    else:
        background += 'to right'
    percentage = 100 / len(colours)
    for i, colour in enumerate(colours):
        if i != 0 and colour != colours[i - 1]:
            background += ',{} {}%'.format(colour, ceil(percentage * i))
        if i != len(colours) - 1 and colour != colours[i + 1]:
            background += ',{} {}%'.format(colour, ceil(percentage * (i + 1)))
    background += ')'

    return background


def get_brightness(colour):
    return (0.299 * colour.red + 0.587 * colour.green + 0.114 * colour.blue) / 255


def get_text_colour(colours):
    colours = colours.split()
    colours = [html5_parse_simple_color(colour) for colour in colours]
    brightnesses = [get_brightness(colour) for colour in colours]
    colours_length = len(colours)
    if colours_length > 2:
        middle_brightness = sum(brightnesses[1:-1])
        outer_brightness = (brightnesses[0] + brightnesses[-1])
        brightness = (middle_brightness * 2 + outer_brightness) / ((colours_length - 2) * 2 + 2)
    else:
        brightness = sum(brightnesses) / colours_length
    if brightness < .5:
        return '#fff'


class VehicleType(models.Model):
    name = models.CharField(max_length=255, unique=True)
    double_decker = models.NullBooleanField()
    coach = models.NullBooleanField()

    class Meta:
        ordering = ('name',)

    def __str__(self):
        return self.name


class Livery(models.Model):
    name = models.CharField(max_length=255, unique=True)
    colours = models.CharField(max_length=255, blank=True)
    css = models.CharField(max_length=255, blank=True)
    horizontal = models.BooleanField(default=False)
    angle = models.PositiveSmallIntegerField(null=True, blank=True)

    class Meta:
        ordering = ('name',)
        verbose_name_plural = 'liveries'

    def __str__(self):
        return self.name

    def get_css(self, direction=None):
        if self.css:
            css = self.css
            if direction is not None and direction < 180:
                for angle in re.findall(r'\((\d+)deg,', css):
                    replacement = 360 - int(angle)
                    css = css.replace(f'({angle}deg,', f'({replacement}deg,', 1)
                    # doesn't work with e.g. angles {a, b} where a = 360 - b
                css = css.replace('left', 'right')
            return escape(css)
        if self.colours:
            return get_css(self.colours.split(), direction, self.horizontal, self.angle)

    def preview(self, name=False):
        background = self.get_css()
        if not background:
            return
        div = f'<div style="height:1.5em;width:2.25em;background:{background}"'
        if name:
            return format_html(div + '></div> {}', self.name)
        else:
            return format_html(div + ' title="{}"></div>', self.name)

    def clean(self):
        if self.colours:
            try:
                get_text_colour(self.colours)
            except ValueError as e:
                raise ValidationError({
                    'colours': str(e)
                })


class VehicleFeature(models.Model):
    name = models.CharField(max_length=255, unique=True)

    def __str__(self):
        if self.name[1:].islower():
            return self.name.lower()
        return self.name


class Vehicle(models.Model):
    code = models.CharField(max_length=255)
    fleet_number = models.PositiveIntegerField(null=True, blank=True)
    fleet_code = models.CharField(max_length=24, blank=True)
    reg = models.CharField(max_length=24, blank=True)
    source = models.ForeignKey(DataSource, models.CASCADE, null=True, blank=True)
    operator = models.ForeignKey(Operator, models.SET_NULL, null=True, blank=True)
    vehicle_type = models.ForeignKey(VehicleType, models.SET_NULL, null=True, blank=True)
    colours = models.CharField(max_length=255, blank=True)
    livery = models.ForeignKey(Livery, models.SET_NULL, null=True, blank=True)
    name = models.CharField(max_length=255, blank=True)
    branding = models.CharField(max_length=255, blank=True)
    notes = models.CharField(max_length=255, blank=True)
    latest_location = models.ForeignKey('VehicleLocation', models.SET_NULL, null=True, blank=True,
                                        related_name='latest_vehicle', editable=False)
    features = models.ManyToManyField(VehicleFeature, blank=True)
    withdrawn = models.BooleanField(default=False)
    data = JSONField(null=True, blank=True)

    def save(self, force_insert=False, force_update=False, **kwargs):
        if self.fleet_number and not self.fleet_code:
            self.fleet_code = str(self.fleet_number)
        super().save(force_insert, force_update, **kwargs)

    class Meta:
        unique_together = ('code', 'operator')

    def __str__(self):
        fleet_code = self.fleet_code or self.fleet_number
        if len(self.reg) > 3:
            reg = self.get_reg()
            if fleet_code:
                return '{} - {}'.format(fleet_code, reg)
            return reg
        if fleet_code:
            return str(fleet_code)
        return self.code.replace('_', ' ')

    def get_previous(self):
        if self.fleet_number and self.operator:
            vehicles = self.operator.vehicle_set.filter(withdrawn=False, fleet_number__lt=self.fleet_number)
            return vehicles.order_by('-fleet_number').first()

    def get_next(self):
        if self.fleet_number and self.operator:
            vehicles = self.operator.vehicle_set.filter(withdrawn=False, fleet_number__gt=self.fleet_number)
            return vehicles.order_by('fleet_number').first()

    def get_reg(self):
        if self.reg[-3:].isalpha():
            return self.reg[:-3] + '\u00A0' + self.reg[-3:]
        if self.reg[:3].isalpha():
            return self.reg[:3] + '\u00A0' + self.reg[3:]
        if self.reg[-2:].isalpha():
            return self.reg[:-2] + '\u00A0' + self.reg[-2:]
        return self.reg

    def get_text_colour(self):
        colours = self.livery and self.livery.colours or self.colours
        if colours:
            return get_text_colour(colours)

    def get_livery(self, direction=None):
        if self.livery:
            return self.livery.get_css(direction=direction)
        else:
            colours = self.colours
        if colours:
            colours = colours.split()
            return get_css(colours, direction, self.livery and self.livery.horizontal)

    def get_absolute_url(self):
        return reverse('vehicle_detail', args=(self.id,))

    def fleet_number_mismatch(self):
        if self.code.isdigit():
            if self.fleet_number and self.fleet_number != int(self.code):
                return True
        elif self.reg:
            code = self.code.replace('-', '').replace('_', '').replace(' ', '')
            if self.reg not in code:
                fleet_code = self.fleet_code.replace(' ', '') or self.fleet_number
                if not fleet_code or str(fleet_code) not in code:
                    return True

    def get_flickr_url(self):
        if self.reg:
            reg = self.get_reg().replace('\xa0', ' ')
            search = f'{self.reg} or "{reg}"'
        else:
            if self.fleet_number:
                search = str(self.fleet_number)
            else:
                search = str(self).replace('/', ' ')
            if self.operator:
                name = str(self.operator).split(' (', 1)[0]
                if 'Yellow' not in name:
                    name = str(self.operator).replace(' Buses', '', 1).replace(' Coaches', '', 1)
                if name.startswith('First ') or name.startswith('Stagecoach ') or name.startswith('Arriva '):
                    name = name.split()[0]
                search = f'{name} {search}'
        return f'https://www.flickr.com/search/?text={quote(search)}&sort=date-taken-desc'

    def get_flickr_link(self):
        return format_html('<a href="{}" target="_blank" rel="noopener">Flickr</a>', self.get_flickr_url())

    get_flickr_link.short_description = 'Flickr'

    clean = Livery.clean

    def maybe_change_operator(self, operator):
        if self.operator_id != operator.id:
            week_ago = timezone.now() - timedelta(days=7)
            # hasn't operated as the current operator in the last week
            if not self.vehiclejourney_set.filter(service__operator=self.operator_id, datetime__gt=week_ago).exists():
                self.operator_id = operator.id
                self.save(update_fields=['operator'])

    def update_last_modified(self):
        if self.latest_location.journey.service_id:
            cache.set(f'{self.latest_location.journey.service_id}:vehicles_last_modified', timezone.now())


class VehicleEdit(models.Model):
    vehicle = models.ForeignKey(Vehicle, models.CASCADE)
    fleet_number = models.CharField(max_length=24, blank=True)
    reg = models.CharField(max_length=24, blank=True)
    vehicle_type = models.CharField(max_length=255, blank=True)
    colours = models.CharField(max_length=255, blank=True)
    livery = models.ForeignKey(Livery, models.SET_NULL, null=True, blank=True)
    name = models.CharField(max_length=255, blank=True)
    branding = models.CharField(max_length=255, blank=True)
    notes = models.CharField(max_length=255, blank=True)
    features = models.ManyToManyField(VehicleFeature, blank=True)
    withdrawn = models.BooleanField(default=False)
    changes = JSONField(null=True, blank=True)
    url = models.URLField(blank=True)
    approved = models.BooleanField(default=False)
    datetime = models.DateTimeField(null=True, blank=True)
    user = models.CharField(max_length=255, blank=True)

    def get_changes(self):
        changes = {}
        for field in ('fleet_number', 'reg', 'vehicle_type', 'branding', 'name', 'notes', 'colours', 'livery'):
            edit = str(getattr(self, field) or '')
            if edit:
                if field == 'reg':
                    edit = edit.upper().replace(' ', '')
                vehicle = str(getattr(self.vehicle, field) or '')
                if edit != vehicle:
                    changes[field] = edit
        if self.features.all():
            features = [feature for feature in self.features.all() if feature not in self.vehicle.features.all()]
            features += [feature for feature in self.vehicle.features.all() if feature not in self.features.all()]
            if features:
                changes['features'] = features
        if self.withdrawn and not self.vehicle.withdrawn:
            changes['withdrawn'] = True
        if self.changes and self.changes != self.vehicle.data:
            changes = {**self.changes, **changes}
        return changes

    def get_diff(self, field):
        vehicle = str(getattr(self.vehicle, field) or '')
        edit = str(getattr(self, field) or '')
        if field == 'reg':
            edit = edit.upper().replace(' ', '')
        if vehicle != edit:
            if edit:
                if vehicle:
                    if edit == f'-{vehicle}':
                        return format_html('<del>{}</del>', vehicle)
                    else:
                        return format_html('<del>{}</del><br><ins>{}</ins>', vehicle, edit)
                else:
                    return format_html('<ins>{}</ins>', edit)
        return vehicle

    def get_absolute_url(self):
        return self.vehicle.get_absolute_url()

    def __str__(self):
        return str(self.vehicle)


class VehicleJourney(models.Model):
    datetime = models.DateTimeField()
    service = models.ForeignKey(Service, models.SET_NULL, null=True, blank=True)
    route_name = models.CharField(max_length=64, blank=True)
    source = models.ForeignKey(DataSource, models.CASCADE)
    vehicle = models.ForeignKey(Vehicle, models.CASCADE, null=True, blank=True)
    code = models.CharField(max_length=255, blank=True)
    destination = models.CharField(max_length=255, blank=True)
    direction = models.CharField(max_length=8, blank=True)

    def get_absolute_url(self):
        return reverse('journey_detail', args=(self.id,))

    def __str__(self):
        return f'{self.datetime}'

    class Meta:
        ordering = ('id',)
        index_together = (
            ('vehicle', 'datetime'),
            ('service', 'datetime'),
        )


class Call(models.Model):
    journey = models.ForeignKey(VehicleJourney, models.CASCADE, editable=False)
    visit_number = models.PositiveSmallIntegerField()
    stop = models.ForeignKey(StopPoint, models.CASCADE)
    aimed_arrival_time = models.DateTimeField(null=True)
    expected_arrival_time = models.DateTimeField(null=True)
    aimed_departure_time = models.DateTimeField(null=True)
    expected_departure_time = models.DateTimeField(null=True)

    def arrival_delay(self):
        if self.expected_arrival_time and self.aimed_arrival_time:
            delay = (self.expected_arrival_time - self.aimed_arrival_time).total_seconds()
            if delay:
                return '{0:+d}'.format(int(delay / 60))
        return ''

    def departure_delay(self):
        if self.expected_departure_time and self.aimed_departure_time:
            delay = (self.expected_departure_time - self.aimed_departure_time).total_seconds()
            if delay:
                return '{0:+d}'.format(int(delay / 60))
        return ''

    class Meta:
        index_together = (
            ('stop', 'expected_departure_time'),
        )


class JourneyCode(models.Model):
    code = models.CharField(max_length=64, blank=True)
    service = models.ForeignKey(Service, models.SET_NULL, null=True, blank=True)
    data_source = models.ForeignKey(DataSource, models.SET_NULL, null=True, blank=True)
    siri_source = models.ForeignKey(SIRISource, models.SET_NULL, null=True, blank=True)
    destination = models.CharField(max_length=255, blank=True)

    class Meta:
        unique_together = ('code', 'service', 'siri_source')


class VehicleLocation(models.Model):
    datetime = models.DateTimeField()
    latlong = models.PointField()
    journey = models.ForeignKey(VehicleJourney, models.CASCADE)
    heading = models.PositiveSmallIntegerField(null=True, blank=True)
    early = models.SmallIntegerField(null=True, blank=True)
    delay = models.SmallIntegerField(null=True, blank=True)
    current = models.BooleanField(default=False)

    class Meta:
        ordering = ('id',)
        indexes = (
            Index(name='datetime', fields=('datetime',), condition=Q(current=True)),
            Index(name='datetime_latlong', fields=('datetime', 'latlong'), condition=Q(current=True)),
        )

    def get_json(self, extended=False):
        journey = self.journey
        vehicle = journey.vehicle
        json = {
            'type': 'Feature',
            'geometry': {
                'type': 'Point',
                'coordinates': tuple(self.latlong),
            },
            'properties': {
                'vehicle': {
                    'url': vehicle.get_absolute_url(),
                    'name': str(vehicle),
                    'text_colour': vehicle.get_text_colour(),
                    'livery': vehicle.get_livery(self.heading),
                    'features': [str(feature) for feature in vehicle.features.all()]
                },
                'delta': self.early,
                'direction': self.heading,
                'datetime': self.datetime,
                'destination': journey.destination,
                'source': journey.source_id
            }
        }
        if vehicle.vehicle_type:
            json['properties']['vehicle']['coach'] = vehicle.vehicle_type.coach
            json['properties']['vehicle']['decker'] = vehicle.vehicle_type.double_decker
        if extended:
            if journey.service:
                json['properties']['service'] = {
                    'line_name': journey.service.line_name,
                    'url': journey.service.get_absolute_url()
                }
            else:
                json['properties']['service'] = {
                    'line_name': journey.route_name
                }
            if vehicle.operator:
                json['properties']['operator'] = str(vehicle.operator)
        return json
