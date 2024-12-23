from django.core.exceptions import ValidationError
from django.test import TestCase

from .models import Livery, Vehicle


class VehicleModelTests(TestCase):
    def test_vehicle(self):
        vehicle = Vehicle(reg="3990ME")
        self.assertEqual(str(vehicle), "3990 ME")
        self.assertIn(
            "search/?text=3990ME%20or%20%223990%20ME%22&sort", vehicle.get_flickr_url()
        )

        vehicle.reg = "HC6422"
        self.assertEqual(str(vehicle), "HC 6422")

        vehicle.reg = "J122018"
        self.assertEqual(str(vehicle), "J122018")

        vehicle = Vehicle(code="RML2604")
        self.assertIsNone(vehicle.get_flickr_url())
        self.assertEqual("", vehicle.get_flickr_link())

    def test_vehicle_validation(self):
        vehicle = Vehicle(colours="ploop")
        with self.assertRaises(ValidationError):
            vehicle.clean()

        vehicle.colours = ""
        vehicle.clean()

    def test_livery(self):
        livery = Livery(name="Go-Coach", published=False)
        livery.text_colour = "#c0c0c0"
        livery.stroke_colour = "#ffee99"
        self.assertEqual("Go-Coach", str(livery))
        self.assertIsNone(livery.preview())
        self.assertEqual(
            '<div style="height:1.5em;width:2.25em;background:"></div> Go-Coach',
            livery.preview(name=True),
        )

        livery.colours = "#7D287D #FDEE00 #FDEE00"
        livery.horizontal = True
        livery.save()
        self.assertEqual(
            '<div style="height:1.5em;width:2.25em;background:linear-gradient'
            + '(#fdee00 66%,#7d287d 66%)" title="Go-Coach"></div>',
            livery.preview(),
        )
        self.assertEqual(
            livery.get_styles(),
            [
                f""".livery-{livery.id} {{
  background: linear-gradient(#fdee00 66%,#7d287d 66%);
  color:#c0c0c0;fill:#c0c0c0;stroke:#ffee99\n}}\n"""
            ],
        )

        livery.horizontal = False
        livery.angle = 45
        livery.save()
        self.assertEqual(
            "linear-gradient(45deg,#7d287d 34%,#fdee00 34%)", livery.left_css.lower()
        )
        self.assertEqual(
            "linear-gradient(315deg,#7d287d 34%,#fdee00 34%)", livery.right_css.lower()
        )

        livery.angle = None
        livery.save()

        vehicle = Vehicle(livery=livery)
        self.assertEqual(
            "linear-gradient(270deg,#7d287d 34%,#fdee00 34%)",
            vehicle.get_livery(179).lower(),
        )
        self.assertIsNone(vehicle.get_text_colour())

        vehicle.livery.colours = "#c0c0c0"
        vehicle.livery.save()
        self.assertEqual("silver", vehicle.get_livery(200))
        # self.assertEqual("#c0c0c0", vehicle.get_livery(200))

        livery.css = "linear-gradient(45deg,#ed1b23 35%,#fff 35%,#fff 45%,#ed1b23 45%)"
        livery.set_css()
        self.assertEqual(
            livery.left_css,
            "linear-gradient(45deg,#ed1b23 35%,#fff 35%,#fff 45%,#ed1b23 45%)",
        )
        self.assertEqual(
            livery.right_css,
            "linear-gradient(315deg,#ed1b23 35%,#fff 35%,#fff 45%,#ed1b23 45%)",
        )

    def test_livery_validation(self):
        livery = Livery()

        livery.clean()  # should not raise an exception

        livery.text_colour = "#c0c0c0"
        livery.stroke_colour = "#ff00a9"
        livery.right_css = "{"
        with self.assertRaises(ValidationError) as cm:
            livery.clean()
        self.assertEqual(
            cm.exception.args, ({"right_css": "Must not contain { or }"}, None, None)
        )

        livery.right_css = ""
        livery.left_css = "url(("
        with self.assertRaises(ValidationError) as cm:
            livery.clean()
        self.assertEqual(
            cm.exception.args,
            ({"left_css": "Must contain equal numbers of ( and )"}, None, None),
        )

        livery.left_css = ""
        livery.stroke_colour = "red"
        with self.assertRaises(ValidationError) as cm:
            livery.clean()
        self.assertEqual(
            cm.exception.args,
            (
                {
                    "stroke_colour": "An HTML5 simple color must be a Unicode string "
                    "seven characters long."
                },
                None,
                None,
            ),
        )
