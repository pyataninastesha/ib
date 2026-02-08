from django.urls import path
from . import views

urlpatterns = [
    
path('admin/', views.admin_dashboard, name='admin_dashboard'),

    path('', views.home, name='home'),

    # cook
    path('cook/issue/', views.cook_issue, name='cook_issue'),
    path('cook/purchase/', views.cook_purchase, name='cook_purchase'),
    path('cook/daily-menu/', views.cook_daily_menu, name='cook_daily_menu'),

    # admin
    path('admin/', views.admin_dashboard, name='admin_dashboard'),
    path('admin/reports/', views.admin_reports, name='admin_reports'),
    path('admin/organization/', views.organization_settings, name='organization_settings'),
    path('eco/dashboard/', views.eco_dashboard, name='eco_dashboard'),
    path('admin/purchase/', views.admin_purchase, name='admin_purchase'),
    path('admin/subscriptions/', views.admin_subscriptions, name='admin_subscriptions'),
]
