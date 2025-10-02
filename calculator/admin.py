from django.contrib import admin
from .models import Insulator, Request, RequestInsulator

@admin.register(Insulator)
class InsulatorAdmin(admin.ModelAdmin):
    list_display = ('insulator_name', 'is_active', 'thermal_conductivity', 'price_per_m2')
    search_fields = ('insulator_name',)

@admin.register(Request)
class RequestAdmin(admin.ModelAdmin):
    list_display = ('id', 'status_request', 'client', 'creation_datetime')
    list_filter = ('status_request',)

@admin.register(RequestInsulator)
class RequestInsulatorAdmin(admin.ModelAdmin):
    list_display = ('request', 'insulator', 'quantity', 'order', 'is_main')