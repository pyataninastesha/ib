from django.contrib.auth.models import User
from django.db import models
from django.utils import timezone


class Dish(models.Model):
    name = models.CharField(max_length=255)
    price = models.DecimalField(max_digits=6, decimal_places=2)
    quantity = models.PositiveIntegerField(default=0)
    is_available = models.BooleanField(default=True)

    def __str__(self):
        return self.name


class Order(models.Model):
    STATUS_CHOICES = [
        ('new', 'Новый'),
        ('cooking', 'Готовится'),
        ('ready', 'Готов к выдаче'),
        ('done', 'Завершён'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='new')

    def __str__(self):
        return f"Заказ #{self.id} — {self.user.username}"


class OrderItem(models.Model):
    order = models.ForeignKey(Order, related_name='items', on_delete=models.CASCADE)
    dish = models.ForeignKey(Dish, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=1)


class MealReceipt(models.Model):
    MEAL_CHOICES = [
        ('breakfast', 'Завтрак'),
        ('lunch', 'Обед'),
    ]

    student = models.ForeignKey(User, on_delete=models.CASCADE)
    meal_type = models.CharField(max_length=20, choices=MEAL_CHOICES)
    date = models.DateField(default=timezone.now)

    class Meta:
        unique_together = ('student', 'meal_type', 'date')
