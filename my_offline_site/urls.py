from django.contrib import admin
from django.urls import path, include
from main.views import dashboard, statements, setup_shop, logout_shop, leaderboard_page

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', dashboard, name='dashboard'),
    path('setup/', setup_shop, name='setup_shop'),
    path('logout/', logout_shop, name='logout_shop'),
    path('leaderboard/', leaderboard_page, name='leaderboard'),
    path('statements/', statements, name='statements'),
    path('promoter/', include('promoter.urls')),  # <-- THIS LINE FIXES THE 404
]