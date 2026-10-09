from django.shortcuts import render, redirect
from django.contrib import messages
from main.models import Promoter, DailyDeployment, Shop
from django.db.models import Sum
from datetime import date, timedelta

def promoter_login(request):
    if request.method == "POST":
        phone = request.POST.get("phone_number", "").strip()
        pin = request.POST.get("pin", "").strip()
        
        # Check BOTH phone and PIN
        promoter = Promoter.objects.filter(phone_number=phone, pin=pin).first()
        
        if promoter:
            request.session["promoter_id"] = promoter.id
            request.session["shop_id"] = promoter.shop.id
            return redirect("promoter_dashboard")
        else:
            messages.error(request, "Invalid phone number or PIN.")
            return redirect("promoter_login")
            
    return render(request, "promoter/promoter_login.html")

def promoter_dashboard(request):
    promoter_id = request.session.get("promoter_id")
    if not promoter_id:
        return redirect("promoter_login")
    
    promoter = Promoter.objects.filter(id=promoter_id).first()
    if not promoter:
        return redirect("promoter_login")
    
    shop = promoter.shop
    deployments = DailyDeployment.objects.filter(promoter=promoter).order_by("-date")
    total_cash_owed = sum(d.cash_owed for d in deployments)
    
    window = request.GET.get("window", "1")
    today = date.today()
    if window == "3": start_date = today - timedelta(days=2)
    elif window == "7": start_date = today - timedelta(days=6)
    else: start_date = today
    
    leaderboard = DailyDeployment.objects.filter(
        shop=shop, date__gte=start_date
    ).values("promoter__id", "promoter__name").annotate(
        total_cash=Sum("cash_owed")
    ).order_by("-total_cash")
    
    my_rank = None
    for i, entry in enumerate(leaderboard, 1):
        if entry["promoter__id"] == promoter.id:
            my_rank = i
            break
    
    context = {
        "promoter": promoter, "shop": shop, "deployments": deployments,
        "total_cash_owed": total_cash_owed, "leaderboard": leaderboard,
        "my_rank": my_rank, "active_window": window,
    }
    return render(request, "promoter/promoter_dashboard.html", context)

def promoter_logout(request):
    request.session.pop("promoter_id", None)
    request.session.pop("shop_id", None)
    return redirect("promoter_login")