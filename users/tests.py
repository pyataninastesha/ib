from django.test import TestCase
from django.urls import reverse
from django.contrib.auth import get_user_model
from .models import User


class UserModelTests(TestCase):
    def test_create_user(self):
        """Тест создания пользователя"""
        user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123',
            phone='+79999999999',
            allergies='молоко, яйца'
        )
        self.assertEqual(user.username, 'testuser')
        self.assertEqual(user.email, 'test@example.com')
        self.assertEqual(user.phone, '+79999999999')
        self.assertEqual(user.allergies, 'молоко, яйца')
        self.assertTrue(user.check_password('testpass123'))
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_superuser)

    def test_add_to_balance(self):
        """Тест пополнения баланса"""
        user = User.objects.create_user('testuser', 'test@example.com', 'testpass123')
        initial_balance = user.balance
        user.add_to_balance(100)
        self.assertEqual(user.balance, initial_balance + 100)

    def test_deduct_from_balance_success(self):
        """Тест успешного списания с баланса"""
        user = User.objects.create_user('testuser', 'test@example.com', 'testpass123')
        user.add_to_balance(100)
        result = user.deduct_from_balance(50)
        self.assertTrue(result)
        self.assertEqual(user.balance, 50)

    def test_deduct_from_balance_failure(self):
        """Тест неудачного списания (недостаточно средств)"""
        user = User.objects.create_user('testuser', 'test@example.com', 'testpass123')
        user.balance = 30
        user.save()
        result = user.deduct_from_balance(50)
        self.assertFalse(result)
        self.assertEqual(user.balance, 30)


class UserViewsTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )

    def test_register_view(self):
        """Тест страницы регистрации"""
        response = self.client.get(reverse('register'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'users/register.html')

    def test_login_view(self):
        """Тест страницы входа"""
        response = self.client.get(reverse('login'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'users/login.html')

    def test_wallet_view_requires_login(self):
        """Тест что кошелек требует авторизации"""
        response = self.client.get(reverse('wallet'))
        self.assertRedirects(response, f'{reverse("login")}?next={reverse("wallet")}')

    def test_wallet_view_with_login(self):
        """Тест кошелька с авторизацией"""
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(reverse('wallet'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'users/wallet.html')