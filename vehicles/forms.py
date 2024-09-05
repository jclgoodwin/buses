from django import forms
from django.conf import settings
from django.contrib.admin.widgets import AutocompleteSelect
from django.core.exceptions import ValidationError

from busstops.models import Operator

from . import fields
from .models import Livery, Vehicle, VehicleFeature, VehicleType, get_text_colour


class AutcompleteWidget(forms.Select):
    optgroups = AutocompleteSelect.optgroups

    def __init__(self, field=None, attrs=None, choices=(), using=None):
        self.field = field
        self.attrs = {} if attrs is None else attrs.copy()
        self.choices = choices
        self.db = None


class EditVehicleForm(forms.Form):
    @property
    def media(self):
        return forms.Media(
            js=(
                "admin/js/vendor/jquery/jquery.min.js",
                "admin/js/vendor/select2/select2.full.min.js",
                "js/edit-vehicle.js",
            ),
            css={
                "screen": ("admin/css/vendor/select2/select2.min.css",),
            },
        )

    field_order = [
        "spare_ticket_machine",
        "withdrawn",
        "fleet_number",
        "reg",
        "operator",
        "vehicle_type",
        "colours",
        "other_colour",
        "branding",
        "name",
        "previous_reg",
        "features",
        "notes",
        "rules",
    ]
    spare_ticket_machine = forms.BooleanField(
        required=False,
        help_text="Only to be used if the ticket machine code is something like SPARE",
    )
    withdrawn = forms.BooleanField(
        label="Remove from list",
        required=False,
        help_text="""Don't feel you need to "tidy up" by removing vehicles you only *think* have been withdrawn""",
    )

    fleet_number = forms.CharField(required=False, max_length=24)
    reg = fields.RegField(label="Number plate", required=False, max_length=24)

    operator = forms.ModelChoiceField(
        queryset=Operator.objects,
        required=False,
        empty_label="",
        widget=forms.TextInput(),
        help_text="This only needs to change for permanent transfers, not for short-term loans to another depot",
    )

    vehicle_type = forms.ModelChoiceField(
        widget=AutcompleteWidget(field=Vehicle.vehicle_type.field),
        queryset=VehicleType.objects,
        required=False,
        empty_label="",
    )

    colours = forms.ModelChoiceField(
        widget=AutcompleteWidget(field=Vehicle.livery.field),
        label="Current livery",
        queryset=Livery.objects,
        required=False,
        help_text="""Please wait until the bus has *finished being repainted*
(<em>not</em> just "in the paint shop" or "awaiting repaint")""",
    )
    other_colour = forms.CharField(
        label="Other colours",
        help_text="E.g. '#c0c0c0 #ff0000 #ff0000' (red with a silver front)",
        required=False,
        max_length=255,
    )

    branding = forms.CharField(
        label="Other branding",
        required=False,
        max_length=40,
    )
    name = forms.CharField(
        label="Vehicle name",
        required=False,
        max_length=40,
    )
    previous_reg = fields.RegField(
        required=False,
        max_length=24,
        help_text="Separate multiple regs with a comma (,)",
    )

    features = forms.ModelMultipleChoiceField(
        queryset=VehicleFeature.objects,
        widget=forms.CheckboxSelectMultiple,
        required=False,
    )
    notes = forms.CharField(required=False, max_length=255)
    summary = fields.SummaryField(
        min_length=10,
        max_length=255,
        help_text="""Please briefly explain your changes and provide proof of your edit.
E.g. how you *know* a vehicle has *definitely been* withdrawn or repainted,
link to a picture to prove it. Be polite.""",
    )
    rules = forms.BooleanField(
        label="I agree that my edit is made in good faith and complies with the editing rules. I also acknowledge that abusing the vehicle editing feature may lead to a ban",
        required=true,
    )
    #Maybe find a way for this note to change so Superusers see a note that misusing the form may result in privilages being revoked rather than threatening ban?

    def clean_other_colour(self):
        if self.cleaned_data["other_colour"]:
            try:
                get_text_colour(self.cleaned_data["other_colour"])
            except ValueError as e:
                raise ValidationError(str(e))

        return self.cleaned_data["other_colour"]

    def clean_reg(self):
        reg = self.cleaned_data["reg"].replace(".", "")
        if self.cleaned_data["spare_ticket_machine"] and reg:
            raise ValidationError(
                "A spare ticket machine can\u2019t have a number plate"
            )
        return reg

    def __init__(self, data, *args, user, vehicle, **kwargs):
        super().__init__(data, *args, **kwargs)

        if vehicle.vehicle_type_id and not vehicle.is_spare_ticket_machine():
            self.fields["spare_ticket_machine"].disabled = True

        if not (vehicle.livery_id and vehicle.vehicle_type_id and vehicle.reg):
            self.fields["summary"].required = False

        if not user.is_superuser:
            if not (
                vehicle.notes
                or vehicle.operator_id in settings.ALLOW_VEHICLE_NOTES_OPERATORS
            ):
                del self.fields["notes"]

        if vehicle.is_spare_ticket_machine():
            del self.fields["notes"]
            if not vehicle.fleet_code:
                del self.fields["fleet_number"]
            if not vehicle.reg:
                del self.fields["reg"]
            if not vehicle.vehicle_type_id:
                del self.fields["vehicle_type"]
            if not vehicle.name:
                del self.fields["name"]
            if not vehicle.data:
                del self.fields["previous_reg"]
            if (
                not vehicle.colours
                and not vehicle.livery_id
                and "colours" in self.fields
            ):
                del self.fields["colours"]
                del self.fields["other_colour"]


class DebuggerForm(forms.Form):
    data = forms.CharField(widget=forms.Textarea(attrs={"rows": 6}))


class DateForm(forms.Form):
    date = forms.DateField()
