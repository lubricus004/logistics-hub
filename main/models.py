from django.db import models
from django.core.exceptions import ValidationError
from django.utils import timezone

# --- NEW: THE SHOP MODEL ---
class Shop(models.Model):
    name = models.CharField(max_length=200, default="My Shop")
    created_at = models.DateTimeField(auto_now_add=True)
    def __str__(self):
        return self.name

class Product(models.Model):
    shop = models.ForeignKey(Shop, on_delete=models.CASCADE, null=True, blank=True)
    name = models.CharField(max_length=200)
    items_per_carton = models.IntegerField(help_text="How many single pieces fit into one carton?")
    price_per_carton = models.DecimalField(max_digits=10, decimal_places=2)
    price_per_piece = models.DecimalField(max_digits=10, decimal_places=2)
    initial_stock = models.IntegerField(default=0)
    cartons_in_stock = models.IntegerField(default=0, editable=False)
    pieces_in_stock = models.IntegerField(default=0, editable=False)
    total_pieces_in_stock = models.IntegerField(default=0, editable=False)

    def recalculate(self):
        from django.db.models import Sum
        from django.db.models.functions import Coalesce
        agg = self.dailydeployment_set.aggregate(
            taken_c=Coalesce(Sum("cartons_taken"), 0), taken_p=Coalesce(Sum("pieces_taken"), 0),
            ret_c=Coalesce(Sum("cartons_returned"), 0), ret_p=Coalesce(Sum("pieces_returned"), 0),
        )
        taken_c, taken_p = int(agg["taken_c"] or 0), int(agg["taken_p"] or 0)
        ret_c, ret_p = int(agg["ret_c"] or 0), int(agg["ret_p"] or 0)
        items_per, initial = int(self.items_per_carton or 1), int(self.initial_stock or 0)
        taken = (taken_c * items_per) + taken_p
        returned = (ret_c * items_per) + ret_p
        current = max(0, initial - (taken - returned))
        self.total_pieces_in_stock = current
        self.cartons_in_stock = current // items_per
        self.pieces_in_stock = current % items_per
        super().save(update_fields=["total_pieces_in_stock", "cartons_in_stock", "pieces_in_stock"])

    def save(self, *args, **kwargs):
        if self.pk is None:
            self.initial_stock = (int(self.cartons_in_stock or 0) * int(self.items_per_carton or 1)) + int(self.pieces_in_stock or 0)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.name} ({self.cartons_in_stock} crt, {self.pieces_in_stock} pcs)"

class Promoter(models.Model):
    shop = models.ForeignKey(Shop, on_delete=models.CASCADE, null=True, blank=True)
    name = models.CharField(max_length=100)
    phone_number = models.CharField(max_length=20, blank=True)
    def __str__(self):
        return self.name

class DailyDeployment(models.Model):
    shop = models.ForeignKey(Shop, on_delete=models.CASCADE, null=True, blank=True)
    promoter = models.ForeignKey(Promoter, on_delete=models.CASCADE)
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    date = models.DateField(auto_now_add=True)
    cartons_taken = models.IntegerField(default=0)
    pieces_taken = models.IntegerField(default=0)
    cartons_returned = models.IntegerField(default=0)
    pieces_returned = models.IntegerField(default=0)
    cash_owed = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, editable=False)

    def save(self, *args, **kwargs):
        items_per = int(self.product.items_per_carton or 1)
        new_taken = (int(self.cartons_taken or 0) * items_per) + int(self.pieces_taken or 0)
        new_returned = (int(self.cartons_returned or 0) * items_per) + int(self.pieces_returned or 0)
        if new_returned > new_taken:
            raise ValidationError(f"Returns ({new_returned} pcs) cannot exceed dispatches ({new_taken} pcs)!")
        units_sold = new_taken - new_returned
        if units_sold > 0:
            cartons_sold, pieces_sold = units_sold // items_per, units_sold % items_per
            self.cash_owed = (cartons_sold * self.product.price_per_carton) + (pieces_sold * self.product.price_per_piece)
        else:
            self.cash_owed = 0.00
        super().save(*args, **kwargs)
        self.product.recalculate()

    def delete(self, *args, **kwargs):
        product = self.product
        super().delete(*args, **kwargs)
        product.recalculate()

    def __str__(self):
        return f"{self.promoter.name} - {self.product.name}"

class ActivityLog(models.Model):
    shop = models.ForeignKey(Shop, on_delete=models.CASCADE, null=True, blank=True)
    DISPATCH = "dispatch"
    RETURN = "return"
    CORRECTION = "correction"
    DELETE = "delete"
    EVENT_CHOICES = [
        (DISPATCH, "Dispatched Out"), (RETURN, "Returned — Not Sold"),
        (CORRECTION, "Correction"), (DELETE, "Deleted Mistake"),
    ]
    created_at = models.DateTimeField(auto_now_add=True)
    business_date = models.DateField(db_index=True)
    event_type = models.CharField(max_length=20, choices=EVENT_CHOICES, db_index=True)
    promoter_name = models.CharField(max_length=100)
    product_name = models.CharField(max_length=200)
    cartons = models.IntegerField(default=0)
    pieces = models.IntegerField(default=0)
    cash_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    label = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.business_date} | {self.event_type} | {self.promoter_name} | {self.product_name}"

    @classmethod
    def record(cls, event_type, promoter_name, product_name, cartons=0, pieces=0, cash_amount=0, label="", business_date=None, shop=None):
        return cls.objects.create(
            shop=shop, business_date=business_date or timezone.localdate(), event_type=event_type,
            promoter_name=promoter_name, product_name=product_name, cartons=int(cartons or 0),
            pieces=int(pieces or 0), cash_amount=cash_amount or 0, label=label or "",
        )