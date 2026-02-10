from django.db import models
from django.conf import settings
from decimal import Decimal


class Category(models.Model):
    name = models.CharField(max_length=100, verbose_name='Название')
    description = models.TextField(blank=True, verbose_name='Описание')
    order = models.IntegerField(default=0, verbose_name='Порядок')

    class Meta:
        verbose_name = 'Категория'
        verbose_name_plural = 'Категории'
        ordering = ['order']

    def __str__(self):
        return self.name


class MenuItem(models.Model):
    ALLERGENS = [
        ('gluten', 'Глютен (пшеница/мука)'),
        ('lactose', 'Лактоза (молочные продукты)'),
        ('eggs', 'Яйца'),
        ('nuts', 'Орехи'),
        ('peanuts', 'Арахис'),
        ('sesame', 'Кунжут'),
        ('soy', 'Соя'),
        ('fish', 'Рыба'),
        ('seafood', 'Морепродукты'),
        ('strawberry', 'Клубника'),
        ('tomato', 'Помидоры'),
        ('cocoa', 'Шоколад / какао'),
        ('citrus', 'Цитрусовые'),
        ('honey', 'Мёд'),
        ('apple', 'Яблоки'),
        ('banana', 'Банан'),
    ]
    name = models.CharField(max_length=200, verbose_name='Название')
    description = models.TextField(verbose_name='Описание')
    price = models.DecimalField(max_digits=8, decimal_places=2, verbose_name='Цена')
    category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name='items', verbose_name='Категория')
    image = models.ImageField(upload_to='menu_items/', blank=True, null=True, verbose_name='Изображение')

    # хранится строкой
    allergens = models.CharField(max_length=300, blank=True, verbose_name='Аллергены (коды через пробел)')
    is_available = models.BooleanField(default=True, verbose_name='Доступно')
    calories = models.IntegerField(blank=True, null=True, verbose_name='Калории')

    class Meta:
        verbose_name = 'Позиция меню'
        verbose_name_plural = 'Позиции меню'
        ordering = ['category', 'name']

    def __str__(self):
        return self.name


class BanquetMenu(models.Model):
    """Готовый набор блюд для банкета (кейтеринг)."""

    STATUS_PENDING = 'pending'
    STATUS_APPROVED = 'approved'
    STATUS_REJECTED = 'rejected'

    STATUS_CHOICES = [
        (STATUS_PENDING, 'На рассмотрении'),
        (STATUS_APPROVED, 'Принято'),
        (STATUS_REJECTED, 'Отклонено'),
    ]

    name = models.CharField(max_length=200, verbose_name='Название')
    description = models.TextField(blank=True, verbose_name='Описание')
    items = models.ManyToManyField('MenuItem', blank=True, related_name='banquet_menus', verbose_name='Блюда')

    # ВАЖНО: повар создаёт → админ принимает/отклоняет
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='banquet_menus_created',
        verbose_name='Создал',
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_PENDING,
        verbose_name='Статус',
    )
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='banquet_menus_reviewed',
        verbose_name='Проверил',
    )
    reviewed_at = models.DateTimeField(null=True, blank=True, verbose_name='Проверено')

    # Активность меню для клиента (включается при approve)
    is_active = models.BooleanField(default=False, verbose_name='Активно')

    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Создано')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Обновлено')

    class Meta:
        verbose_name = 'Меню для банкета'
        verbose_name_plural = 'Меню для банкетов'
        ordering = ['-updated_at']

    def __str__(self):
        return self.name

    @property
    def price_per_person(self):
        """Сумма цен блюд в наборе (за 1 гостя)."""
        total = Decimal('0')
        for it in self.items.all():
            try:
                total += it.price
            except Exception:
                pass
        return total



class Review(models.Model):
    RATING_CHOICES = [
        (1, '1 - Ужасно'),
        (2, '2 - Плохо'),
        (3, '3 - Нормально'),
        (4, '4 - Хорошо'),
        (5, '5 - Отлично'),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, verbose_name='Пользователь')
    item = models.ForeignKey(MenuItem, on_delete=models.CASCADE, related_name='reviews', verbose_name='Блюдо')
    rating = models.IntegerField(choices=RATING_CHOICES, verbose_name='Оценка')
    comment = models.TextField(verbose_name='Комментарий')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Дата создания')

    class Meta:
        verbose_name = 'Отзыв'
        verbose_name_plural = 'Отзывы'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.user} - {self.item} ({self.rating})'


class Order(models.Model):
    STATUS_CHOICES = [
        ('pending', 'В обработке'),
        ('confirmed', 'Подтвержден'),
        ('preparing', 'Готовится'),
        ('ready', 'Готов к выдаче'),
        ('completed', 'Завершен'),
        ('cancelled', 'Отменен'),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, verbose_name='Пользователь')
    items = models.ManyToManyField(MenuItem, through='OrderItem', verbose_name='Позиции')
    order_type = models.CharField(
        max_length=20,
        choices=[('regular', 'Обычный'), ('banquet', 'Банкет')],
        default='regular',
        verbose_name='Тип заказа'
    )
    event_date = models.DateField(blank=True, null=True, verbose_name='Дата мероприятия')
    guests_count = models.IntegerField(blank=True, null=True, verbose_name='Количество гостей')
    total_amount = models.DecimalField(max_digits=10, decimal_places=2, verbose_name='Общая сумма')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending', verbose_name='Статус')
    received_by_student = models.BooleanField(default=False, verbose_name='Получено клиентом')
    received_at = models.DateTimeField(blank=True, null=True, verbose_name='Дата получения')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Дата создания')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Дата обновления')

    class Meta:
        verbose_name = 'Заказ'
        verbose_name_plural = 'Заказы'
        ordering = ['-created_at']

    def __str__(self):
        return f'Заказ #{self.id} - {self.user}'


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, verbose_name='Заказ')
    item = models.ForeignKey(MenuItem, on_delete=models.CASCADE, verbose_name='Позиция')
    quantity = models.IntegerField(default=1, verbose_name='Количество')
    price = models.DecimalField(max_digits=8, decimal_places=2, verbose_name='Цена')

    class Meta:
        verbose_name = 'Позиция заказа'
        verbose_name_plural = 'Позиции заказов'

    def __str__(self):
        return f'{self.quantity} x {self.item.name}'


class Product(models.Model):
    name = models.CharField(max_length=200, unique=True)
    unit = models.CharField(max_length=20, default="г")
    stock = models.DecimalField(max_digits=20, decimal_places=2, default=0)
    min_stock = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    @staticmethod
    def normalize_name(value: str) -> str:
        if not value:
            return value
        v = " ".join(value.strip().split())
        while v and v[0] in "([{":
            v = v[1:].lstrip()
        while v and v[-1] in ")]}.,;:!?":
            v = v[:-1].rstrip()
        v = " ".join(v.strip().split())
        v = v.lower()
        return (v[:1].upper() + v[1:]) if v else v

    def save(self, *args, **kwargs):
        self.name = self.normalize_name(self.name)
        super().save(*args, **kwargs)


class MenuItemIngredient(models.Model):
    item = models.ForeignKey('MenuItem', on_delete=models.CASCADE, related_name='ingredients')
    product = models.ForeignKey(Product, on_delete=models.PROTECT, related_name='used_in')
    amount = models.DecimalField(max_digits=10, decimal_places=2)  # сколько на 1 порцию

    class Meta:
        unique_together = ('item', 'product')

    def __str__(self):
        return f"{self.item.name}: {self.product.name} — {self.amount}{self.product.unit}"


class DailyMenu(models.Model):
    date = models.DateField(unique=True)
    breakfast_items = models.ManyToManyField("MenuItem", blank=True, related_name="daily_breakfasts")
    lunch_items = models.ManyToManyField("MenuItem", blank=True, related_name="daily_lunches")

    def __str__(self):
        return f"Меню дня {self.date}"
