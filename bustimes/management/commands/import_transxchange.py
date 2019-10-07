"""
Usage:

    ./manage.py import_transxchange EA.zip [EM.zip etc]
"""

import logging
import os
import shutil
import csv
import yaml
import zipfile
from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import transaction
from django.contrib.gis.geos import LineString, MultiLineString
from django.utils import timezone
from busstops.models import (Operator, Service, DataSource, StopPoint, StopUsage, ServiceCode, Journey, ServiceDate,
                             Region)
from busstops.management.commands.generate_departures import handle_region as generate_departures
from busstops.management.commands.generate_service_dates import handle_services as generate_service_dates
from ...models import Route, Calendar, CalendarDate, Trip, StopTime
from timetables.txc import TransXChange, Grouping, sanitize_description_part


logger = logging.getLogger(__name__)


NS = {'txc': 'http://www.transxchange.org.uk/'}


def sanitize_description(name):
    """
    Given an oddly formatted description from the North East,
    like 'Bus Station bay 5,Blyth - Grange Road turning circle,Widdrington Station',
    returns a shorter, more normal version like
    'Blyth - Widdrington Station'
    """

    parts = [sanitize_description_part(part) for part in name.split(' - ')]
    return ' - '.join(parts)


def get_line_name_and_brand(service_element):
    line_name = service_element.find('txc:Lines', NS)[0][0].text
    if '|' in line_name:
        line_name, line_brand = line_name.split('|', 1)
    else:
        line_brand = ''
    return line_name, line_brand


def infer_from_filename(filename):
    """
    Given a filename like 'ea_21-45A-_-y08-1.xml',
    returns a (net, service_code, line_ver) tuple like ('ea', 'ea_21-45A-_-y08', '1')

    Given any other sort of filename, returns ('', None, None)
    """
    parts = filename.split('-')  # ['ea_21', '3', '_', '1']
    if len(parts) == 5:
        net = parts[0].split('_')[0]
        if len(net) <= 3 and net.islower():
            return (net, '-'.join(parts[:-1]), parts[-1][:-4])
    return ('', None, None)


def correct_services():
    with open(os.path.join(settings.DATA_DIR, 'services.yaml')) as open_file:
        records = yaml.load(open_file, Loader=yaml.FullLoader)
        for service_code in records:
            services = Service.objects.filter(service_code=service_code)
            if 'operator' in records[service_code]:
                if services.exists():
                    services.get().operator.set(records[service_code]['operator'])
                    del records[service_code]['operator']
                else:
                    continue
            services.update(**records[service_code])


def get_operator_code(operator_element, element_name):
    element = operator_element.find('txc:{}'.format(element_name), NS)
    if element is not None:
        return element.text


def get_operator_name(operator_element):
    "Given an Operator element, returns the operator name or None"

    for element_name in ('TradingName', 'OperatorNameOnLicence', 'OperatorShortName'):
        name = get_operator_code(operator_element, element_name)
        if name:
            return name.replace('&amp;', '&')


def get_operator_by(scheme, code):
    if code:
        return Operator.objects.filter(operatorcode__code=code, operatorcode__source__name=scheme).first()


def line_string_from_journeypattern(journeypattern, stops):
    points = []
    stop = stops.get(journeypattern.sections[0].timinglinks[0].origin.stop.atco_code)
    if stop:
        points.append(stop.latlong)
    for timinglink in journeypattern.get_timinglinks():
        stop = stops.get(timinglink.destination.stop.atco_code)
        if stop:
            points.append(stop.latlong)
    try:
        linestring = LineString(points)
        return linestring
    except ValueError:
        pass


class Command(BaseCommand):
    @staticmethod
    def add_arguments(parser):
        parser.add_argument('filenames', nargs='+', type=str)

    def handle(self, *args, **options):
        self.calendar_cache = {}
        for archive_name in options['filenames']:
            self.handle_archive(archive_name)

    def set_region(self, archive_name):
        self.region_id, _ = os.path.splitext(os.path.basename(archive_name))

        self.source, created = DataSource.objects.get_or_create(name=self.region_id)

        if not created:
            self.source.service_set.filter(current=True).update(current=False)
            self.source.route_set.all().delete()

        if self.region_id == 'NCSD':
            self.region_id = 'GB'

    def get_operator(self, operator_element):
        "Given an Operator element, returns an operator code for an operator that exists."

        for tag_name, scheme in (
            ('NationalOperatorCode', 'National Operator Codes'),
            ('LicenceNumber', 'Licence'),
        ):
            operator_code = get_operator_code(operator_element, tag_name)
            if operator_code:
                operator = get_operator_by(scheme, operator_code)
                if operator:
                    return operator

        # Get by regional operator code
        operator_code = get_operator_code(operator_element, 'OperatorCode')
        if operator_code:
            operator = get_operator_by(self.region_id, operator_code)
            if not operator:
                operator = get_operator_by('National Operator Codes', operator_code)
            if operator:
                return operator

        # Get by name
        operator_name = get_operator_name(operator_element)

        print(operator_name)

    def get_operators(self, transxchange):
        operators = transxchange.operators
        if len(operators) > 1:
            journey_operators = {journey.operator for journey in transxchange.journeys}
            journey_operators.add(transxchange.operator)
            operators = [operator for operator in operators if operator.get('id') in journey_operators]
        operators = (self.get_operator(operator) for operator in operators)
        return [operator for operator in operators if operator]

    def set_service_descriptions(self, archive):
        # the NCSD has service descriptions in a separate file:
        self.service_descriptions = {}
        if 'IncludedServices.csv' in archive.namelist():
            with archive.open('IncludedServices.csv') as csv_file:
                reader = csv.DictReader(line.decode('utf-8') for line in csv_file)
                # e.g. {'NATX323': 'Cardiff - Liverpool'}
                for row in reader:
                    key = f"{row['Operator']}{row['LineName']}{row['Dir']}"
                    self.service_descriptions[key] = row['Description']

    def get_service_descriptions(self, filename):
        parts = filename.split('_')
        operator = parts[-2]
        line_name = parts[-1][:-4]
        key = f'{operator}{line_name}'
        outbound = self.service_descriptions.get(f'{key}O', '')
        inbound = self.service_descriptions.get(f'{key}I', '')
        return outbound, inbound

    def handle_archive(self, archive_name):
        self.service_codes = set()

        with transaction.atomic():
            self.set_region(archive_name)

            self.source.datetime = timezone.now()

            with zipfile.ZipFile(archive_name) as archive:
                self.set_service_descriptions(archive)

                for filename in archive.namelist():
                    if filename.endswith('.xml'):
                        with archive.open(filename) as open_file:
                            self.handle_file(open_file, filename)

            correct_services()

            self.source.save(update_fields=['datetime'])

        try:
            shutil.copy(archive_name, settings.TNDS_DIR)
        except shutil.SameFileError:
            pass

        if self.region_id != 'L':
            with transaction.atomic():
                Journey.objects.filter(service__region=self.region_id).delete()
                generate_departures(Region.objects.get(id=self.region_id))

            with transaction.atomic():
                ServiceDate.objects.filter(service__region=self.region_id).delete()
                generate_service_dates(Service.objects.filter(region=self.region_id))

        StopPoint.objects.filter(active=False, service__current=True).update(active=True)
        StopPoint.objects.filter(active=True, service__isnull=True).update(active=False)

        Service.objects.filter(region=self.region_id, current=False, geometry__isnull=False).update(geometry=None)

    def get_calendar(self, operating_profile, operating_period):
        calendar_dates = [
            CalendarDate(start_date=date_range.start, end_date=date_range.end, operation=False)
            for date_range in operating_profile.nonoperation_days
        ]
        calendar_dates += [
            CalendarDate(start_date=date_range.start, end_date=date_range.end, operation=True)
            for date_range in operating_profile.operation_days
        ]

        if not calendar_dates and not operating_profile.regular_days:
            return

        calendar_hash = f'{operating_profile.regular_days}{operating_period.start}{operating_period.end}'
        calendar_hash += ''.join(f'{date.start_date}{date.end_date}{date.operation}' for date in calendar_dates)

        if calendar_hash in self.calendar_cache:
            return self.calendar_cache[calendar_hash]

        calendar = Calendar(
            mon=False,
            tue=False,
            wed=False,
            thu=False,
            fri=False,
            sat=False,
            sun=False,
            start_date=operating_period.start,
            end_date=operating_period.end
        )

        for day in operating_profile.regular_days:
            if day == 0:
                calendar.mon = True
            elif day == 1:
                calendar.tue = True
            elif day == 2:
                calendar.wed = True
            elif day == 3:
                calendar.thu = True
            elif day == 4:
                calendar.fri = True
            elif day == 5:
                calendar.sat = True
            elif day == 6:
                calendar.sun = True

        calendar.save()
        for date in calendar_dates:
            date.calendar = calendar
        CalendarDate.objects.bulk_create(calendar_dates)

        self.calendar_cache[calendar_hash] = calendar

        return calendar

    def handle_file(self, open_file, filename):
        transxchange = TransXChange(open_file)

        try:
            service_element = transxchange.element.find('txc:Services/txc:Service', NS)
        except AttributeError:
            return

        if transxchange.mode == 'underground':
            return

        today = self.source.datetime.date()

        if transxchange.operating_period.end and transxchange.operating_period.end < today:
            return

        line_name, line_brand = get_line_name_and_brand(service_element)

        net, service_code, line_ver = infer_from_filename(filename)
        if service_code is None:
            service_code = transxchange.service_code

        defaults = {
            'line_name': line_name,
            'line_brand': line_brand,
            'mode': transxchange.mode,
            'net': net,
            'line_ver': line_ver,
            'region_id': self.region_id,
            'date': today,
            'current': True,
            'source': self.source,
            'show_timetable': True
        }
        if transxchange.description:
            defaults['description'] = transxchange.description

        # stops:
        stops = StopPoint.objects.in_bulk(transxchange.stops.keys())

        groupings = {
            'outbound': Grouping('outbound', transxchange),
            'inbound': Grouping('inbound', transxchange)
        }

        for journey_pattern in transxchange.journey_patterns.values():
            if journey_pattern.direction == 'inbound':
                grouping = groupings['inbound']
            else:
                grouping = groupings['outbound']
            grouping.add_journey_pattern(journey_pattern)

        try:
            stop_usages = []
            for grouping in groupings.values():
                if grouping.rows:
                    stop_usages += [
                        StopUsage(
                            service_id=service_code, stop_id=row.part.stop.atco_code,
                            direction=grouping.direction, order=i, timing_status=row.part.timingstatus
                        )
                        for i, row in enumerate(grouping.rows) if row.part.stop.atco_code in stops
                    ]
                    if grouping.direction == 'outbound' or grouping.direction == 'inbound':
                        # grouping.description_parts = transxchange.description_parts
                        defaults[grouping.direction + '_description'] = str(grouping)

            line_strings = []
            for pattern in transxchange.journey_patterns.values():
                line_string = line_string_from_journeypattern(pattern, stops)
                if line_string not in line_strings:
                    line_strings.append(line_string)
            multi_line_string = MultiLineString(*(ls for ls in line_strings if ls))

        except (AttributeError, IndexError) as error:
            logger.error(error, exc_info=True)
            defaults['show_timetable'] = False
            stop_usages = [StopUsage(service_id=service_code, stop_id=stop, order=0) for stop in stops]
            multi_line_string = None

        defaults['geometry'] = multi_line_string

        if self.service_descriptions:
            defaults['outbound_description'], defaults['inbound_description'] = self.get_service_descriptions(filename)
            defaults['description'] = defaults['outbound_description'] or defaults['inbound_description']

        service, service_created = Service.objects.update_or_create(service_code=service_code, defaults=defaults)

        operators = self.get_operators(transxchange)

        if service_created:
            service.operator.add(*operators)
        else:
            if service.slug == service_code.lower():
                service.slug = ''
                service.save()
            service.operator.set(operators)
            if service_code not in self.service_codes:
                service.stops.clear()
        StopUsage.objects.bulk_create(stop_usages)

        # a code used in Traveline Cymru URLs:

        if transxchange.journeys and transxchange.journeys[0].private_code:
            private_code = transxchange.journeys[0].private_code
            if ':' in private_code:
                ServiceCode.objects.update_or_create({
                    'code': private_code.split(':', 1)[0]
                }, service=service, scheme='Traveline Cymru')

        # timetable data:

        defaults = {
            'line_name': line_name,
            'line_brand': line_brand,
            'start_date': transxchange.operating_period.start,
            'end_date': transxchange.operating_period.end,
            'service': service,
        }
        if transxchange.description:
            defaults['description'] = transxchange.description

        route, route_created = Route.objects.get_or_create(defaults, source=self.source, code=filename)

        default_calendar = None

        for journey in transxchange.journeys:
            calendar = None
            if journey.operating_profile:
                calendar = self.get_calendar(journey.operating_profile, transxchange.operating_period)
                if not calendar:
                    continue
            else:
                if not default_calendar:
                    default_calendar = self.get_calendar(transxchange.operating_profile, transxchange.operating_period)
                calendar = default_calendar

            trip = Trip(
                inbound=journey.journey_pattern.direction == 'inbound',
                calendar=calendar,
                route=route,
                journey_pattern=journey.journey_pattern.id,
            )
            trip.save()

            stop_times = [
                StopTime(
                    stop_code=cell.stopusage.stop.atco_code,
                    trip=trip,
                    arrival=cell.arrival_time,
                    departure=cell.departure_time,
                    sequence=i,
                    timing_status=cell.stopusage.timingstatus,
                    activity=cell.stopusage.activity or ''
                ) for i, cell in enumerate(journey.get_times())
            ]

            StopTime.objects.bulk_create(stop_times)
