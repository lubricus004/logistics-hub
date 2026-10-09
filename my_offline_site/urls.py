from django.contrib import admin
from django.urls import path, include
from main.views import dashboard, statements, shop_login, shop_register, shop_logout, leaderboard_page, profile

urlpatterns = [
    path('admin/', admin.site.urls),
    path('login/', shop_login, name='shop_login'),
    path('register/', shop_register, name='shop_register'),
    path('logout/', shop_logout, name='shop_logout'),
    path('', dashboard, name='dashboard'),
    path('leaderboard/', leaderboard_page, name='leaderboard'),
    path('statements/', statements, name='statements'),
    path('promoter/', include('promoter.urls')),
    path('profile/', profile, name='profile'),
]