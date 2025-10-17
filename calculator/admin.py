from django.contrib import admin
from .models import Insulator, InsulatorRequest, DetailRequestInsulator

@admin.register(Insulator)
class InsulatorAdmin(admin.ModelAdmin):
    list_display = ('insulator_name', 'Insulator_active', 'thermal_conductivity', 'price_per_m2')
    search_fields = ('insulator_name',)

@admin.register(InsulatorRequest)
class RequestAdmin(admin.ModelAdmin):
    list_display = ('id', 'status_request', 'client', 'creation_datetime')
    list_filter = ('status_request',)

@admin.register(DetailRequestInsulator)
class RequestInsulatorAdmin(admin.ModelAdmin):
    list_display = ('detail_request', 'insulator', 'quantity', 'order', 'DetailRequestActive')