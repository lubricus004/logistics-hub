from django.shortcuts import render, redirect
from django.contrib import messages
from django.db.models import Sum
from django.utils import timezone
from datetime import timedelta
from main.models import Shop, Promoter, DailyDeployment, Product


def promoter_login(request):
    """Promoter logs in with phone number (scoped to a shop)."""
    if request.method == "POST":
        phone = request.POST.get("phone_number", "").strip()
        shop_code = request.POST.get("shop_code", "").strip()

        if not phone:
            messages.error(request, "❌ Please enter your phone number.")
            return redirect("promoter_login")

        # Find promoter — optionally scoped by shop
        qs = Promoter.objects.filter(phone_number=phone)
        if shop_code:
            qs = qs.filter(shop__id=shop_code)
        
        promoter = qs.first()

        if not promoter:
            messages.error(request, "❌ Phone number not registered. Ask your admin to add you.")
            return redirect("promoter_login")

        # Save to session so they stay logged in
        request.session["promoter_id"] = promoter.id
        request.session["promoter_shop_id"] = promoter.shop.id
        
        messages.success(request, f"👋 Welcome back, {promoter.name}!")
        return redirect("promoter_dashboard")

    return render(request, "promoter/promoter_login.html")


def promoter_dashboard(request):
    """Shows My Stock + cash-based leaderboard for the promoter's shop."""
    # 1. Check if they are logged in
    promoter_id = request.session.get("promoter_id")
    shop_id = request.session.get("promoter_shop_id")

    if not promoter_id or not shop_id:
        return redirect("promoter_login")

    try:
        promoter = Promoter.objects.get(id=promoter_id, shop_id=shop_id)
        shop = Shop.objects.get(id=shop_id)
    except (Promoter.DoesNotExist, Shop.DoesNotExist):
        request.session.flush()
        return redirect("promoter_login")

    # 2. My Stock: all deployments for this promoter in this shop
    my_deployments = (
        DailyDeployment.objects
        .filter(shop=shop, promoter=promoter)
        .select_related("product")
        .order_by("-date")
    )

    total_cash_owed = sum(d.cash_owed for d in my_deployments)

    # 3. Leaderboard: cash-based, rolling windows (1, 3, or 7 days)
    window = request.GET.get("window", "1")  
    today = timezone.localdate()

    if window == "3":
        start_date = today - timedelta(days=2)
    elif window == "7":
        start_date = today - timedelta(days=6)
    else:
        start_date = today

    leaderboard = (
        DailyDeployment.objects
        .filter(shop=shop, date__gte=start_date)
        .values("promoter__id", "promoter__name")
        .annotate(total_cash=Sum("cash_owed"))
        .order_by("-total_cash")
    )

    # Find current promoter's rank
    my_rank = None
    for idx, entry in enumerate(leaderboard, start=1):
        if entry["promoter__id"] == promoter.id:
            my_rank = idx
            break

    context = {
        "promoter": promoter,
        "shop": shop,
        "deployments": my_deployments,
        "total_cash_owed": total_cash_owed,
        "leaderboard": leaderboard,
        "my_rank": my_rank,
        "active_window": window,
    }
    return render(request, "promoter/promoter_dashboard.html", context)


def promoter_logout(request):
    request.session.flush()
    return redirect("promoter_login")