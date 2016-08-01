"""Represent TransXChange concepts, and generate a matrix timetable from
TransXChange documents
"""
import os
import re
import zipfile
import cPickle as pickle
import xml.etree.cElementTree as ET
from datetime import date, datetime
from django.utils.dateparse import parse_duration
from django.utils.text import slugify
from django.core.cache import cache
import titlecase

DIR = os.path.dirname(__file__)
NS = {
    'txc': 'http://www.transxchange.org.uk/'
}
# A safe date far from any daylight savings changes or leap seconds
DUMMY_DATE = date(2016, 4, 5)
DESCRIPTION_REGEX = re.compile(r'.+,([^ ].+)$')


def time_between(end, start):
    """Return the timedelta between two times (by converting them to datetimes)."""
    return datetime.combine(DUMMY_DATE, end) - datetime.combine(DUMMY_DATE, start)


def add_time(time, delta):
    """Add a timededelta the delta between two times (by naively converting them to datetimes)."""
    return (datetime.combine(DUMMY_DATE, time) + delta).time()


def sanitize_description_part(part):
    """Given an oddly formatted part like 'Bus Station bay 5,Blyth',
    returns a shorter, more normal version like 'Blyth'
    """
    sanitized_part = DESCRIPTION_REGEX.match(part.strip())
    return sanitized_part.group(1) if sanitized_part is not None else part


class Stop(object):
    """A TransXChange StopPoint."""
    stop = None
    locality = None

    def __init__(self, element):
        self.atco_code = element.find('txc:StopPointRef', NS).text
        self.common_name = element.find('txc:CommonName', NS).text
        locality_element = element.find('txc:LocalityName', NS)
        if locality_element is not None:
            self.locality = locality_element.text

    def __unicode__(self):
        if self.locality is None or self.locality in self.common_name:
            return self.common_name
        else:
            return '%s %s' % (self.locality, self.common_name)

    def is_at(self, text):
        """Whether a given slugified tring roughly matches either
        this stop's locality's name, or this stop's name
        (e.g. 'kings-lynn' matches 'kings-lynn-bus-station' and vice versa).
        """
        locality_name = slugify(self.stop.locality.name if self.stop else self.locality)
        if locality_name and locality_name in text or text in locality_name:
            return True
        name = slugify(self.common_name)
        return text in name or name in text


class Row(object):
    """A row in a grouping in a timetable.
    Each row is associated with a Stop, and a list of times.
    """
    def __init__(self, part):
        self.part = part
        part.row = self
        self.times = []
        self.sequencenumbers = {}

    def __lt__(self, other):
        for key in self.sequencenumbers:
            if key in other.sequencenumbers:
                return self.sequencenumbers[key] < other.sequencenumbers[key]
        return max(self.sequencenumbers.values()) < max(other.sequencenumbers.values())


class Cell(object):
    """Represents a special cell in a timetable, spanning multiple rows and columns,
    with some text like 'then every 5 minutes until'.
    """
    def __init__(self, colspan, rowspan, duration):
        self.colspan = colspan
        self.rowspan = rowspan
        if duration.seconds == 3600:
            self.text = 'then hourly until'
        elif duration.seconds % 3600 == 0:
            self.text = 'then every %d hours until' % (duration.seconds / 3600)
        else:
            self.text = 'then every %d minutes until' % (duration.seconds / 60)


class Grouping(object):
    """Probably either 'outbound' or 'inbound'.
    (Could perhaps be extended to group by weekends, bank holidays in the future).
    """
    def __init__(self, direction, service_description_parts):
        self.direction = direction
        self.service_description_parts = service_description_parts
        self.column_heads = []
        self.column_feet = []
        self.journeys = []
        self.rows = {}

    def has_minor_stops(self):
        for row in self.rows:
            if row.part.timingstatus == 'OTH':
                return True
        return False

    def starts_at(self, locality_name):
        return self.rows[0].part.stop.is_at(locality_name)

    def ends_at(self, locality_name):
        return self.rows[-1].part.stop.is_at(locality_name)

    def do_heads_and_feet(self):
        self.rows = self.rows.values()

        if not self.journeys:
            return

        if self.rows and self.rows[0].part.sequencenumber is None:
            self.rows.sort()

        prev_journey = None
        head_span = 0
        in_a_row = 0
        prev_difference = None
        difference = None
        foot_span = 0
        for i, journey in enumerate(self.journeys):
            if prev_journey:
                if not journey.operating_profile and not prev_journey.operating_profile:
                    difference = time_between(journey.departure_time, prev_journey.departure_time)
                    if prev_difference == difference:
                        in_a_row += 1
                elif prev_journey.operating_profile != journey.operating_profile:
                    self.column_heads.append(ColumnHead(prev_journey.operating_profile, head_span))
                    head_span = 0
                    if in_a_row > 1:
                        abbreviate(self, i, in_a_row - 1, prev_difference)
                    in_a_row = 0
                elif prev_journey.journeypattern.id == journey.journeypattern.id:
                    difference = time_between(journey.departure_time, prev_journey.departure_time)
                    if difference == prev_difference:
                        in_a_row += 1
                    else:
                        if in_a_row > 1:
                            abbreviate(self, i, in_a_row - 1, prev_difference)
                        in_a_row = 0
                else:
                    if in_a_row > 1:
                        abbreviate(self, i, in_a_row - 1, prev_difference)
                    in_a_row = 0

                if str(prev_journey.notes) != str(journey.notes):
                    if prev_journey.notes:
                        self.column_feet.append(ColumnFoot(prev_journey.notes.values(), foot_span))
                        foot_span = 0

            head_span += 1
            prev_difference = difference
            difference = None
            if journey:
                prev_journey = journey
            foot_span += 1
        if in_a_row > 1:
            abbreviate(self, len(self.journeys), in_a_row - 1, prev_difference)
        self.column_heads.append(ColumnHead(prev_journey.operating_profile, head_span))
        self.column_feet.append(ColumnFoot(prev_journey.notes.values(), foot_span))

    def __unicode__(self):
        if hasattr(self, 'service_description_parts') and self.service_description_parts:
            start = slugify(self.service_description_parts[0])
            end = slugify(self.service_description_parts[-1])
            if self.starts_at(start) or self.ends_at(end):
                return ' - '.join(self.service_description_parts)
            if self.starts_at(end) or self.ends_at(start):
                self.service_description_parts.reverse()
                return ' - '.join(self.service_description_parts)
        return self.direction.capitalize()


class JourneyPattern(object):
    """A collection of JourneyPatternSections, in order."""
    def __init__(self, element, sections, (outbound_grouping, inbound_grouping)):
        self.id = element.attrib.get('id')
        self.journeys = []
        self.sections = [
            sections[section_element.text]
            for section_element in element.findall('txc:JourneyPatternSectionRefs', NS)
        ]

        origin = self.sections[0].timinglinks[0].origin

        self.rows = []
        self.rows.append(Row(origin))
        for section in self.sections:
            for timinglink in section.timinglinks:
                self.rows.append(Row(timinglink.destination))

        direction_element = element.find('txc:Direction', NS)
        if direction_element is not None and direction_element.text == 'outbound':
            self.grouping = outbound_grouping
        else:
            self.grouping = inbound_grouping

        if origin.sequencenumber is not None:
            for row in self.rows:
                if row.part.sequencenumber not in self.grouping.rows:
                    self.grouping.rows[row.part.sequencenumber] = row
        else:
            visited_stops = []
            i = 0
            for row in self.rows:
                if row.part.stop.atco_code not in self.grouping.rows:
                    self.grouping.rows[row.part.stop.atco_code] = row
                    row.sequencenumbers[self.id] = i
                elif row.part.stop.atco_code in visited_stops:
                    self.grouping.rows[i] = row
                    row.part.row = row
                    row.sequencenumbers[self.id] = i
                else:
                    row.part.row = self.grouping.rows[row.part.stop.atco_code]
                    row.part.row.sequencenumbers[self.id] = i
                i += 1
                visited_stops.append(row.part.stop.atco_code)


class JourneyPatternSection(object):
    """A collection of JourneyPatternStopUsages, in order."""
    def __init__(self, element, stops):
        self.timinglinks = [
            JourneyPatternTimingLink(timinglink_element, stops)
            for timinglink_element in element
        ]


class JourneyPatternStopUsage(object):
    """Either a 'From' or 'To' element in TransXChange."""
    def __init__(self, element, stops):
        # self.activity = element.find('txc:Activity', NS).text
        self.sequencenumber = element.get('SequenceNumber')
        if self.sequencenumber is not None:
            self.sequencenumber = int(self.sequencenumber)
        self.stop = stops.get(element.find('txc:StopPointRef', NS).text)
        self.timingstatus = element.find('txc:TimingStatus', NS).text

        waittime_element = element.find('txc:WaitTime', NS)
        if waittime_element is not None:
            self.waittime = parse_duration(waittime_element.text)

        self.row = None
        self.parent = None


class JourneyPatternTimingLink(object):
    def __init__(self, element, stops):
        self.origin = JourneyPatternStopUsage(element.find('txc:From', NS), stops)
        self.destination = JourneyPatternStopUsage(element.find('txc:To', NS), stops)
        self.origin.parent = self.destination.parent = self
        self.runtime = parse_duration(element.find('txc:RunTime', NS).text)
        self.id = element.get('id')


def get_deadruns(journey_element):
    """Given a VehicleJourney element, return a tuple."""
    start_element = journey_element.find('txc:StartDeadRun', NS)
    end_element = journey_element.find('txc:EndDeadRun', NS)
    return (get_deadrun_ref(start_element), get_deadrun_ref(end_element))


def get_deadrun_ref(deadrun_element):
    """Given a StartDeadRun or EndDeadRun element,
    return the ID of a JourneyPetternTimingLink.
    """
    if deadrun_element is not None:
        return deadrun_element.find('txc:ShortWorking/txc:JourneyPatternTimingLinkRef', NS).text


class VehicleJourney(object):
    """A journey represents a scheduled journey that happens at most once per
    day. A sort of "instance" of a JourneyPattern, made distinct by having its
    own start time (and possibly operating profile and dead run).
    """
    operating_profile = None

    def __init__(self, element, journeypatterns, servicedorgs):
        self.departure_time = datetime.strptime(
            element.find('txc:DepartureTime', NS).text, '%H:%M:%S'
        ).time()

        self.code = element.find('txc:VehicleJourneyCode', NS).text

        journeypatternref_element = element.find('txc:JourneyPatternRef', NS)
        if journeypatternref_element is not None:
            self.journeypattern = journeypatterns[journeypatternref_element.text]
        else:
            # Journey has no direct reference to a JourneyPattern
            # instead it as a reference to a similar journey with does
            self.journeyref = element.find('txc:VehicleJourneyRef', NS).text

        self.start_deadrun, self.end_deadrun = get_deadruns(element)

        note_elements = element.findall('txc:Note', NS)
        if note_elements is not None:
            self.notes = {
                note_element.find('txc:NoteCode', NS).text: note_element.find('txc:NoteText', NS).text
                for note_element in note_elements
            }

        operatingprofile_element = element.find('txc:OperatingProfile', NS)
        if operatingprofile_element is not None:
            self.operating_profile = OperatingProfile(operatingprofile_element, servicedorgs)

    def add_times(self):
        row_length = len(self.journeypattern.grouping.rows.values()[0].times)

        stopusage = self.journeypattern.sections[0].timinglinks[0].origin
        time = self.departure_time
        deadrun = self.start_deadrun is not None
        if not deadrun:
            if stopusage.sequencenumber is not None:
                self.journeypattern.grouping.rows.get(stopusage.sequencenumber).times.append(time)
            else:
                stopusage.row.times.append(time)

        for section in self.journeypattern.sections:
            for timinglink in section.timinglinks:
                stopusage = timinglink.destination
                if hasattr(timinglink.origin, 'waittime'):
                    time = add_time(time, timinglink.origin.waittime)

                time = add_time(time, timinglink.runtime)

                if deadrun:
                    if self.start_deadrun == timinglink.id:
                        deadrun = False  # end of dead run
                elif stopusage.sequencenumber is not None:
                    row = self.journeypattern.grouping.rows.get(stopusage.sequencenumber)
                    row.times.append(time)
                else:
                    stopusage.row.times.append(time)

                if self.end_deadrun == timinglink.id:
                    deadrun = True  # start of dead run
                if hasattr(stopusage, 'waittime'):
                    time = add_time(time, stopusage.waittime)

        for row in self.journeypattern.grouping.rows.values():
            if len(row.times) == row_length:
                row.times.append('')

    def get_departure_time(self):
        return self.departure_time

    def get_order(self):
        if self.operating_profile:
            return self.operating_profile.get_order()
        return 0

    def should_show(self):
        if not hasattr(self, 'operating_profile'):
            return True
        if str(self.operating_profile) == 'HolidaysOnlys':
            return False
        if hasattr(self.operating_profile, 'nonoperation_days'):
            for daterange in self.operating_profile.nonoperation_days:
                if daterange.finishes_in_past() or daterange.starts_in_future():
                    return True
            return False
        return True


class ServicedOrganisation(object):
    def __init__(self, element, servicedorgs):
        # Days of non-operation:
        noop_element = element.find('txc:DaysOfNonOperation', NS)
        if noop_element:
            noop_hols_element = noop_element.find('txc:Holidays/txc:ServicedOrganisationRef', NS)
            noop_workingdays_element = noop_element.find('txc:WorkingDays/txc:ServicedOrganisationRef', NS)

            if noop_hols_element is not None:
                self.nonoperation_holidays = noop_hols_element.text

            if noop_workingdays_element is not None:
                self.nonoperation_workingdays = noop_workingdays_element.text

        # Days of operation:
        op_element = element.find('txc:DaysOfOperation', NS)
        if op_element:
            op_hols_element = op_element.find('txc:Holidays/txc:ServicedOrganisationRef', NS)
            op_workingdays_element = op_element.find('txc:WorkingDays/txc:ServicedOrganisationRef', NS)

            if op_hols_element is not None:
                self.operation_holidays = op_hols_element.text

            if op_workingdays_element is not None:
                self.operation_workingdays = op_workingdays_element.text


class OperatingProfile(object):
    def __init__(self, element, servicedorgs):
        element = element

        regular_days_element = element.find('txc:RegularDayType', NS)
        week_days_element = regular_days_element.find('txc:DaysOfWeek', NS)

        if week_days_element is None:
            self.regular_days = [e.tag[33:] for e in regular_days_element]
        else:
            self.regular_days = [e.tag[33:] for e in week_days_element]

        # Special Days:

        special_days_element = element.find('txc:SpecialDaysOperation', NS)

        if special_days_element is not None:
            nonoperation_days_element = special_days_element.find('txc:DaysOfNonOperation', NS)

            if nonoperation_days_element is not None:
                self.nonoperation_days = map(DateRange, nonoperation_days_element.findall('txc:DateRange', NS))

            operation_days_element = special_days_element.find('txc:DaysOfOperation', NS)

            if operation_days_element is not None:
                self.operation_days = map(DateRange, operation_days_element.findall('txc:DateRange', NS))

        # Serviced Organisation:

        servicedorg_days_element = element.find('txc:ServicedOrganisationDayType', NS)

        if servicedorg_days_element is not None:
            self.servicedorganisation = ServicedOrganisation(servicedorg_days_element, servicedorgs)

    def __str__(self):
        if self.regular_days:
            if len(self.regular_days) == 1:
                if 'To' in self.regular_days[0]:
                    string = self.regular_days[0].replace('To', ' to ')
                else:
                    string = self.regular_days[0] + 's'
            else:
                string = '%ss and %s' % ('s, '.join(self.regular_days[:-1]), self.regular_days[-1] + 's')

                if string == 'Mondays, Tuesdays, Wednesdays, Thursdays and Fridays':
                    string = 'Monday to Friday'
                elif string == 'Mondays, Tuesdays, Wednesdays, Thursdays, Fridays and Saturdays':
                    string = 'Monday to Saturday'
                elif string == 'Mondays, Tuesdays, Wednesdays, Thursdays, Fridays, Saturdays and Sundays':
                    string = 'Monday to Sunday'
        else:
            string = ''

        # if hasattr(self, 'nonoperation_days'):
        #     string = string + '\nNot ' + ', '.join(map(str, self.nonoperation_days))

        # if hasattr(self, 'operation_days'):
        #     string = string + '\n' + ', '.join(map(str, self.operation_days))

        if hasattr(self, 'servicedorganisation'):
            if hasattr(self.servicedorganisation, 'nonoperation_holidays'):
                string += '\nSchool days'
            if hasattr(self.servicedorganisation, 'operation_holidays'):
                string += '\nSchool holidays'
            if hasattr(self.servicedorganisation, 'nonoperation_workingdays'):
                string += '\nSchool holidays'
            if hasattr(self.servicedorganisation, 'operation_workingdays'):
                string += '\nSchool days'

        return string

    def get_order(self):
        if self.regular_days:
            if self.regular_days[0][:3] == 'Mon':
                return 0
            if self.regular_days[0][:3] == 'Sat':
                return 1
            if self.regular_days[0][:3] == 'Sun':
                return 2
            if self.regular_days[0][:3] == 'Hol':
                return 3
        return 0

    def __eq__(self, other):
        return str(self) == str(other)

    def __ne__(self, other):
        return str(self) != str(other)


class DateRange(object):
    def __init__(self, element):
        self.start = datetime.strptime(element.find('txc:StartDate', NS).text, '%Y-%m-%d').date()
        end = element.find('txc:EndDate', NS)
        self.end = datetime.strptime(end.text, '%Y-%m-%d').date() if end is not None else None

    def __str__(self):
        if self.start == self.end:
            return self.start.strftime('%-d %B %Y')
        else:
            return '%s to %s' % (str(self.start), str(self.end))

    def starts_in_future(self):
        return self.start > date.today()

    def finishes_in_past(self):
        return self.end < date.today()


class OperatingPeriod(DateRange):
    def __str__(self):
        if self.start == self.end:
            return self.start.strftime('on %-d %B %Y')
        elif self.starts_in_future():
            if self.end is None:
                return self.start.strftime('from %-d %B %Y')
            elif self.end is not None and self.start.year == self.end.year:
                if self.start.month == self.end.month:
                    start_format = '%-d'
                else:
                    start_format = '%-d %B'
            else:
                start_format = '%-d %B %Y'
            return 'from %s to %s' % (
                self.start.strftime(start_format), self.end.strftime('%-d %B %Y')
            )
        elif self.end is not None and self.end.year == date.today().year:
            return self.end.strftime('until %-d %B %Y')
        return ''


class ColumnHead(object):
    def __init__(self, operatingprofile, span):
        self.operatingprofile = operatingprofile
        self.span = span


class ColumnFoot(object):
    def __init__(self, notes, span):
        self.notes = notes
        self.span = span


class Timetable(object):
    def __get_journeys(self, xml, servicedorgs):
        journeys = {
            journey.code: journey for journey in (
                VehicleJourney(element, self.journeypatterns, servicedorgs)
                for element in xml.find('txc:VehicleJourneys', NS)
            )
        }

        # some journeys did not have a direct reference to a journeypattern,
        # but rather a reference to another journey with a reference to a journeypattern
        for journey in journeys.values():
            if hasattr(journey, 'journeyref'):
                journey.journeypattern = journeys[journey.journeyref].journeypattern

        return [journey for journey in journeys.values() if journey.should_show()]

    def __init__(self, xml):
        service_element = xml.find('txc:Services/txc:Service', NS)

        description_element = service_element.find('txc:Description', NS)
        if description_element is not None:
            if description_element.text.isupper():
                description_element.text = titlecase.titlecase(description_element.text)
            description_parts = map(sanitize_description_part, description_element.text.split(' - '))
        else:
            description_parts = None

        self.groupings = (
            Grouping('outbound', description_parts),
            Grouping('inbound', description_parts)
        )

        stops = {
            element.find('txc:StopPointRef', NS).text: Stop(element)
            for element in xml.find('txc:StopPoints', NS)
        }
        journeypatternsections = {
            element.get('id'): JourneyPatternSection(element, stops)
            for element in xml.find('txc:JourneyPatternSections', NS)
        }
        self.journeypatterns = {
            element.get('id'): JourneyPattern(element, journeypatternsections, self.groupings)
            for element in service_element.findall('txc:StandardService/txc:JourneyPattern', NS)
        }

        servicedorgs = xml.find('txc:ServicedOrganisations', NS)

        # time calculation begins here:
        journeys = self.__get_journeys(xml, servicedorgs)

        journeys.sort(key=VehicleJourney.get_departure_time)
        journeys.sort(key=VehicleJourney.get_order)
        for journey in journeys:
            journey.journeypattern.grouping.journeys.append(journey)
            journey.add_times()

        operatingprofile_element = service_element.find('txc:OperatingProfile', NS)
        if operatingprofile_element:
            self.operating_profile = OperatingProfile(operatingprofile_element, servicedorgs)

        self.operating_period = OperatingPeriod(service_element.find('txc:OperatingPeriod', NS))

        for grouping in self.groupings:
            grouping.do_heads_and_feet()


def abbreviate(grouping, i, in_a_row, difference):
    """Given a Grouping, and a timedetlta, modify each row and..."""
    grouping.rows[0].times[i - in_a_row - 2] = Cell(in_a_row + 1, len(grouping.rows), difference)
    for j in range(i - in_a_row - 1, i - 1):
        grouping.rows[0].times[j] = None
    for j in range(i - in_a_row - 2, i - 1):
        for row in grouping.rows[1:]:
            row.times[j] = None


def get_pickle_filenames(service, path):
    """Given a Service and a folder path, return a list of filenames."""
    if service.region_id == 'NE':
        return [service.pk]
    if service.region_id in ('S', 'NW'):
        return ['SVR%s' % service.pk]
    try:
        namelist = os.listdir(path)
    except OSError:
        return []
    if service.net:
        return [name for name in namelist if name.startswith('%s-' % service.pk)]
    if service.region_id == 'GB':
        parts = service.pk.split('_')
        return [name for name in namelist if name.endswith('_%s_%s' % (parts[1], parts[0]))]
    if service.region_id == 'Y':
        return [
            name for name in namelist
            if name.startswith('SVR%s-' % service.pk) or name == 'SVR%s' % service.pk
        ]
    return [name for name in namelist if name.endswith('_%s' % service.pk)]


def get_files_from_zipfile(service):
    """Given a Service,
    return an iterable of open files from the relevant zipfile.
    """
    service_code = service.service_code
    if service.region_id == 'GB':
        archive_name = 'NCSD'
        parts = service_code.split('_')
        service_code = '_%s_%s' % (parts[-1], parts[-2])
    else:
        archive_name = service.region_id
    archive_path = os.path.join(DIR, '../data/TNDS/', archive_name + '.zip')
    archive = zipfile.ZipFile(archive_path)
    filenames = (name for name in archive.namelist() if service_code in name)

    return (archive.open(filename) for filename in filenames)


def timetable_from_filename(path, filename):
    """Given a path and filename, join them, and return a Timetable."""
    if filename[-4:] == '.xml':
        with open(os.path.join(path, filename)) as xmlfile:
            xml = ET.parse(xmlfile).getroot()
        return Timetable(xml)
    cache_prefix = 'GB' if 'NCSD' in path else path.split('/')[-2]
    cache_key = '%s/%s' % (cache_prefix, filename.replace(' ', ''))
    timetable = cache.get(cache_key)
    if timetable is None:
        timetable = unpickle_timetable(os.path.join(path, filename))
        cache.set(cache_key, timetable)
    return timetable


def unpickle_timetable(filename):
    """Given a filename, try to open it and unpickle the contents."""
    try:
        with open(filename) as open_file:
            return pickle.load(open_file)
    except IOError:
        return


def timetable_from_service(service):
    """Given a Service, return a list of Timetables."""
    if service.region_id == 'GB':
        path = os.path.join(DIR, '../data/TNDS/NCSD/NCSD_TXC/')
    else:
        path = os.path.join(DIR, '../data/TNDS/%s/' % service.region_id)

    filenames = get_pickle_filenames(service, path)
    if filenames:
        timetables = filter(None, (timetable_from_filename(path, name) for name in filenames))
        if timetables:
            return timetables
    return [Timetable(ET.parse(xml_file)) for xml_file in get_files_from_zipfile(service)]
