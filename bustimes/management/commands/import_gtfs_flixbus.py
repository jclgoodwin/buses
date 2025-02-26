import logging
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd
from shapely.errors import EmptyPartError
import gtfs_kit
from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Min
from django.utils.dateparse import parse_duration

from busstops.models import DataSource, Operator, Service, StopPoint

from ...download_utils import download_if_modified
from ...models import Route, StopTime, Trip
from .import_gtfs_ember import get_calendars

logger = logging.getLogger(__name__)


def get_stoppoint(stop, source):
    stoppoint = StopPoint(
        atco_code=stop.stop_id,
        naptan_code=stop.stop_code,
        common_name=stop.stop_name,
        active=True,
        source=source,
        latlong=f"POINT({stop.stop_lon} {stop.stop_lat})",
    )

    if len(stoppoint.common_name) > 48:
        if " (" in stoppoint.common_name and stoppoint.common_name[-1] == ")":
            stoppoint.common_name, stoppoint.indicator = stoppoint.common_name.split(
                " (", 1
            )
        stoppoint.indicator = stoppoint.indicator[:-1]

    return stoppoint


class Command(BaseCommand):
    def handle(self, *args, **options):
        operator = Operator.objects.get(name="FlixBus")
        source = DataSource.objects.get(name="FlixBus")

        path = settings.DATA_DIR / Path("flixbus_eu.zip")

        source.url = "https://gtfs.gis.flix.tech/gtfs_generic_eu.zip"

        modified, last_modified = download_if_modified(path, source)

        if not modified:
            return

        feed = gtfs_kit.read_feed(path, dist_units="km")

        feed = feed.restrict_to_routes(
            feed.routes[feed.routes.route_id.str.startswith("UK")].route_id
            feed.routes[feed.routes.route_long_name.str.startswith("London")].route_long_name
            feed.routes[feed.routes.route_long_name.str.endswith("London")].route_long_name
        )

        stops_data = {row.stop_id: row for row in feed.stops.itertuples()}
        stop_codes = {
            stop_code.code: stop_code.stop_id for stop_code in source.stopcode_set.all()
        }
        missing_stops = {}

        existing_services = {
            service.line_name: service for service in operator.service_set.all()
        }
        existing_routes = {route.code: route for route in source.route_set.all()}
        routes = []

        calendars = get_calendars(feed, source)

        # get UTC offset (0 or 1 hours) at midday at the start of each calendar
        # (the data uses UTC times but we want local times)
        tzinfo = ZoneInfo("Europe/London")
        utc_offsets = {
            calendar.start_date: datetime.strptime(
                f"{calendar.start_date} 12", "%Y%m%d %H"
            )
            .replace(tzinfo=tzinfo)
            .utcoffset()
            for calendar in calendars.values()
        }

        geometries = {}
        try:
            for row in gtfs_kit.routes.get_routes(feed, as_gdf=True).itertuples():
                if row.geometry:
                    print(row.geometry, row.geometry.wkt)
                    geometries[row.route_id] = row.geometry.wkt
        except EmptyPartError:
            pass

        for row in feed.routes.itertuples():
            line_name = row.route_id.removeprefix("UK")

            if line_name in existing_services:
                service = existing_services[line_name]
            else:
                service = Service(line_name=line_name, source=source)

            if row.route_id in existing_routes:
                route = existing_routes[row.route_id]
            else:
                route = Route(code=row.route_id, source=source)
            route.service = service
            route.line_name = line_name
            service.description = route.description = row.route_long_name
            service.current = True
            service.colour_id = operator.colour_id
            service.source = source
            service.geometry = geometries.get(row.route_id)
            service.region_id = "GB"

            service.save()
            service.operator.add(operator)
            route.save()

            routes.append(route)

            existing_routes[route.code] = route  # deals with duplicate rows

        existing_trips = {
            trip.vehicle_journey_code: trip for trip in operator.trip_set.all()
        }
        trips = {}
        for row in feed.trips.itertuples():
            trip = Trip(
                route=existing_routes[row.route_id],
                calendar=calendars[row.service_id],
                inbound=row.direction_id == 1,
                vehicle_journey_code=row.trip_id,
                operator=operator,
            )
            if trip.vehicle_journey_code in existing_trips:
                # reuse existing trip id
                trip.id = existing_trips[trip.vehicle_journey_code].id
            trips[trip.vehicle_journey_code] = trip
        del existing_trips

        stop_times = []
        for row in feed.stop_times.itertuples():
            trip = trips[row.trip_id]
            offset = utc_offsets[trip.calendar.start_date]

            arrival_time = parse_duration(row.arrival_time) + offset
            departure_time = parse_duration(row.departure_time) + offset

            if not trip.start:
                trip.start = arrival_time
            trip.end = departure_time

            stop_time = StopTime(
                arrival=arrival_time,
                departure=departure_time,
                sequence=row.stop_sequence,
                trip=trip,
            )
            if pd.notna(row.timepoint) and row.timepoint == 1:
                stop_time.timing_status = "PTP"
            else:
                stop_time.timing_status = "OTH"

            if row.stop_id in stop_codes:
                stop_time.stop_id = stop_codes[row.stop_id]
            else:
                stop = stops_data[row.stop_id]
                stop_time.stop_id = row.stop_id

                if row.stop_id not in missing_stops:
                    missing_stops[row.stop_id] = get_stoppoint(stop, source)

                    logger.info(
                        f"{stop.stop_name} {stop.stop_code} {stop.stop_timezone} {stop.platform_code}"
                    )
                    logger.info(
                        f"https://bustimes.org/map#16/{stop.stop_lat}/{stop.stop_lon}"
                    )
                    logger.info(
                        f"https://bustimes.org/admin/busstops/stopcode/add/?code={row.stop_id}\n"
                    )

            trip.destination_id = stop_time.stop_id

            stop_times.append(stop_time)
        StopPoint.objects.bulk_create(
            missing_stops.values(),
            update_conflicts=True,
            update_fields=["common_name", "indicator", "naptan_code", "latlong"],
            unique_fields=["atco_code"],
        )

        # if no timing points specified (FlixBus), set all stops as timing points
        if all(stop_time.timing_status == "OTH" for stop_time in stop_times):
            for stop_time in stop_times:
                stop_time.timing_status = "PTP"

        with transaction.atomic():
            Trip.objects.bulk_create([trip for trip in trips.values() if not trip.id])
            existing_trips = [trip for trip in trips.values() if trip.id]
            Trip.objects.bulk_update(
                existing_trips,
                fields=[
                    "route",
                    "calendar",
                    "inbound",
                    "start",
                    "end",
                    "destination",
                    "block",
                    "vehicle_journey_code",
                ],
            )

            StopTime.objects.filter(trip__in=existing_trips).delete()
            StopTime.objects.bulk_create(stop_times)

            for service in source.service_set.filter(current=True):
                service.do_stop_usages()
                service.update_search_vector()

            print(
                source.route_set.exclude(id__in=[route.id for route in routes]).delete()
            )

            for route in source.route_set.annotate(
                start=Min("trip__calendar__start_date")
            ):
                route.start_date = route.start
                route.save(update_fields=["start_date"])

            print(
                operator.trip_set.exclude(
                    id__in=[trip.id for trip in trips.values()]
                ).delete()
            )
            print(
                operator.service_set.filter(current=True, route__isnull=True).update(
                    current=False
                )
            )
            if last_modified:
                source.datetime = last_modified
                source.save(update_fields=["datetime"])
