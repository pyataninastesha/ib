from django.urls import path, include

urlpatterns = [
    path('', include('core.urls')),
    path('', include('users.urls')),
    path('menu/', include('menu.urls')),
]
