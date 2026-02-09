from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),

    # cook
    path('cook/issue/', views.cook_issue, name='cook_issue'),
    path('cook/purchase/', views.cook_purchase, name='cook_purchase'),
    path('cook/banquet-menus/', views.cook_banquet_menus, name='cook_banquet_menus'),

    # admin
    path('admin/reports/', views.admin_reports, name='admin_reports'),
    path('admin/purchase/', views.admin_purchase, name='admin_purchase'),
    path('admin/banquet-menus/', views.admin_banquet_menus, name='admin_banquet_menus'),

]
