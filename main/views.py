import re
from django.shortcuts import render, redirect
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db.models import Sum
from .models import Product, Promoter, DailyDeployment, ActivityLog, Shop
from decimal import Decimal
from datetime import date, timedelta
from django.contrib.auth import login, logout
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required


def get_active_shop(request):
    shop_id = request.session.get("active_shop_id")
    if shop_id:
        return Shop.objects.filter(id=shop_id).first()
    return None

def shop_login(request):
    if request.user.is_authenticated:
        return redirect('dashboard')
    if request.method == "POST":
        email = request.POST.get("email", "").strip()
        password = request.POST.get("password", "").strip()
        try:
            user = User.objects.get(email=email)
            if user.check_password(password):
                login(request, user)
                shop = Shop.objects.get(owner=user)
                request.session["active_shop_id"] = shop.id
                return redirect("dashboard")
            else:
                messages.error(request, "Invalid email or password.")
        except User.DoesNotExist:
            messages.error(request, "Invalid email or password.")
    return render(request, "main/login.html")

def shop_register(request):
    if request.method == "POST":
        shop_name = request.POST.get("shop_name", "").strip()
        email = request.POST.get("email", "").strip()
        password = request.POST.get("password", "").strip()
        confirm_password = request.POST.get("confirm_password", "").strip()

        if password != confirm_password:
            messages.error(request, "Passwords do not match.")
            return redirect("shop_register")

        if User.objects.filter(email=email).exists():
            messages.error(request, "Email already registered.")
            return redirect("shop_register")

        user = User.objects.create_user(username=email, email=email, password=password)
        shop = Shop.objects.create(name=shop_name, owner=user)
        login(request, user)
        request.session["active_shop_id"] = shop.id
        return redirect("dashboard")
    return render(request, "main/register.html")

def shop_logout(request):
    logout(request)
    if 'active_shop_id' in request.session:
        del request.session['active_shop_id']
    return redirect('shop_login')

# ... end of your previous function ...

@login_required(login_url='shop_login')
def profile(request):
    user = request.user
    if request.method == "POST":
        new_email = request.POST.get("email", "").strip()
        new_password = request.POST.get("password", "").strip()
        
        if new_email:
            user.email = new_email
            user.username = new_email # Keep username and email in sync
        
        if new_password:
            user.set_password(new_password) # This encrypts the password securely
            
        user.save()
        messages.success(request, "✅ Profile updated successfully!")
        return redirect("profile")
        
    return render(request, "main/profile.html", {"user": user})


@login_required(login_url='shop_login')
def dashboard(request):
    shop = get_active_shop(request)
    if not shop:
        return redirect("shop_login")
    
    # ... (rest of your dashboard code) ...


@login_required(login_url='shop_login')
def statements(request):
    shop = get_active_shop(request)
    if not shop:
        return redirect("shop_login")
        
    # ... (rest of your statements code) ...


@login_required(login_url='shop_login')
def leaderboard_page(request):
    shop = get_active_shop(request)
    if not shop:
        return redirect("shop_login")
        
    # ... (rest of your leaderboard code) ...

def leaderboard_page(request):
    shop = get_active_shop(request)
    if not shop:
        return redirect("setup_shop")
    window = request.GET.get("window", "1")
    today = date.today()
    if window == "3":
        start_date = today - timedelta(days=2)
    elif window == "7":
        start_date = today - timedelta(days=6)
    else:
        start_date = today
    leaderboard = DailyDeployment.objects.filter(shop=shop, date__gte=start_date).values("promoter__id", "promoter__name").annotate(total_cash=Sum("cash_owed")).order_by("-total_cash")
    return render(request, "main/leaderboard.html", {"leaderboard": leaderboard, "active_window": window, "shop": shop})

def dashboard(request):
    shop = get_active_shop(request)
    if not shop:
        return redirect("setup_shop")

    if request.method == "POST":
        action = request.POST.get("action")

        if action == "add_product":
            name = request.POST.get("name", "").strip()
            cartons = int(request.POST.get("cartons_in_stock", "0") or 0)
            pieces = int(request.POST.get("pieces_in_stock", "0") or 0)
            items_per_crt = max(1, int(request.POST.get("items_per_carton", "1") or 1))
            existing = Product.objects.filter(shop=shop, name__iexact=name).first()
            if existing:
                add_total = (cartons * existing.items_per_carton) + pieces
                existing.initial_stock += add_total
                existing.save()
                existing.recalculate()
                messages.success(request, f"Added stock to '{existing.name}'!")
            else:
                prod = Product(shop=shop, name=name, items_per_carton=items_per_crt, price_per_carton=Decimal(request.POST.get("price_per_carton", "0.00")), price_per_piece=Decimal(request.POST.get("price_per_piece", "0.00")), cartons_in_stock=cartons, pieces_in_stock=pieces)
                prod.save()
                prod.recalculate()
                messages.success(request, f"New product '{name}' registered!")

        elif action == "add_promoter":
            name = request.POST.get("name", "").strip()
            phone = request.POST.get("phone_number", "").strip()
            pin = request.POST.get("pin", "").strip()

            if not pin or len(pin) != 4 or not pin.isdigit():
                messages.error(request, "PIN must be exactly 4 digits.")
                return redirect("dashboard")

            if phone and not re.match(r'^(?:\+233|0)(20|24|26|27|28|50|54|55|56|59|53)\d{7}$', phone):
                messages.error(request, "Invalid phone. Use: 0241234567")
                return redirect("dashboard")

            Promoter.objects.create(shop=shop, name=name, phone_number=phone, pin=pin)
            messages.success(request, f"Promoter '{name}' saved!")

        elif action == "edit_promoter":
            prom = Promoter.objects.filter(shop=shop, pk=request.POST.get("promoter_id")).first()
            if not prom:
                messages.error(request, "Promoter not found.")
            else:
                new_name = request.POST.get("name", "").strip()
                new_phone = request.POST.get("phone_number", "").strip()
                new_pin = request.POST.get("pin", "").strip()

                if not new_name:
                    messages.error(request, "Name cannot be empty.")
                else:
                    if new_pin and (len(new_pin) != 4 or not new_pin.isdigit()):
                        messages.error(request, "PIN must be exactly 4 digits.")
                        return redirect("dashboard")
                    if new_phone and not re.match(r'^(?:\+233|0)(20|24|26|27|28|50|54|55|56|59|53)\d{7}$', new_phone):
                        messages.error(request, "Invalid phone format.")
                        return redirect("dashboard")

                    prom.name = new_name
                    prom.phone_number = new_phone
                    if new_pin:
                        prom.pin = new_pin
                    prom.save()
                    messages.success(request, f"Promoter '{new_name}' updated!")

        elif action == "delete_promoter":
            promoter_id = request.POST.get("promoter_id")
            prom = Promoter.objects.filter(shop=shop, pk=promoter_id).first()
            if not prom:
                messages.error(request, "Promoter not found.")
            else:
                if DailyDeployment.objects.filter(promoter=prom).exists():
                    messages.error(request, f"Cannot delete '{prom.name}'. They have records.")
                else:
                    prom.delete()
                    messages.success(request, "Promoter deleted.")

        elif action == "dispatch_stock":
            promoter_id = request.POST.get("promoter")
            product_id = request.POST.get("product")
            c_taken = int(request.POST.get("cartons_taken", "0") or 0)
            p_taken = int(request.POST.get("pieces_taken", "0") or 0)
            if c_taken == 0 and p_taken == 0:
                messages.error(request, "Enter at least 1 carton or piece.")
            else:
                product = Product.objects.filter(shop=shop, pk=product_id).first()
                if product:
                    req = (c_taken * int(product.items_per_carton or 1)) + p_taken
                    if req > int(product.total_pieces_in_stock or 0):
                        messages.error(request, f"Not enough stock! Available: {product.cartons_in_stock} crt / {product.pieces_in_stock} pcs.")
                    else:
                        existing = DailyDeployment.objects.filter(shop=shop, promoter_id=promoter_id, product_id=product_id, date=date.today()).first()
                        try:
                            promoter = Promoter.objects.get(shop=shop, pk=promoter_id)
                            if existing:
                                existing.cartons_taken += c_taken
                                existing.pieces_taken += p_taken
                                existing.save()
                            else:
                                DailyDeployment.objects.create(shop=shop, promoter_id=promoter_id, product_id=product_id, cartons_taken=c_taken, pieces_taken=p_taken)
                            messages.success(request, "Dispatch logged!")
                            ActivityLog.record(event_type=ActivityLog.DISPATCH, promoter_name=promoter.name, product_name=product.name, cartons=c_taken, pieces=p_taken, label=f"Dispatched to {promoter.name}", shop=shop)
                        except Exception as e:
                            messages.error(request, f"Error: {e}")

        elif action == "reconcile_return":
            c_ret = int(request.POST.get("cartons_returned", "0") or 0)
            p_ret = int(request.POST.get("pieces_returned", "0") or 0)
            if c_ret == 0 and p_ret == 0:
                messages.error(request, "Enter at least 1 carton or piece to return.")
            else:
                dep = DailyDeployment.objects.filter(shop=shop, promoter_id=request.POST.get("promoter"), product_id=request.POST.get("product"), date=date.today()).first()
                if not dep:
                    messages.error(request, "No matching dispatch found today.")
                else:
                    items_per = dep.product.items_per_carton
                    remaining = ((dep.cartons_taken * items_per) + dep.pieces_taken) - ((dep.cartons_returned * items_per) + dep.pieces_returned)
                    attempting = (c_ret * items_per) + p_ret
                    if attempting > remaining:
                        messages.error(request, f"Cannot return more than outstanding ({remaining // items_per} crt / {remaining % items_per} pcs).")
                    else:
                        dep.cartons_returned += c_ret
                        dep.pieces_returned += p_ret
                        dep.save()
                        messages.success(request, f"Returned {c_ret} crt / {p_ret} pcs. Stock restored.")
                        ActivityLog.record(event_type=ActivityLog.RETURN, promoter_name=dep.promoter.name, product_name=dep.product.name, cartons=c_ret, pieces=p_ret, label="Returned", shop=shop)
        return redirect("dashboard")

    for p in Product.objects.filter(shop=shop):
        p.recalculate()
        
    deployments = DailyDeployment.objects.filter(shop=shop, date=date.today()).order_by("-id")
    promoter_records = {}
    for d in deployments:
        if d.promoter.id not in promoter_records:
            promoter_records[d.promoter.id] = {"promoter_name": d.promoter.name, "items": [], "grand_total": Decimal("0.00")}
        promoter_records[d.promoter.id]["items"].append(d)
        promoter_records[d.promoter.id]["grand_total"] += d.cash_owed

    return render(request, "main/dashboard.html", {
        "products": Product.objects.filter(shop=shop),
        "promoters": Promoter.objects.filter(shop=shop),
        "promoter_containers": list(promoter_records.values()),
        "cash_outstanding": sum(c["grand_total"] for c in promoter_records.values()),
        "shop": shop,
    })

def statements(request):
    shop = get_active_shop(request)
    if not shop:
        return redirect("setup_shop")
    date_str = request.GET.get("date", "").strip()
    selected = date.today()
    if date_str:
        try:
            selected = date.fromisoformat(date_str)
        except ValueError:
            pass
    logs_qs = ActivityLog.objects.filter(shop=shop, business_date=selected)
    if request.GET.get("event") in ("dispatch", "return", "correction", "delete"):
        logs_qs = logs_qs.filter(event_type=request.GET.get("event"))
    if request.GET.get("promoter"):
        logs_qs = logs_qs.filter(promoter_name=request.GET.get("promoter"))
    return render(request, "main/statement.html", {
        "selected_date": selected,
        "selected_date_str": selected.isoformat(),
        "today_str": date.today().isoformat(),
        "yesterday_str": (date.today() - timedelta(days=1)).isoformat(),
        "is_today": selected == date.today(),
        "logs": logs_qs.order_by("-created_at"),
        "entry_count": logs_qs.count(),
        "promoter_names": list(logs_qs.order_by("promoter_name").values_list("promoter_name", flat=True).distinct()),
        "event_filter": request.GET.get("event", ""),
        "promoter_filter": request.GET.get("promoter", ""),
    })