from django.test import TestCase
from django.urls import reverse
from django.contrib.auth import get_user_model
from .models import Category, MenuItem, Order, OrderItem, Review

User = get_user_model()


class MenuModelTests(TestCase):
    def setUp(self):
        self.category = Category.objects.create(
            name='Основные блюда',
            description='Вкусные основные блюда',
            order=1
        )
        self.item = MenuItem.objects.create(
            name='Плов',
            description='Вкусный плов с бараниной',
            price=250,
            category=self.category,
            allergens='глютен',
            calories=350,
            is_available=True
        )
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )

    def test_category_creation(self):
        self.assertEqual(self.category.name, 'Основные блюда')
        self.assertEqual(str(self.category), 'Основные блюда')

    def test_menu_item_creation(self):
        """Тест создания блюда"""
        self.assertEqual(self.item.name, 'Плов')
        self.assertEqual(self.item.price, 250)
        self.assertTrue(self.item.is_available)
        self.assertEqual(str(self.item), 'Плов')

    def test_review_creation(self):
        review = Review.objects.create(
            user=self.user,
            item=self.item,
            rating=5,
            comment='Очень вкусно!'
        )
        self.assertEqual(review.rating, 5)
        self.assertEqual(review.comment, 'Очень вкусно!')
        self.assertEqual(str(review), f'{self.user} - {self.item} (5)')

    def test_order_creation(self):
        """Тест создания заказа"""
        order = Order.objects.create(
            user=self.user,
            total_amount=500,
            status='pending'
        )
        self.assertEqual(order.total_amount, 500)
        self.assertEqual(order.status, 'pending')
        self.assertEqual(str(order), f'Заказ #{order.id} - {self.user}')


class MenuViewsTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.category = Category.objects.create(
            name='Основные блюда',
            description='Вкусные основные блюда'
        )
        self.item = MenuItem.objects.create(
            name='Плов',
            description='Вкусный плов с бараниной',
            price=250,
            category=self.category,
            is_available=True
        )

    def test_menu_list_view(self):
        response = self.client.get(reverse('menu_list'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'menu/menu_list.html')
        self.assertContains(response, 'Меню столовой')

    def test_item_detail_view(self):
        response = self.client.get(reverse('item_detail', args=[self.item.id]))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'menu/item_detail.html')
        self.assertContains(response, 'Плов')

    def test_add_to_cart_requires_login(self):
        response = self.client.get(reverse('add_to_cart', args=[self.item.id]))
        self.assertRedirects(response, f'{reverse("login")}?next={reverse("add_to_cart", args=[self.item.id])}')

    def test_add_to_cart_with_login(self):
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(reverse('add_to_cart', args=[self.item.id]))
        # Должен быть редирект на список меню
        self.assertRedirects(response, reverse('menu_list'))
        # Проверяем что товар добавился в сессию
        session = self.client.session
        self.assertIn('cart', session)
        self.assertIn(str(self.item.id), session['cart'])