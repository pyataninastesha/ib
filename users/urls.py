from django.urls import path
from . import views

urlpatterns = [
    path('register/', views.register_view, name='register'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),

    path('profile/', views.profile_view, name='profile'),
    path('wallet/', views.wallet_view, name='wallet'),
    path('banquets/', views.banquet_purchase_view, name='banquets'),
    path('subscription/', views.subscription_view, name='subscription'),
    path('subscription/cancel/<int:sub_id>/', views.subscription_cancel, name='subscription_cancel'),
    path('receive-meal/', views.receive_meal_view, name='receive_meal'),
    path('receive-meal/request/', views.request_meal, name='request_meal'),
    path('receive-meal/cancel/<int:request_id>/', views.cancel_meal_request, name='cancel_meal_request'),
    path('receive-meal/confirm/<int:request_id>/', views.confirm_meal, name='confirm_meal'),


]
