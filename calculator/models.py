from django.db import models
from django.contrib.auth.models import User

class Insulator(models.Model):
    name = models.CharField(max_length=255)
    description = models.TextField()
    is_active = models.BooleanField(default=True)
    image_key = models.CharField(max_length=255, null=True, blank=True)
    thermal_conductivity = models.FloatField()
    price_per_m2 = models.DecimalField(max_digits=10, decimal_places=2)
    density = models.FloatField()
    fire_rating = models.CharField(max_length=10)

    def __str__(self):
        return self.name

class Request(models.Model):
    class Status(models.TextChoices):
        DRAFT = 'DRAFT', 'Черновик'
        DELETED = 'DELETED', 'Удалён'
        FORMED = 'FORMED', 'Сформирован'
        COMPLETED = 'COMPLETED', 'Завершён'
        REJECTED = 'REJECTED', 'Отклонён'

    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)
    creation_datetime = models.DateTimeField(auto_now_add=True)
    formation_datetime = models.DateTimeField(null=True, blank=True)
    completion_datetime = models.DateTimeField(null=True, blank=True)
    client = models.ForeignKey(User, on_delete=models.DO_NOTHING, related_name='created_requests')
    manager = models.ForeignKey(User, on_delete=models.DO_NOTHING, related_name='managed_requests', null=True, blank=True)
    climate_zone = models.CharField(max_length=100)
    required_r_value = models.FloatField()
    wall_type = models.CharField(max_length=50)
    norm_standard = models.CharField(max_length=50)
    total_thickness = models.FloatField(null=True, blank=True)

    def __str__(self):
        return f"Заявка №{self.id}"
        
class RequestInsulator(models.Model):
    request = models.ForeignKey(Request, on_delete=models.CASCADE)  # Изменено на CASCADE
    insulator = models.ForeignKey(Insulator, on_delete=models.CASCADE)  # Для согласованности
    quantity = models.IntegerField()
    order = models.IntegerField()
    is_main = models.BooleanField(default=False)
    comment = models.TextField(null=True, blank=True)
    calculated_thickness = models.FloatField(null=True, blank=True)

    def __str__(self):
        return f"{self.request_id}-{self.insulator_id}"

    class Meta:
        unique_together = ('request', 'insulator')