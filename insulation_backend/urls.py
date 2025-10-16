from django.contrib import admin
from django.urls import path, include
from calculator import views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include('calculator.api.urls')),
    
]