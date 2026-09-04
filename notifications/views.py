from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import EmptyPage, PageNotAnInteger, Paginator
from django.shortcuts import get_object_or_404, redirect, render
from .models import Notification


@login_required
def notification_list_view(request):
    status_filter = request.GET.get("status", "all").strip().lower()
    query = request.GET.get("q", "").strip()

    base_qs = Notification.objects.filter(user=request.user).select_related("appointment").order_by("-created_at")
    
    total_count = base_qs.count()
    unread_count = base_qs.filter(is_read=False).count()
    read_count = base_qs.filter(is_read=True).count()

    filtered_qs = base_qs
    if status_filter == "unread":
        filtered_qs = filtered_qs.filter(is_read=False)
    elif status_filter == "read":
        filtered_qs = filtered_qs.filter(is_read=True)

    if query:
        filtered_qs = filtered_qs.filter(message__icontains=query)

    paginator = Paginator(filtered_qs, 10)  # 10 notifications per page
    page = request.GET.get("page", 1)

    try:
        notifications = paginator.page(page)
    except PageNotAnInteger:
        notifications = paginator.page(1)
    except EmptyPage:
        notifications = paginator.page(paginator.num_pages)

    return render(
        request,
        "notifications/notification_list.html",
        {
            "notifications": notifications,
            "status_filter": status_filter,
            "query": query,
            "total_count": total_count,
            "unread_count": unread_count,
            "read_count": read_count,
            "filtered_count": filtered_qs.count(),
        }
    )


@login_required
def mark_as_read_view(request, notification_id):
    notification = get_object_or_404(Notification, id=notification_id, user=request.user)
    notification.is_read = True
    notification.save()
    
    if notification.appointment:
        return redirect("appointments:appointment_detail", appointment_id=notification.appointment.id)
    return redirect("notifications:notification_list")


@login_required
def mark_all_as_read_view(request):
    updated_count = Notification.objects.filter(user=request.user, is_read=False).update(is_read=True)
    if updated_count > 0:
        messages.success(request, f"Marked {updated_count} notification(s) as read.")
    else:
        messages.info(request, "All notifications are already marked as read.")
    return redirect("notifications:notification_list")
