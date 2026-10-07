from django.contrib import admin
from .models import Product, Promoter, DailyDeployment, ActivityLog, Shop

@admin.register(Shop)
class ShopAdmin(admin.ModelAdmin):
    list_display = ('name', 'created_at')

@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ("name", "shop", "cartons_in_stock", "pieces_in_stock")
    list_filter = ("shop",)

@admin.register(Promoter)
class PromoterAdmin(admin.ModelAdmin):
    list_display = ("name", "shop", "phone_number")
    list_filter = ("shop",)

@admin.register(DailyDeployment)
class DailyDeploymentAdmin(admin.ModelAdmin):
    list_display = ("date", "shop", "promoter", "product", "cash_owed")
    list_filter = ("shop",)

@admin.register(ActivityLog)
class ActivityLogAdmin(admin.ModelAdmin):
    list_display = ("business_date", "shop", "event_type", "promoter_name", "product_name")
    list_filter = ("shop", "event_type")