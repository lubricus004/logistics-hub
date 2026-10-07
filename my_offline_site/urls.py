from django.contrib import admin
from django.urls import path, include
from main.views import dashboard, statements, setup_shop, logout_shop, leaderboard_page

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', dashboard, name='dashboard'),
    path('statements/', statements, name='statements'),
    path('setup/', setup_shop, name='setup_shop'),
    path('logout/', logout_shop, name='logout_shop'),
    path('leaderboard/', leaderboard_page, name='leaderboard'),
    path('promoter/', include('promoter.urls')),  # <-- This was missing!
]