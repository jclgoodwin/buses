from django.contrib import admin
from django.contrib.postgres.aggregates import StringAgg
from .models import DataSet, Tariff, PriceGroup, FareZone, UserProfile, DistanceMatrixElement, FareTable


class DataSetAdmin(admin.ModelAdmin):
    list_display = ["__str__", "description", "noc"]
    autocomplete_fields = ["operators"]

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        if 'changelist' in request.resolver_match.view_name:
            return queryset.annotate(noc=StringAgg('operators', ', ', distinct=True))
        return queryset

    def noc(self, obj):
        return obj.noc


class TariffAdmin(admin.ModelAdmin):
    autocomplete_fields = ["operators", "services"]


class FareZoneAdmin(admin.ModelAdmin):
    autocomplete_fields = ["stops"]


class FareTableAdmin(admin.ModelAdmin):
    raw_id_fields = ["user_profile", "sales_offer_package", "tariff"]


admin.site.register(DataSet, DataSetAdmin)
admin.site.register(Tariff, TariffAdmin)
admin.site.register(PriceGroup)
admin.site.register(UserProfile)
admin.site.register(FareTable, FareTableAdmin)
admin.site.register(DistanceMatrixElement)
admin.site.register(FareZone, FareZoneAdmin)
