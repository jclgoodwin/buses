import re
from math import ceil
from urllib.parse import quote
from webcolors import html5_parse_simple_color
from django.contrib.gis.db import models
from django.core.exceptions import ValidationError
from django.db.models import Count
from django.urls import reverse
from django.utils.safestring import mark_safe
from busstops.models import Operator, Service, DataSource, SIRISource


def get_css(colours, direction=None, horizontal=False):
    if len(colours) == 1:
        return colours[0]
    if direction is None:
        direction = 180
    background = 'linear-gradient('
    if horizontal:
        background += 'to top'
    elif direction < 180:
        background += 'to left'
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

    class Meta:
        ordering = ('name',)
        verbose_name_plural = 'liveries'

    def __str__(self):
        return self.name

    def preview(self, name=False):
        if self.css:
            background = self.css
        elif self.colours:
            background = get_css(self.colours.split(), None, self.horizontal)
        else:
            return
        div = f'<div style="height:1.5em;width:4em;background:{background}"'
        if name:
            div = f'{div}></div> {self.name}'
        else:
            div = f'{div} title="{self.name}"></div>'
        return mark_safe(div)

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
        return self.name


class Vehicle(models.Model):
    code = models.CharField(max_length=255)
    fleet_number = models.PositiveIntegerField(null=True, blank=True)
    reg = models.CharField(max_length=24, blank=True)
    source = models.ForeignKey(DataSource, models.CASCADE, null=True, blank=True)
    operator = models.ForeignKey(Operator, models.SET_NULL, null=True, blank=True)
    vehicle_type = models.ForeignKey(VehicleType, models.SET_NULL, null=True, blank=True)
    colours = models.CharField(max_length=255, blank=True)
    livery = models.ForeignKey(Livery, models.SET_NULL, null=True, blank=True)
    notes = models.CharField(max_length=255, blank=True)
    latest_location = models.ForeignKey('VehicleLocation', models.SET_NULL, null=True, blank=True,
                                        related_name='latest_vehicle', editable=False)
    features = models.ManyToManyField(VehicleFeature, blank=True)

    class Meta:
        unique_together = ('code', 'operator')

    def __str__(self):
        if len(self.reg) > 3:
            reg = self.get_reg()
            if self.fleet_number:
                return '{} - {}'.format(self.fleet_number, reg)
            return reg
        if self.fleet_number:
            return str(self.fleet_number)
        return self.code.replace('_', ' ')

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
            if self.livery.css:
                css = self.livery.css
                if direction and direction < 180:
                    for angle in re.findall(r'\((\d+)deg,', css):
                        replacement = 360 - int(angle)
                        css = css.replace(f'({angle}deg,', f'({replacement}deg,', 1)
                return css
            colours = self.livery.colours
        else:
            colours = self.colours
        if colours:
            colours = colours.split()
            return get_css(colours, direction, self.livery and self.livery.horizontal)

    def get_absolute_url(self):
        return reverse('vehicle_detail', args=(self.id,))

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
                name = str(self.operator).replace(' Buses', '', 1).replace(' Coaches', '', 1)
                if name.startswith('First ') or name.startswith('Stagecoach ') or name.startswith('Arriva '):
                    name = name.split()[0]
                search = f'{name} {search}'
        return f'https://www.flickr.com/search/?text={quote(search)}&sort=date-taken-desc'

    def get_flickr_link(self):
        return mark_safe(f'<a href="{self.get_flickr_url()}" target="_blank" rel="noopener">Flickr</a>')

    def get_livery_choices(self):
        choices = []
        liveries = Livery.objects.filter(vehicle__operator=self.operator_id).annotate(popularity=Count('vehicle'))
        for livery in liveries.order_by('-popularity').distinct():
            choices.append((livery.id, livery.preview(name=True)))
        for vehicle in Vehicle.objects.filter(operator=self.operator).exclude(colours='').distinct('colours'):
            choices.append((vehicle.colours, Livery(colours=vehicle.colours, name=vehicle.notes).preview(name=True)))
        choices.append(('Other', 'Other'))
        return choices

    get_flickr_link.short_description = 'Flickr'

    clean = Livery.clean


class VehicleEdit(models.Model):
    vehicle = models.ForeignKey(Vehicle, models.CASCADE)
    fleet_number = models.PositiveIntegerField(null=True, blank=True)
    reg = models.CharField(max_length=24, blank=True)
    vehicle_type = models.CharField(max_length=255, blank=True)
    colours = models.CharField(max_length=255, blank=True)
    livery = models.ForeignKey(Livery, models.SET_NULL, null=True, blank=True)
    notes = models.CharField(max_length=255, blank=True)

    def get_changes(self):
        changes = {}
        for field in ('fleet_number', 'reg', 'vehicle_type', 'notes'):
            edit = str(getattr(self, field) or '')
            if edit:
                if field == 'reg':
                    edit = edit.upper().replace(' ', '')
                vehicle = str(getattr(self.vehicle, field) or '')
                if edit != vehicle:
                    changes[field] = edit
        if self.colours and self.colours != self.vehicle.colours and self.colours != str(self.vehicle.livery_id):
            changes['colours'] = self.colours
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
                        return mark_safe(f'<del>{vehicle}</del>')
                    else:
                        return mark_safe(f'<del>{vehicle}</del><br><ins>{edit}</ins>')
                else:
                    return mark_safe(f'<ins>{edit}</ins>')
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
    vehicle = models.ForeignKey(Vehicle, models.CASCADE)
    code = models.CharField(max_length=255, blank=True)
    destination = models.CharField(max_length=255, blank=True)
    direction = models.CharField(max_length=8, blank=True)

    class Meta:
        ordering = ('id',)


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
    heading = models.PositiveIntegerField(null=True, blank=True)
    early = models.IntegerField(null=True, blank=True)
    current = models.BooleanField(default=False, db_index=True)

    class Meta:
        ordering = ('id',)
        index_together = (
            ('current', 'datetime')
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
                    'notes': vehicle.notes
                },
                'delta': self.early,
                'direction': self.heading,
                'datetime': self.datetime,
                'destination': journey.destination,
                'source': journey.source_id
            }
        }
        if extended:
            if vehicle.vehicle_type:
                json['properties']['vehicle']['type'] = str(vehicle.vehicle_type)
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
        else:
            if vehicle.vehicle_type:
                json['properties']['vehicle']['coach'] = vehicle.vehicle_type.coach
                json['properties']['vehicle']['decker'] = vehicle.vehicle_type.double_decker
        return json
