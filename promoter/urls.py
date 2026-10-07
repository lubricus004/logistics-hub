from django.urls import path
from . import views

urlpatterns = [
    path('', views.promoter_login, name='promoter_login'),
    path('dashboard/', views.promoter_dashboard, name='promoter_dashboard'),
    path('logout/', views.promoter_logout, name='promoter_logout'),
]