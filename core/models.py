from django.db import models
from django.conf import settings


class PurchaseRequest(models.Model):
    STATUS_CHOICES = (
        ("new", "Новая"),
        ("in_progress", "В работе"),
        ("done", "Закуплено"),
        ("cancelled", "Отменено"),
        ("rejected", "Отклонено"),
    )

    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="purchase_requests")
    title = models.CharField(max_length=200, verbose_name="Продукт")
    quantity = models.CharField(max_length=50, blank=True, verbose_name="Количество")
    unit = models.CharField(max_length=50, blank=True, verbose_name="Ед. изм.")
    comment = models.TextField(blank=True, verbose_name="Комментарий")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="new")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Заявка на закупку"
        verbose_name_plural = "Заявки на закупку"

    def __str__(self):
        return f"{self.title} ({self.get_status_display()})"
