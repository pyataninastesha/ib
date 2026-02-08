from django.urls import path
from . import views

urlpatterns = [
    path('', views.menu_list, name='menu_list'),
    path('item/<int:item_id>/', views.item_detail, name='item_detail'),

    path('add-to-cart/<int:item_id>/', views.add_to_cart, name='add_to_cart'),

    # ✅ increase/decrease вместо -1/+1
    path('update-cart/<int:item_id>/increase/', views.cart_increase, name='cart_increase'),
    path('update-cart/<int:item_id>/decrease/', views.cart_decrease, name='cart_decrease'),

    path('remove-from-cart/<int:item_id>/', views.remove_from_cart, name='remove_from_cart'),

    path('cart/', views.view_cart, name='view_cart'),
    path('checkout/', views.checkout, name='checkout'),

    path('orders/', views.order_history, name='order_history'),
    path('orders/<int:order_id>/received/', views.mark_received, name='mark_received'),
    path("cook/stock/", views.stock_list, name="stock_list"),
    path("cook/stock/<int:product_id>/purchase/", views.add_to_purchase_request, name="add_to_purchase_request"),
    path("cook/stock/<int:product_id>/<str:action>/", views.stock_adjust, name="stock_adjust"),
    path('item/<int:item_id>/review/', views.add_review, name='add_review'),


]
