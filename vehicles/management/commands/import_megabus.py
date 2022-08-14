import functools
import json
import ciso8601
from datetime import timedelta
from time import sleep
from requests import RequestException
from django.contrib.gis.geos import Point
from django.core.serializers.json import DjangoJSONEncoder
from busstops.models import Service
from .import_nx import Command as NatExpCommand, parse_datetime
from ...models import VehicleJourney, VehicleLocation
from ...utils import redis_client


class Command(NatExpCommand):
    source_name = "Megabus"
    url = ""
    operators = ["MEGA", "SCLK", "SCUL"]
    sleep = 10
    livery = 910

    def get_line_names(self):
        if self.source_name == "Megabus":
            yield "FALC"
        for line_name in super().get_line_names():
            if line_name != "783":
                yield line_name

    def get_items(self):
        for line_name in self.get_line_names():
            line_name = line_name.upper()
            try:
                res = self.session.get(self.source.url.format(line_name), timeout=5)
            except RequestException as e:
                print(e)
                continue
            if not res.ok:
                print(res.url, res)
                continue
            for item in res.json()["routes"][0]["chronological_departures"]:
                if item["active_vehicle"] and not item["tracking"]["is_future_trip"]:
                    yield (item)
            self.save()
            sleep(self.sleep)

    @functools.cache
    def get_service(self, line_name, class_code):
        operators = self.operators

        if class_code == "FALC":
            operators = ["SDVN"]

        services = Service.objects.filter(
            line_name__iexact=line_name, operator__in=operators, current=True
        )
        try:
            service = services.get()
        except Service.MultipleObjectsReturned:
            service = self.operators
            if class_code == "ST":
                service = services.get(operator="MEGA")
            elif class_code == "C":
                service = services.get(operator__in=["SCLK", "SCUL"])
        except Service.DoesNotExist:
            return

        if not service.tracking:
            service.tracking = True
            service.save(update_fields=["tracking"])
        return service

    @functools.lru_cache
    def get_journey(self, route_name, service, departure_time, destination):
        journey = VehicleJourney.objects.filter(
            service=service,
            datetime=departure_time,
            destination=destination,
            vehicle=None,
            source=self.source,
        ).first()
        if not journey:
            journey = VehicleJourney(
                route_name=route_name,
                service=service,
                datetime=departure_time,
                destination=destination,
                source=self.source,
            )
            journey.trip = journey.get_trip(departure_time=departure_time)
            journey.save()
        return journey

    def handle_item(self, item, now):
        route_name = item["trip"]["route_id"]
        service = self.get_service(item["trip"]["route_id"], item["trip"]["class_code"])
        departure_time = parse_datetime(item["trip"]["departure_time_formatted_local"])
        destination = item["trip"]["arrival_location_name"]

        journey = self.get_journey(route_name, service, departure_time, destination)

        updated_at = parse_datetime(
            item["active_vehicle"]["last_update_time_formatted_local"]
        )

        latest = redis_client.get(f"vehicle{journey.id}")
        if latest:
            latest = json.loads(latest)
            latest_datetime = ciso8601.parse_datetime(latest["datetime"])
            if latest_datetime >= updated_at:
                return

        if (now - updated_at).total_seconds() > 600:
            return

        delay = item["tracking"]["current_delay_seconds"]
        location = VehicleLocation(
            latlong=Point(
                item["active_vehicle"]["current_wgs84_longitude_degrees"],
                item["active_vehicle"]["current_wgs84_latitude_degrees"],
            ),
            heading=item["active_vehicle"]["current_forward_azimuth_degrees"],
            early=-timedelta(seconds=delay) if delay is not None else None,
        )
        location.datetime = updated_at
        location.journey = journey
        location.id = journey.id
        pipeline = redis_client.pipeline(transaction=False)

        pipeline.rpush(*location.get_appendage())

        pipeline.geoadd(
            "vehicle_location_locations",
            [location.latlong.x, location.latlong.y, journey.id],
        )
        pipeline.sadd(f"service{journey.service_id}vehicles", journey.id)
        redis_json = location.get_redis_json()

        redis_json["vehicle"] = {
            "name": item["trip"]["operator_name"],
        }

        if item["trip"]["class_code"] == "DE":
            livery = 2455
        else:
            match item["trip"]["class_code"]:
                case "C" | "SCUL":
                    livery = 896
                case "FALC":
                    livery = 583
                case _:
                    livery = self.livery
            redis_json["vehicle"]["livery"] = livery

        if service:
            redis_json["service"]["url"] = service.get_absolute_url()
        redis_json = json.dumps(redis_json, cls=DjangoJSONEncoder)
        pipeline.set(f"vehicle{journey.id}", redis_json, ex=900)

        pipeline.execute()
