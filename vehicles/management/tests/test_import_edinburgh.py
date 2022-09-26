from django.test import TestCase

from busstops.models import DataSource, Operator, Region, Service

from ..commands.import_edinburgh import Command


class EdinburghImportTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        source = DataSource.objects.create(
            name="TfE", url="", datetime="1066-01-01 12:18Z"
        )
        Region.objects.create(name="Scotland", id="S")
        cls.operator_1 = Operator.objects.create(
            name="Lothian Buses", noc="LOTH", region_id="S"
        )
        cls.operator_2 = Operator.objects.create(
            name="Edinburgh Trams", noc="EDTR", region_id="S"
        )
        cls.service = Service.objects.create(line_name="11", current=True)
        cls.service.operator.add(cls.operator_2)
        cls.source = source

    def test_get_journey(self):
        command = Command()
        command.source = self.source

        item = {
            "journey_id": "1135",
            "vehicle_id": "3032",
            "destination": "Yoker",
            "service_name": "11",
            "heading": 76,
            "latitude": 55.95376,
            "longitude": -3.18718,
            "last_gps_fix": 1554038242,
            "ineo_gps_fix": 1554038242,
        }
        with self.assertNumQueries(11):
            command.handle_item(item)
            command.save()
        with self.assertNumQueries(1):
            command.handle_item(item)
            command.save()
        journey = command.source.vehiclejourney_set.get()

        self.assertEqual("1135", journey.code)
        self.assertEqual("Yoker", journey.destination)
        self.assertEqual(self.service, journey.service)
        self.assertTrue(journey.service.tracking)

        with self.assertNumQueries(1):
            vehicle, created = command.get_vehicle(item)
        self.assertEqual(self.operator_2, vehicle.operator)
        self.assertEqual(3032, vehicle.fleet_number)
        self.assertFalse(created)

        item["last_gps_fix"] += 200
        with self.assertNumQueries(1):
            command.handle_item(item)
            command.save()

    def test_vehicle_location(self):
        command = Command()
        command.source = self.source

        item = {
            "vehicle_id": "3030",
            "heading": 76,
            "latitude": 55.95376,
            "longitude": -3.18718,
            "last_gps_fix": 1554034642,
            "ineo_gps_fix": 1554038242,
        }
        location = command.create_vehicle_location(item)
        self.assertEqual(76, location.heading)
        self.assertTrue(location.latlong)

        self.assertEqual("2019-03-31 12:17:22+00:00", str(command.get_datetime(item)))
