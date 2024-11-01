import calendar
import datetime
import logging
import xml.etree.cElementTree as ET

from django.contrib.gis.geos import GEOSGeometry, LineString
from django.utils.dateparse import parse_duration

logger = logging.getLogger(__name__)


WEEKDAYS = {day: i for i, day in enumerate(calendar.day_name)}  # {'Monday:' 0,


def parse_time(string: str) -> datetime.timedelta:
    hours, minutes, seconds = string.split(":")
    return datetime.timedelta(
        hours=int(hours), minutes=int(minutes), seconds=int(seconds)
    )


class Stop:
    """A TransXChange StopPoint."""

    def __init__(self, element):
        atco_code = element.findtext("StopPointRef")
        if not atco_code:
            atco_code = element.findtext("AtcoCode", "")
        self.atco_code = atco_code.upper()

        self.common_name = element.findtext("CommonName")
        if not self.common_name:
            self.common_name = element.findtext("Descriptor/CommonName")

        self.indicator = element.findtext("Indicator")

        self.locality = element.findtext("LocalityName")

        self.element = element

    def __str__(self):
        name = self.common_name
        if not name:
            return self.atco_code
        if self.indicator:
            name = f"{name} ({self.indicator})"
        if not self.locality or self.locality in name:
            return name
        return f"{self.locality} {name}"


class Route:
    def __init__(self, element):
        self.id = element.get("id")
        self.route_section_refs = [
            section.text for section in element.findall("RouteSectionRef")
        ]


class RouteSection:
    def __init__(self, element):
        self.id = element.get("id")
        self.links = [RouteLink(link) for link in element.findall("RouteLink")]


class RouteLink:
    @staticmethod
    def get_point(element):
        lon = element.findtext("Longitude")
        if lon is not None:
            lat = element.findtext("Latitude")
            return GEOSGeometry(f"POINT({lon} {lat})")

        easting = element.findtext("Easting")
        northing = element.findtext("Northing")
        return GEOSGeometry(f"SRID=27700;POINT({easting} {northing})")

    def __init__(self, element):
        self.id = element.get("id")
        self.from_stop = element.findtext("From/StopPointRef").upper()
        self.to_stop = element.findtext("To/StopPointRef").upper()
        locations = element.findall("Track/Mapping/Location/Translation")
        if not locations:
            locations = element.findall("Track/Mapping/Location")

        locations = [self.get_point(location) for location in locations]
        self.track = LineString(*locations)
        if locations:
            self.track.srid = locations[0].srid


class JourneyPattern:
    """A collection of JourneyPatternSections, in order."""

    def __init__(self, element, sections, serviced_organisations):
        self.id = element.attrib.get("id")
        self.sections = [
            sections[section_element.text]
            for section_element in element.findall("JourneyPatternSectionRefs")
            if section_element.text in sections
        ]

        self.route_ref = element.findtext("RouteRef")
        self.direction = element.findtext("Direction")
        if (
            self.direction
            and self.direction != "inbound"
            and self.direction != "outbound"
        ):
            # clockwise/anticlockwise? Not supported, not sure if that's a problem
            self.direction = self.direction.lower()

        self.operating_profile = element.find("OperatingProfile")
        if self.operating_profile is not None:
            self.operating_profile = OperatingProfile(
                self.operating_profile, serviced_organisations
            )

    def is_inbound(self):
        return self.direction in ("inbound", "anticlockwise")

    def get_timinglinks(self):
        for section in self.sections:
            yield from section.timinglinks


class JourneyPatternSection:
    """A collection of JourneyPatternStopUsages, in order."""

    def __init__(self, element, stops):
        self.id = element.get("id")
        self.timinglinks = [
            JourneyPatternTimingLink(timinglink_element, stops)
            for timinglink_element in element
        ]


class JourneyPatternStopUsage:
    """Either a 'From' or 'To' element in TransXChange."""

    def __init__(self, element, stops):
        self.activity = element.findtext("Activity")
        self.dynamic_destination_display = element.findtext("DynamicDestinationDisplay")

        self.sequencenumber = element.get("SequenceNumber")
        if self.sequencenumber is not None:
            self.sequencenumber = int(self.sequencenumber)

        stop_ref = element.findtext("StopPointRef").upper()
        try:
            self.stop = stops[stop_ref]
        except KeyError:
            self.stop = Stop(element)

        self.timingstatus = element.findtext("TimingStatus")

        self.wait_time = element.find("WaitTime")
        if self.wait_time is not None:
            self.wait_time = parse_duration(self.wait_time.text)
            if self.wait_time.total_seconds() > 10000:
                # bad data detected
                logger.warning(f"long wait time {self.wait_time} at stop {self.stop}")

        self.notes = [
            (note_element.find("NoteCode").text, note_element.find("NoteText").text)
            for note_element in element.findall("Notes/Note")
        ]
        if self.notes:
            if self.notes == [("R", "Sets down by request to driver only")]:
                if self.activity != "setDown":
                    self.activity = "setDown"
                self.notes = []

        self.row = None
        self.parent = None


class JourneyPatternTimingLink:
    def __init__(self, element, stops):
        self.origin = JourneyPatternStopUsage(element.find("From"), stops)
        self.destination = JourneyPatternStopUsage(element.find("To"), stops)
        self.origin.parent = self.destination.parent = self
        self.runtime = parse_duration(element.find("RunTime").text)
        self.id = element.get("id")
        self.route_link_ref = element.findtext("RouteLinkRef")


def get_deadruns(journey_element):
    """Given a VehicleJourney element, return a tuple."""
    start_element = journey_element.find("StartDeadRun")
    end_element = journey_element.find("EndDeadRun")
    return (get_deadrun_ref(start_element), get_deadrun_ref(end_element))


def get_deadrun_ref(deadrun_element):
    """Given a StartDeadRun or EndDeadRun element with a ShortWorking,
    return the ID of a JourneyPetternTimingLink.
    """
    if deadrun_element is not None:
        return deadrun_element.findtext("ShortWorking/JourneyPatternTimingLinkRef")
        # ignore PositioningLinks


class VehicleJourneyTimingLink:
    def __init__(self, element):
        self.id = element.attrib.get("id")
        self.journeypatterntiminglinkref = element.find(
            "JourneyPatternTimingLinkRef"
        ).text
        self.run_time = element.findtext("RunTime")
        if self.run_time is not None:
            self.run_time = parse_duration(self.run_time)

        self.from_wait_time = element.findtext("From/WaitTime")
        if self.from_wait_time is not None:
            self.from_wait_time = parse_duration(self.from_wait_time)

        self.to_wait_time = element.findtext("To/WaitTime")
        if self.to_wait_time is not None:
            self.to_wait_time = parse_duration(self.to_wait_time)

        self.from_activity = element.findtext("From/Activity")
        self.to_activity = element.findtext("To/Activity")

        self.notes = [
            (note_element.find("NoteCode").text, note_element.find("NoteText").text)
            for note_element in element.findall("Notes/Note")
        ]
        assert not self.notes


class VehicleType:
    def __init__(self, element):
        self.code = element.findtext("VehicleTypeCode")
        self.description = element.findtext("Description")


class Block:
    def __init__(self, element):
        self.code = element.findtext("BlockNumber")
        self.description = element.findtext("Description")


class VehicleJourney:
    """A scheduled journey that happens at most once per day"""

    def __str__(self):
        return str(self.departure_time)

    def __init__(self, element, services, serviced_organisations):
        self.code = element.find("VehicleJourneyCode").text
        self.private_code = element.findtext("PrivateCode")

        self.ticket_machine_journey_code = element.findtext(
            "Operational/TicketMachine/JourneyCode"
        )
        self.ticket_machine_service_code = element.findtext(
            "Operational/TicketMachine/TicketMachineServiceCode"
        )

        self.block = element.find("Operational/Block")
        if self.block is not None:
            self.block = Block(self.block)
        self.vehicle_type = element.find("Operational/VehicleType")
        if self.vehicle_type is not None:
            self.vehicle_type = VehicleType(self.vehicle_type)

        self.garage_ref = element.findtext("GarageRef")

        self.service_ref = element.find("ServiceRef").text.strip()
        self.line_ref = element.find("LineRef").text

        journeypatternref_element = element.find("JourneyPatternRef")
        if journeypatternref_element is not None:
            self.journey_ref = None
            self.journey_pattern = services[self.service_ref].journey_patterns.get(
                journeypatternref_element.text
            )
        else:
            # Journey has no direct reference to a JourneyPattern.
            # Instead, it has a reference to another journey...
            self.journey_ref = element.findtext("VehicleJourneyRef")
            self.journey_pattern = None

        self.operating_profile = element.find("OperatingProfile")
        if self.operating_profile is not None:
            self.operating_profile = OperatingProfile(
                self.operating_profile, serviced_organisations
            )

        self.departure_time = parse_time(element.findtext("DepartureTime"))
        departure_day_shift = element.findtext("DepartureDayShift")
        if departure_day_shift:
            departure_day_shift = int(departure_day_shift)
            if (
                self.departure_time > datetime.timedelta(hours=12)
                or departure_day_shift > 1
            ):
                logger.error(f"{self.departure_time=}, ignoring {departure_day_shift=}")
            else:
                self.departure_time += datetime.timedelta(days=departure_day_shift)

        self.start_deadrun, self.end_deadrun = get_deadruns(element)

        self.operator = element.findtext("OperatorRef")

        sequencenumber = element.get("SequenceNumber")
        self.sequencenumber = sequencenumber and int(sequencenumber)

        timing_links = element.findall("VehicleJourneyTimingLink")
        self.timing_links = [
            VehicleJourneyTimingLink(timing_link) for timing_link in timing_links
        ]

        note_elements = element.findall("Note")
        if note_elements is not None:
            self.notes = {
                note_element.find("NoteCode").text: note_element.find("NoteText").text
                for note_element in note_elements
            }

        self.frequency_interval = None
        frequency = element.find("Frequency")
        if frequency is not None:
            interval = frequency.find("Interval")
            if interval is not None:
                self.frequency_interval = parse_duration(
                    interval.findtext("ScheduledFrequency")
                )
            self.frequency_end_time = parse_time(frequency.findtext("EndTime"))

    def get_timinglinks(self):
        pattern_links = self.journey_pattern.get_timinglinks()
        journey_links = {
            link.journeypatterntiminglinkref: link for link in self.timing_links
        }
        for link in pattern_links:
            yield link, journey_links.get(link.id)

    def get_times(self):
        stopusage = None
        prev_activity = None
        time = self.departure_time
        deadrun = self.start_deadrun is not None
        deadrun_next = False
        wait_time = None
        for timinglink, journey_timinglink in self.get_timinglinks():
            if journey_timinglink and journey_timinglink.from_activity:
                activity = journey_timinglink.from_activity
            else:
                activity = timinglink.origin.activity

            if stopusage and prev_activity != activity:
                # assume "pickUp" + "setDown" = "pickUpAndSetDown" = None
                activity = None

            # <From>
            stopusage = timinglink.origin

            if deadrun and self.start_deadrun == timinglink.id:
                deadrun = False  # end of dead run

            if not deadrun:
                if journey_timinglink and journey_timinglink.from_wait_time is not None:
                    wait_time = journey_timinglink.from_wait_time
                elif stopusage.wait_time is not None:
                    wait_time = stopusage.wait_time

                notes = (
                    journey_timinglink and journey_timinglink.notes or stopusage.notes
                )

                if wait_time:
                    next_time = time + wait_time
                    yield Cell(stopusage, time, next_time, activity, notes)
                    time = next_time
                else:
                    yield Cell(stopusage, time, time, activity, notes)

                if journey_timinglink and journey_timinglink.run_time is not None:
                    run_time = journey_timinglink.run_time
                else:
                    run_time = timinglink.runtime
                if run_time:
                    time += run_time

            if deadrun_next:
                deadrun = True
                deadrun_next = False
            elif self.end_deadrun == timinglink.id:
                deadrun_next = True  # start of dead run

            # <To>
            stopusage = timinglink.destination

            if not deadrun:
                if journey_timinglink and journey_timinglink.to_wait_time is not None:
                    wait_time = journey_timinglink.to_wait_time
                else:
                    wait_time = stopusage.wait_time

            if journey_timinglink and journey_timinglink.to_activity:
                prev_activity = journey_timinglink.to_activity
            else:
                prev_activity = stopusage.activity

        if not deadrun:
            notes = None
            if journey_timinglink and journey_timinglink.notes:
                notes = journey_timinglink.notes
            else:
                notes = stopusage.notes

            yield Cell(stopusage, time, time, prev_activity, notes)


class ServicedOrganisation:
    """Like a school, college, or workplace"""

    def __init__(self, element):
        self.code = element.find("OrganisationCode").text
        self.name = element.findtext("Name")

        working_days = element.findall("WorkingDays/DateRange")
        self.working_days = [DateRange(e) for e in working_days if len(e)]

        holidays = element.findall("Holidays/DateRange")
        self.holidays = [DateRange(e) for e in holidays if len(e)]

        self.hash = ET.tostring(element)

    def __str__(self):
        return self.name or self.code


class ServicedOrganisationDayType:
    def __init__(
        self, serviced_organisations: dict, ref: str, operation: bool, working: bool
    ):
        self.ref = ref
        self.operation = (
            operation  # True (DaysOfOperation) or False (DaysOfNonOperation)
        )
        self.working = working  # True (WorkingDays) or False (Holidays)
        self.serviced_organisation = serviced_organisations[ref]

    def __repr__(self):
        """
        It is recommended, however, that any presentation to the user avoids
        negative descriptions such as “this trip does not operate on the
        working days of X” but presents it instead with a positive
        description such as “this trip operates during holidays of X.”
        """

        if self.operation == self.working:  # "working days" or "not holidays"
            return f"{self.serviced_organisation} days"

        # "not working days" or "holidays"
        return f"{self.serviced_organisation} holidays"


class DayOfWeek:
    def __init__(self, day):
        if isinstance(day, int):
            self.day = day
        else:
            self.day = WEEKDAYS[day]

    def __eq__(self, other):
        if isinstance(other, int):
            return self.day == other
        return self.day == other.day

    def __repr__(self):
        return calendar.day_name[self.day]


class OperatingProfile:
    serviced_organisations = None

    def __init__(self, element, serviced_organisations: dict):
        element = element

        week_days = element.find("RegularDayType/DaysOfWeek")
        self.regular_days = []
        if week_days is not None:
            week_days = [e.tag for e in week_days]
            for day in week_days:
                if "To" in day:
                    day_range_bounds = [WEEKDAYS[i] for i in day.split("To")]
                    day_range = range(day_range_bounds[0], day_range_bounds[1] + 1)
                    self.regular_days += [DayOfWeek(i) for i in day_range]
                elif day == "Weekend":
                    self.regular_days += [DayOfWeek(5), DayOfWeek(6)]
                elif day[:3] == "Not":
                    self.regular_days += [
                        DayOfWeek(WEEKDAYS[key]) for key in WEEKDAYS if key != day[3:]
                    ]
                else:
                    self.regular_days.append(DayOfWeek(day))

        self.week_of_month = None
        periodic_day_type = element.find("PeriodicDayType")
        if periodic_day_type is not None:
            logger.info(ET.tostring(periodic_day_type).decode())
            self.week_of_month = periodic_day_type.findtext("WeekOfMonth/WeekNumber")
        # Special Days:

        nonoperation_days = element.findall(
            "SpecialDaysOperation/DaysOfNonOperation/DateRange"
        )
        self.nonoperation_days = [DateRange(e) for e in nonoperation_days if len(e)]

        operation_days = element.findall(
            "SpecialDaysOperation/DaysOfOperation/DateRange"
        )
        self.operation_days = [DateRange(e) for e in operation_days if len(e)]

        # Serviced Organisation:

        self.serviced_organisations = []

        if (
            serviced_organisations
            and (sodt := element.find("ServicedOrganisationDayType")) is not None
        ):
            for path, operation, working in (
                ("DaysOfOperation/Holidays/ServicedOrganisationRef", True, False),
                ("DaysOfOperation/WorkingDays/ServicedOrganisationRef", True, True),
                ("DaysOfNonOperation/Holidays/ServicedOrganisationRef", False, False),
                ("DaysOfNonOperation/WorkingDays/ServicedOrganisationRef", False, True),
            ):
                for e in sodt.findall(path):
                    self.serviced_organisations.append(
                        ServicedOrganisationDayType(
                            serviced_organisations, e.text, operation, working
                        )
                    )

        # Bank Holidays:

        self.operation_bank_holidays = element.find(
            "BankHolidayOperation/DaysOfOperation"
        )
        self.nonoperation_bank_holidays = element.find(
            "BankHolidayOperation/DaysOfNonOperation"
        )

        if self.operation_bank_holidays is None:
            if element.find("RegularDayType/HolidaysOnly") is not None:
                self.operation_bank_holidays = element.find("RegularDayType")

        self.hash = ET.tostring(element)
        if serviced_organisations:
            for organisation in serviced_organisations.values():
                self.hash += organisation.hash


class DateRange:
    def __init__(self, element):
        self.start = element.findtext("StartDate")
        self.end = element.findtext("EndDate")
        if self.start:
            self.start = datetime.date.fromisoformat(self.start.strip())
        if self.end:
            self.end = datetime.date.fromisoformat(self.end.strip())
        self.note = element.findtext("Note", "")
        self.description = element.findtext("Description", "")

    def __str__(self):
        if self.start == self.end:
            return str(self.start)
        return f"{self.start} to {self.end}"

    def contains(self, date):
        return self.start <= date and (not self.end or self.end >= date)


class Service:
    def __init__(self, element, serviced_organisations, journey_pattern_sections):
        self.mode = element.findtext("Mode", "")

        self.operator = element.findtext("RegisteredOperatorRef")

        self.operating_profile = element.find("OperatingProfile")
        if self.operating_profile is not None:
            self.operating_profile = OperatingProfile(
                self.operating_profile, serviced_organisations
            )

        self.operating_period = DateRange(element.find("OperatingPeriod"))

        self.public_use = element.findtext("PublicUse")

        self.service_code = element.find("ServiceCode").text.strip()

        self.marketing_name = element.findtext("MarketingName")

        self.description = element.findtext("Description")
        if self.description:
            self.description = self.description.strip()

        self.origin = element.findtext("StandardService/Origin")
        if self.origin:
            self.origin = self.origin.replace("`", "'").strip()

        self.destination = element.findtext("StandardService/Destination")
        if self.destination:
            self.destination = self.destination.replace("`", "'").strip()

        self.vias = element.find("StandardService/Vias")
        if self.vias is not None:
            self.vias = [via.text for via in self.vias]

        self.journey_patterns = {
            journey_pattern.id: journey_pattern
            for journey_pattern in (
                JourneyPattern(
                    journey_pattern, journey_pattern_sections, serviced_organisations
                )
                for journey_pattern in element.findall("StandardService/JourneyPattern")
            )
            if journey_pattern.sections
        }

        self.lines = [Line(line_element) for line_element in element.find("Lines")]

        self.to_be_marketed_with = [
            d.text
            for d in element.findall("ToBeMarketedWith/RelatedService/Description")
        ]
        self.associated_operators = [
            d.text for d in element.findall("AssociatedOperators/OperatorRef")
        ]

        self.ticket_machine_service_code = element.findtext("TicketMachineServiceCode")
        self.commercial_basis = element.findtext("CommercialBasis")

        self.notes = [
            (note_element.find("NoteCode").text, note_element.find("NoteText").text)
            for note_element in element.findall("Note")
        ]
        assert not self.notes


class Line:
    def __init__(self, element):
        self.id = element.attrib["id"]
        line_name = element.findtext("LineName") or ""
        if "|" in line_name:
            line_name, line_brand = line_name.split("|", 1)
            self.line_brand = line_brand.strip()
        else:
            self.line_brand = ""
        self.line_name = line_name.strip()

        self.marketing_name = element.findtext("MarketingName")

        if (
            element.findtext("LineColour")
            or element.findtext("LineFontColour")
            or element.findtext("LineImage")
        ):
            logger.info(ET.tostring(element).decode())

        self.outbound_description = element.findtext("OutboundDescription/Description")
        self.inbound_description = element.findtext("InboundDescription/Description")


class TransXChange:
    def get_journeys(self, service_code, line_id):
        return [
            journey
            for journey in self.journeys
            if journey.service_ref == service_code and journey.line_ref == line_id
        ]

    def __get_journeys(self, journeys_element, serviced_organisations):
        journeys = {
            journey.code: journey
            for journey in (
                VehicleJourney(element, self.services, serviced_organisations)
                for element in journeys_element
            )
        }

        # Some Journeys do not have a direct reference to a JourneyPattern,
        # but rather a reference to another Journey which has a reference to a JourneyPattern
        for journey in iter(journeys.values()):
            if journey.journey_ref:
                referenced_journey = journeys[journey.journey_ref]
                if journey.journey_pattern is None:
                    journey.journey_pattern = referenced_journey.journey_pattern
                if journey.operating_profile is None:
                    journey.operating_profile = referenced_journey.operating_profile

        return [journey for journey in journeys.values() if journey.journey_pattern]

    def __init__(self, open_file):
        iterator = ET.iterparse(open_file)

        self.services = {}
        self.stops = {}
        self.routes = {}
        self.route_sections = {}
        self.journeys = []
        self.garages = {}

        serviced_organisations = None

        journey_pattern_sections = {}

        for _, element in iterator:
            if element.tag[:33] == "{http://www.transxchange.org.uk/}":
                element.tag = element.tag[33:]
            tag = element.tag

            if tag == "StopPoints":
                for stop_element in element:
                    stop = Stop(stop_element)
                    self.stops[stop.atco_code] = stop
                element.clear()
            elif tag == "RouteSections":
                for section_element in element:
                    section = RouteSection(section_element)
                    self.route_sections[section.id] = section
                element.clear()
            elif tag == "Routes":
                for route_element in element:
                    route = Route(route_element)
                    self.routes[route.id] = route
                element.clear()
            elif tag == "Operators":
                self.operators = element
            elif tag == "JourneyPatternSections":
                for section in element:
                    section = JourneyPatternSection(section, self.stops)
                    if section.timinglinks:
                        journey_pattern_sections[section.id] = section
                element.clear()
            elif tag == "ServicedOrganisations":
                serviced_organisations = (
                    ServicedOrganisation(child) for child in element
                )
                serviced_organisations = {
                    organisation.code: organisation
                    for organisation in serviced_organisations
                }
            elif tag == "VehicleJourneys":
                try:
                    self.journeys = self.__get_journeys(element, serviced_organisations)
                except (AttributeError, KeyError) as e:
                    logger.exception(e)
                    return
                element.clear()
            elif tag == "Service":
                service = Service(
                    element, serviced_organisations, journey_pattern_sections
                )
                self.services[service.service_code] = service
            elif tag == "Garages":
                for garage_element in element:
                    self.garages[garage_element.findtext("GarageCode")] = garage_element
                element.clear()

        self.attributes = element.attrib


class Cell:
    last = False

    def __init__(self, stopusage, arrival_time, departure_time, activity, notes):
        self.stopusage = stopusage
        self.arrival_time = arrival_time
        self.departure_time = departure_time
        if (
            arrival_time is not None
            and departure_time is not None
            and arrival_time != departure_time
        ):
            self.wait_time = True
        else:
            self.wait_time = None

        self.activity = activity
        self.notes = notes
