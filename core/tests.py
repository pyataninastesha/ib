from django.test import TestCase
from django.urls import reverse


class CoreViewsTests(TestCase):
    def test_home_view(self):
        # Тест главной страницы
        response = self.client.get(reverse('home'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'core/home.html')
        self.assertContains(response, 'Добро пожаловать')

    def test_home_view_context(self):
        # Тест контекста главной страницы
        response = self.client.get(reverse('home'))
        self.assertIn('title', response.context)