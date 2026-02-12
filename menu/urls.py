from django.urls import path
from . import views

urlpatterns = [
    path('', views.menu_list, name='menu_list'),
    path('item/<int:item_id>/', views.item_detail, name='item_detail'),

    path('add-to-cart/<int:item_id>/', views.add_to_cart, name='add_to_cart'),
    path('remove-from-cart/<int:item_id>/', views.remove_from_cart, name='remove_from_cart'),

    path('cart/', views.view_cart, name='view_cart'),
    path('checkout/', views.checkout, name='checkout'),
    path('update-cart/<int:item_id>/<str:action>/', views.update_cart, name='update_cart'),

    path('orders/', views.order_history, name='order_history'),
    path('orders/<int:order_id>/cancel/', views.cancel_order, name='cancel_order'),
    path('orders/<int:order_id>/banquet-review/', views.add_banquet_review, name='add_banquet_review'),
    path("cook/stock/", views.stock_list, name="stock_list"),
    path("cook/stock/fill-min/", views.stock_fill_to_min, name="stock_fill_to_min"),
    path("cook/stock/<int:product_id>/purchase/", views.add_to_purchase_request, name="add_to_purchase_request"),
    path('item/<int:item_id>/review/', views.add_review, name='add_review'),


]
