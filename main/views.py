from django.shortcuts import render, redirect
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db.models import Sum
from .models import Product, Promoter, DailyDeployment, ActivityLog, Shop
from decimal import Decimal
from datetime import date, timedelta

def get_active_shop(request):
    shop_id = request.session.get("active_shop_id")
    if shop_id:
        return Shop.objects.filter(id=shop_id).first()
    return None

def setup_shop(request):
    if request.method == "POST":
        shop_name = request.POST.get("shop_name", "").strip()
        if not shop_name:
            messages.error(request, "Please enter a shop name.")
            return redirect("setup_shop")
        shop, created = Shop.objects.get_or_create(name=shop_name)
        request.session["active_shop_id"] = shop.id
        if created:
            messages.success(request, f"🎉 Shop '{shop_name}' created!")
        else:
            messages.success(request, f"👋 Welcome back to '{shop_name}'!")
        return redirect("dashboard")
    return render(request, "main/setup_shop.html")

def logout_shop(request):
    if 'active_shop_id' in request.session:
        del request.session['active_shop_id']
    return redirect('setup_shop')

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
            items_per_crt = int(request.POST.get("items_per_carton", "1") or 1)
            if items_per_crt < 1:
                items_per_crt = 1
            existing = Product.objects.filter(shop=shop, name__iexact=name).first()
            if existing:
                add_total = (cartons * existing.items_per_carton) + pieces
                existing.initial_stock += add_total
                existing.save()
                existing.recalculate()
                messages.success(request, f"📦 Added stock to '{existing.name}'!")
            else:
                prod = Product(
                    shop=shop, name=name, items_per_carton=items_per_crt,
                    price_per_carton=Decimal(request.POST.get("price_per_carton", "0.00")),
                    price_per_piece=Decimal(request.POST.get("price_per_piece", "0.00")),
                    cartons_in_stock=cartons, pieces_in_stock=pieces,
                )
                prod.save()
                prod.recalculate()
                messages.success(request, f"📦 New product '{name}' registered!")

        elif action == "adjust_warehouse":
            product_id = request.POST.get("product")
            direction = request.POST.get("direction", "add")
            cartons = int(request.POST.get("cartons", "0") or 0)
            pieces = int(request.POST.get("pieces", "0") or 0)
            prod = Product.objects.filter(shop=shop, pk=product_id).first()
            if not prod:
                messages.error(request, "❌ Product not found.")
            elif cartons == 0 and pieces == 0:
                messages.error(request, "❌ Enter at least 1 carton or 1 piece.")
            else:
                items_per = int(prod.items_per_carton or 1)
                delta = (cartons * items_per) + pieces
                if direction == "remove":
                    current = int(prod.total_pieces_in_stock or 0)
                    if delta > current:
                        messages.error(request, f"❌ Only {prod.cartons_in_stock} crt / {prod.pieces_in_stock} pcs in warehouse.")
                    else:
                        prod.initial_stock = max(0, int(prod.initial_stock or 0) - delta)
                        prod.save(update_fields=["initial_stock"])
                        prod.recalculate()
                        messages.success(request, f"📤 Removed {cartons} crt / {pieces} pcs from '{prod.name}'.")
                else:
                    prod.initial_stock = int(prod.initial_stock or 0) + delta
                    prod.save(update_fields=["initial_stock"])
                    prod.recalculate()
                    messages.success(request, f"📥 Added {cartons} crt / {pieces} pcs to '{prod.name}'.")

        elif action == "add_promoter":
            prom = Promoter.objects.create(
                shop=shop,
                name=request.POST.get("name"),
                phone_number=request.POST.get("phone_number", ""),
            )
            messages.success(request, f"👤 Promoter '{prom.name}' saved!")

        elif action == "edit_promoter":
            promoter_id = request.POST.get("promoter_id")
            new_name = request.POST.get("name", "").strip()
            new_phone = request.POST.get("phone_number", "").strip()
            prom = Promoter.objects.filter(shop=shop, pk=promoter_id).first()
            if not prom:
                messages.error(request, "❌ Promoter not found.")
            elif not new_name:
                messages.error(request, "❌ Name cannot be empty.")
            else:
                prom.name = new_name
                prom.phone_number = new_phone
                prom.save()
                messages.success(request, f"✅ Promoter '{new_name}' updated!")

        elif action == "delete_promoter":
            promoter_id = request.POST.get("promoter_id")
            prom = Promoter.objects.filter(shop=shop, pk=promoter_id).first()
            if not prom:
                messages.error(request, "❌ Promoter not found.")
            else:
                # Check if promoter has any dispatches
                has_records = DailyDeployment.objects.filter(promoter=prom).exists()
                if has_records:
                    messages.error(
                        request,
                        f"❌ Cannot delete '{prom.name}'. They have dispatch records. "
                        f"Clear their records first or rename them."
                    )
                else:
                    prom_name = prom.name
                    prom.delete()
                    messages.success(request, f"🗑️ Promoter '{prom_name}' deleted.")

        elif action == "dispatch_stock":
            promoter_id = request.POST.get("promoter")
            product_id = request.POST.get("product")
            c_taken = int(request.POST.get("cartons_taken", "0") or 0)
            p_taken = int(request.POST.get("pieces_taken", "0") or 0)
            if c_taken == 0 and p_taken == 0:
                messages.error(request, "❌ Enter at least 1 carton or 1 piece.")
            else:
                product = Product.objects.filter(shop=shop, pk=product_id).first()
                if not product:
                    messages.error(request, "❌ Product not found.")
                else:
                    # Stock availability check
                    items_per = int(product.items_per_carton or 1)
                    requested_pieces = (c_taken * items_per) + p_taken
                    available_pieces = int(product.total_pieces_in_stock or 0)
                    if requested_pieces > available_pieces:
                        messages.error(
                            request,
                            f"❌ Not enough stock! Requested: {c_taken} crt / {p_taken} pcs ({requested_pieces} pcs). "
                            f"Available: {product.cartons_in_stock} crt / {product.pieces_in_stock} pcs ({available_pieces} pcs)."
                        )
                    else:
                        existing = DailyDeployment.objects.filter(
                            shop=shop, promoter_id=promoter_id, product_id=product_id, date=date.today()
                        ).first()
                        try:
                            promoter = Promoter.objects.get(shop=shop, pk=promoter_id)
                            if existing:
                                DailyDeployment(
                                    pk=existing.pk, shop=shop, promoter_id=promoter_id, product_id=product_id,
                                    date=existing.date, cartons_taken=existing.cartons_taken + c_taken,
                                    pieces_taken=existing.pieces_taken + p_taken,
                                    cartons_returned=existing.cartons_returned, pieces_returned=existing.pieces_returned,
                                ).save()
                                messages.success(request, "🔄 Dispatch updated!")
                            else:
                                DailyDeployment(
                                    shop=shop, promoter_id=promoter_id, product_id=product_id,
                                    cartons_taken=c_taken, pieces_taken=p_taken,
                                ).save()
                                messages.success(request, " Morning dispatch logged!")
                            ActivityLog.record(
                                event_type=ActivityLog.DISPATCH, promoter_name=promoter.name,
                                product_name=product.name, cartons=c_taken, pieces=p_taken,
                                label=f"Dispatched {c_taken} crt / {p_taken} pcs to {promoter.name}", shop=shop,
                            )
                        except ValidationError as e:
                            msg = e.messages[0] if hasattr(e, "messages") else str(e)
                            messages.error(request, f"❌ {msg}")

        elif action == "reconcile_return":
            promoter_id = request.POST.get("promoter")
            product_id = request.POST.get("product")
            c_ret = int(request.POST.get("cartons_returned", "0") or 0)
            p_ret = int(request.POST.get("pieces_returned", "0") or 0)
            if c_ret == 0 and p_ret == 0:
                messages.error(request, "❌ Enter at least 1 carton or 1 piece to return.")
            else:
                dep = DailyDeployment.objects.filter(
                    shop=shop, promoter_id=promoter_id, product_id=product_id, date=date.today()
                ).first()
                if not dep:
                    messages.error(request, "❌ No matching morning dispatch found for this agent today!")
                else:
                    new_c_ret = dep.cartons_returned + c_ret
                    new_p_ret = dep.pieces_returned + p_ret
                    items_per = dep.product.items_per_carton
                    total_taken = (dep.cartons_taken * items_per) + dep.pieces_taken
                    already_returned = (dep.cartons_returned * items_per) + dep.pieces_returned
                    attempting = (c_ret * items_per) + p_ret
                    remaining = total_taken - already_returned
                    if attempting > remaining:
                        messages.error(
                            request,
                            f"❌ Cannot return {c_ret} crt / {p_ret} pcs. "
                            f"Only {remaining // items_per} crt and {remaining % items_per} pcs "
                            f"are still outstanding (taken {dep.cartons_taken} crt / {dep.pieces_taken} pcs, "
                            f"already returned {dep.cartons_returned} crt / {dep.pieces_returned} pcs)."
                        )
                    else:
                        try:
                            DailyDeployment(
                                pk=dep.pk, shop=shop, promoter_id=promoter_id, product_id=product_id,
                                date=dep.date, cartons_taken=dep.cartons_taken, pieces_taken=dep.pieces_taken,
                                cartons_returned=new_c_ret, pieces_returned=new_p_ret,
                            ).save()
                            messages.success(request, f"✅ Returned {c_ret} crt / {p_ret} pcs added. Stock restored.")
                            ActivityLog.record(
                                event_type=ActivityLog.RETURN, promoter_name=dep.promoter.name,
                                product_name=dep.product.name, cartons=c_ret, pieces=p_ret,
                                label=f"Returned {c_ret} crt / {p_ret} pcs — not sold", shop=shop,
                            )
                        except ValidationError as e:
                            msg = e.messages[0] if hasattr(e, "messages") else str(e)
                            messages.error(request, f"❌ {msg}")

        elif action == "adjust_entry":
            dep = DailyDeployment.objects.filter(shop=shop, id=request.POST.get("deployment_id")).first()
            target = request.POST.get("target")
            unit_type = request.POST.get("unit_type")
            qty = int(request.POST.get("quantity", "0") or 0)
            if not dep or qty <= 0:
                messages.error(request, "❌ Invalid adjustment.")
            else:
                try:
                    nc_taken, np_taken, nc_ret, np_ret = dep.cartons_taken, dep.pieces_taken, dep.cartons_returned, dep.pieces_returned
                    adj_cartons, adj_pieces = 0, 0
                    if target == "dispatched":
                        if unit_type == "cartons":
                            if qty > dep.cartons_taken: raise ValidationError("Cannot remove more cartons than dispatched.")
                            nc_taken -= qty; adj_cartons = qty
                        else:
                            if qty > dep.pieces_taken: raise ValidationError("Cannot remove more pieces than dispatched.")
                            np_taken -= qty; adj_pieces = qty
                    else:
                        if unit_type == "cartons":
                            if qty > dep.cartons_returned: raise ValidationError("Cannot remove more cartons than returned.")
                            nc_ret -= qty; adj_cartons = qty
                        else:
                            if qty > dep.pieces_returned: raise ValidationError("Cannot remove more pieces than returned.")
                            np_ret -= qty; adj_pieces = qty
                    promoter_name, product_name, biz_date = dep.promoter.name, dep.product.name, dep.date
                    items_per = int(dep.product.items_per_carton or 1)
                    if ((nc_ret * items_per) + np_ret) > ((nc_taken * items_per) + np_taken):
                        raise ValidationError("After this correction, returns would exceed dispatches.")
                    if nc_taken == 0 and np_taken == 0:
                        dep.delete()
                        messages.success(request, "↩️ Last unit(s) undone. Row cleared and stock restored.")
                        ActivityLog.record(
                            event_type=ActivityLog.CORRECTION, promoter_name=promoter_name,
                            product_name=product_name, cartons=adj_cartons, pieces=adj_pieces,
                            label="Undo: mistake fixed, stock restored", business_date=biz_date, shop=shop,
                        )
                    else:
                        DailyDeployment(
                            pk=dep.pk, shop=shop, promoter_id=dep.promoter_id, product_id=dep.product_id,
                            date=dep.date, cartons_taken=nc_taken, pieces_taken=np_taken,
                            cartons_returned=nc_ret, pieces_returned=np_ret,
                        ).save()
                        messages.success(request, "🎯 Entry adjusted and stock re-balanced!")
                        side = "dispatched" if target == "dispatched" else "returned"
                        ActivityLog.record(
                            event_type=ActivityLog.CORRECTION, promoter_name=promoter_name,
                            product_name=product_name, cartons=adj_cartons, pieces=adj_pieces,
                            label=f"Correction: removed {adj_cartons} crt / {adj_pieces} pcs from {side}",
                            business_date=biz_date, shop=shop,
                        )
                except ValidationError as e:
                    msg = e.messages[0] if hasattr(e, "messages") else str(e)
                    messages.error(request, f" {msg}")

        elif action == "nuke_entry":
            dep = DailyDeployment.objects.filter(shop=shop, id=request.POST.get("deployment_id")).first()
            if not dep:
                messages.error(request, "❌ Entry not found.")
            else:
                promoter_name, product_name, product, biz_date = dep.promoter.name, dep.product.name, dep.product, dep.date
                old_cash = dep.cash_owed
                orig_c_taken, orig_p_taken = dep.cartons_taken, dep.pieces_taken
                orig_c_ret, orig_p_ret = dep.cartons_returned, dep.pieces_returned
                items_per = int(product.items_per_carton or 1)
                taken_pcs = (orig_c_taken * items_per) + orig_p_taken
                ret_pcs = (orig_c_ret * items_per) + orig_p_ret
                sold_pcs = taken_pcs - ret_pcs
                if sold_pcs > 0:
                    product.initial_stock = max(0, int(product.initial_stock or 0) - sold_pcs)
                    product.save(update_fields=["initial_stock"])
                dep.delete()
                if sold_pcs > 0:
                    msg = f"🗑️ Cleared {product_name} for {promoter_name}. Treated as sold ({sold_pcs} pcs)."
                    label = f"Nuked (sold/accounted) — {orig_c_taken} crt / {orig_p_taken} pcs. Cash was ₵{old_cash}."
                else:
                    msg = f"🗑️ Cleared {product_name} for {promoter_name}. Fully returned — bookkeeping only."
                    label = f"Nuked (fully returned) — {orig_c_taken} crt / {orig_p_taken} pcs. Cash ₵{old_cash}."
                messages.success(request, msg)
                ActivityLog.record(
                    event_type=ActivityLog.DELETE, promoter_name=promoter_name,
                    product_name=product_name, cartons=orig_c_taken, pieces=orig_p_taken,
                    cash_amount=old_cash, label=label, business_date=biz_date, shop=shop,
                )

        return redirect("dashboard")

    # ---------- BUILD DISPLAY DATA ----------
    for p in Product.objects.filter(shop=shop):
        p.recalculate()

    deployments = DailyDeployment.objects.filter(shop=shop, date=date.today()).order_by("-id")
    promoter_records = {}
    for d in deployments:
        key = d.promoter.id
        if key not in promoter_records:
            promoter_records[key] = {"promoter_name": d.promoter.name, "items": [], "grand_total": Decimal("0.00")}
        promoter_records[key]["items"].append(d)
        promoter_records[key]["grand_total"] += d.cash_owed

    # Calculate cash outstanding properly
    cash_outstanding = sum(c["grand_total"] for c in promoter_records.values())

    context = {
        "products": Product.objects.filter(shop=shop),
        "promoters": Promoter.objects.filter(shop=shop),
        "promoter_containers": list(promoter_records.values()),
        "cash_outstanding": cash_outstanding,
        "shop": shop,
    }
    return render(request, "main/dashboard.html", context)


def leaderboard_page(request):
    """Separate leaderboard page — shows positions only, no prices."""
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

    leaderboard = (
        DailyDeployment.objects
        .filter(shop=shop, date__gte=start_date)
        .values("promoter__id", "promoter__name")
        .annotate(total_cash=Sum("cash_owed"))
        .order_by("-total_cash")
    )

    context = {
        "leaderboard": leaderboard,
        "active_window": window,
        "shop": shop,
    }
    return render(request, "main/leaderboard.html", context)


def statements(request):
    shop = get_active_shop(request)
    if not shop:
        return redirect("setup_shop")
    date_str = request.GET.get("date", "").strip()
    if date_str:
        try:
            selected = date.fromisoformat(date_str)
        except ValueError:
            selected = date.today()
    else:
        selected = date.today()
    event_filter = request.GET.get("event", "").strip()
    promoter_filter = request.GET.get("promoter", "").strip()
    logs_qs = ActivityLog.objects.filter(shop=shop, business_date=selected)
    promoter_names = list(
        logs_qs.order_by("promoter_name").values_list("promoter_name", flat=True).distinct()
    )
    if event_filter in ("dispatch", "return", "correction", "delete"):
        logs_qs = logs_qs.filter(event_type=event_filter)
    if promoter_filter:
        logs_qs = logs_qs.filter(promoter_name=promoter_filter)
    logs = logs_qs.order_by("-created_at")
    today = date.today()
    yesterday = today - timedelta(days=1)
    context = {
        "selected_date": selected, "selected_date_str": selected.isoformat(),
        "today_str": today.isoformat(), "yesterday_str": yesterday.isoformat(),
        "is_today": selected == today, "logs": logs, "entry_count": logs.count(),
        "promoter_names": promoter_names, "event_filter": event_filter, "promoter_filter": promoter_filter,
    }
    return render(request, "main/statement.html", context)