
from django.contrib import admin
from django.urls import path
from calculator import views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('catalog/', views.insulators_list, name='insulators_list'),
    path('info/<int:id>/', views.insulator_detail, name='insulator_detail'),
    path('basket/<int:id>/', views.request_detail, name='request_detail'),
]