from django.db import models
from django.conf import settings
import uuid


class PurchaseRequest(models.Model):
    STATUS_CHOICES = (
        ("new", "Новая"),
        ("in_progress", "В работе"),
        ("done", "Закуплено"),
    )

    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="purchase_requests")
    organization = models.ForeignKey('core.Organization', on_delete=models.CASCADE, null=True, blank=True, related_name='purchase_requests', verbose_name='Организация')
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


class Organization(models.Model):
    """Организация/заведение, в котором используется платформа EcoFood."""

    ORG_TYPES = (
        ('school', 'Школа/университет'),
        ('office', 'Офис/корпоративное питание'),
        ('cafe', 'Кафе/столовая/ресторан'),
        ('catering', 'Кейтеринг/мероприятия'),
        ('retail', 'Магазин/кулинария'),
        ('ngo', 'НКО/социальная кухня'),
        ('other', 'Другое'),
    )

    name = models.CharField(max_length=200, verbose_name='Название заведения')
    org_type = models.CharField(max_length=20, choices=ORG_TYPES, default='other', verbose_name='Тип заведения')
    goals = models.CharField(max_length=300, blank=True, verbose_name='Цели (через запятую)')
    avg_portions_per_day = models.PositiveIntegerField(default=0, verbose_name='Среднее порций в день')

    join_code = models.CharField(max_length=12, unique=True, verbose_name='Код подключения')

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Организация'
        verbose_name_plural = 'Организации'
        ordering = ['name']

    def __str__(self):
        return f"{self.name}" 

    @staticmethod
    def generate_join_code() -> str:
        # короткий, удобный код
        return uuid.uuid4().hex[:12].upper()
