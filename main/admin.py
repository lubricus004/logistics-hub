from django.contrib import admin
from .models import Product, Promoter, DailyDeployment, ActivityLog, Shop

@admin.register(Shop)
class ShopAdmin(admin.ModelAdmin):
    list_display = ('name', 'created_at')
    search_fields = ('name',)

@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ("name", "shop", "cartons_in_stock", "pieces_in_stock", "initial_stock", "items_per_carton", "price_per_carton", "price_per_piece")
    search_fields = ("name",)
    list_filter = ("shop",)

@admin.register(Promoter)
class PromoterAdmin(admin.ModelAdmin):
    list_display = ("name", "shop", "phone_number")
    search_fields = ("name",)
    list_filter = ("shop",)

@admin.register(DailyDeployment)
class DailyDeploymentAdmin(admin.ModelAdmin):
    list_display = ("date", "shop", "promoter", "product", "cartons_taken", "pieces_taken", "cartons_returned", "pieces_returned", "cash_owed")
    list_filter = ("date", "shop", "promoter", "product")

@admin.register(ActivityLog)
class ActivityLogAdmin(admin.ModelAdmin):
    list_display = ("created_at", "shop", "business_date", "event_type", "promoter_name", "product_name", "cartons", "pieces", "label")
    list_filter = ("event_type", "business_date", "shop")
    search_fields = ("promoter_name", "product_name", "label")
    readonly_fields = ("created_at",)