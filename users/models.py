from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone
from django.conf import settings
from decimal import Decimal, InvalidOperation


def _today():
    """Локальная дата (Москва), удобно для абонемента/получений."""
    return timezone.localdate()


class User(AbstractUser):
    ROLE_CHOICES = (
        ('student', 'Участник'),
        ('cook', 'Производство'),
        ('admin', 'Eco-менеджер'),
    )

    role = models.CharField(
        max_length=20,
        choices=ROLE_CHOICES,
        default='student',
        verbose_name='Роль'
    )

    phone = models.CharField(max_length=15, blank=True, verbose_name='Телефон')
    balance = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name='Баланс')
    allergies = models.TextField(blank=True, verbose_name='Аллергии')

    organization = models.ForeignKey('core.Organization', on_delete=models.SET_NULL, null=True, blank=True, related_name='users', verbose_name='Организация')

    # коды аллергенов из menu.MenuItem.ALLERGENS через запятую
    avoid_allergens = models.CharField(
        max_length=200,
        blank=True,
        verbose_name='Исключить аллергены (коды через запятую)'
    )

    food_preferences = models.TextField(blank=True, verbose_name='Пищевые предпочтения')

    def add_to_balance(self, amount):
        """Безопасно пополнить баланс (Decimal)."""
        try:
            amount = Decimal(str(amount))
        except (InvalidOperation, TypeError, ValueError):
            return False

        if amount <= 0:
            return False

        self.balance = (self.balance or Decimal('0')) + amount
        self.save(update_fields=['balance'])
        return True

    def deduct_from_balance(self, amount):
        """Списать средства, если хватает (Decimal)."""
        try:
            amount = Decimal(str(amount))
        except (InvalidOperation, TypeError, ValueError):
            return False

        if amount <= 0:
            return False

        current = self.balance or Decimal('0')
        if current >= amount:
            self.balance = current - amount
            self.save(update_fields=['balance'])
            return True
        return False

    def __str__(self):
        return f"{self.username} ({self.get_role_display()})"


class Subscription(models.Model):
    PLAN_BREAKFAST = 'breakfast'
    PLAN_LUNCH = 'lunch'

    PLAN_CHOICES = [
        (PLAN_BREAKFAST, 'Утро'),
        (PLAN_LUNCH, 'День'),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='subscriptions')
    organization = models.ForeignKey('core.Organization', on_delete=models.CASCADE, null=True, blank=True, related_name='subscriptions', verbose_name='Организация')
    plan = models.CharField(max_length=20, choices=PLAN_CHOICES)
    start_date = models.DateField()
    end_date = models.DateField()
    created_at = models.DateTimeField(auto_now_add=True)

    @property
    def is_active(self):
        today = timezone.localdate()
        return self.start_date <= today <= self.end_date

    def includes_meal(self, meal_type: str) -> bool:
        # meal_type: 'breakfast' | 'lunch'
        return self.plan == meal_type




class MealReceipt(models.Model):
    MEAL_BREAKFAST = 'breakfast'
    MEAL_LUNCH = 'lunch'

    MEAL_CHOICES = [
        (MEAL_BREAKFAST, 'Утро'),
        (MEAL_LUNCH, 'День'),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='meal_receipts')
    organization = models.ForeignKey('core.Organization', on_delete=models.CASCADE, null=True, blank=True, related_name='meal_receipts', verbose_name='Организация')
    date = models.DateField()
    meal_type = models.CharField(max_length=20, choices=MEAL_CHOICES)
    issued_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='issued_meals'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'date', 'meal_type')
        ordering = ['-date', '-created_at']

    def __str__(self):
        return f"{self.user} {self.date} {self.get_meal_type_display()}"


class MealRequest(models.Model):
    STATUS_REQUESTED = 'requested'   # участник нажал "Запросить"
    STATUS_ISSUED = 'issued'         # повар выдал
    STATUS_CONFIRMED = 'confirmed'   # участник подтвердил
    STATUS_CANCELLED = 'cancelled'   # участник отменил заявку (если передумал)

    STATUS_CHOICES = [
        (STATUS_REQUESTED, 'Запрошено'),
        (STATUS_ISSUED, 'Выдано поваром'),
        (STATUS_CONFIRMED, 'Подтверждено участником'),
        (STATUS_CANCELLED, 'Отменено'),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='meal_requests')
    organization = models.ForeignKey('core.Organization', on_delete=models.CASCADE, null=True, blank=True, related_name='meal_requests', verbose_name='Организация')
    date = models.DateField()
    meal_type = models.CharField(max_length=20, choices=MealReceipt.MEAL_CHOICES)

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_REQUESTED)

    subscription = models.ForeignKey('Subscription', on_delete=models.SET_NULL, null=True, blank=True)

    requested_at = models.DateTimeField(auto_now_add=True)
    issued_at = models.DateTimeField(null=True, blank=True)
    confirmed_at = models.DateTimeField(null=True, blank=True)

    issued_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='issued_meal_requests'
    )
    stock_deducted = models.BooleanField(
        default=False,
        verbose_name="Продукты списаны"
    )


    class Meta:
        ordering = ['-date', '-requested_at']

    def __str__(self):
        return f"{self.user} {self.date} {self.meal_type} {self.status}"



class BalanceTopUp(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='topups')
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Пополнение баланса'
        verbose_name_plural = 'Пополнения баланса'

    def __str__(self):
        return f"{self.user} +{self.amount} ₽ ({self.created_at:%d.%m.%Y %H:%M})"
