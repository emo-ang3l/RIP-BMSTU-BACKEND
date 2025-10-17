from django.contrib import admin
from django.urls import path
from calculator import views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('insulators/', views.insulators_list, name='insulators_list'),
    path('insulators/detail/<int:id>/', views.insulator_detail, name='insulator_detail'),
    path('request/detail/<int:id>/', views.request_detail, name='request_detail'),
    path('add_insulator/<int:insulator_id>/', views.add_insulator_to_request, name='add_insulator_to_request'),
    path('delete_request/<int:id>/', views.delete_request, name='delete_request'),
    
]