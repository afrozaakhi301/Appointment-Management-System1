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
def notification_detail_view(request, notification_id):
    """
    Displays full details of a specific notification for both Clients and Engineers.
    Automatically marks unread notification as read upon viewing.
    """
    notification = get_object_or_404(
        Notification.objects.select_related(
            "appointment__client__client_profile",
            "appointment__engineer__engineer_profile",
            "appointment__service",
            "user"
        ),
        id=notification_id,
        user=request.user
    )

    # Auto mark as read if viewing for the first time
    if not notification.is_read:
        notification.is_read = True
        notification.save(update_fields=["is_read"])

    return render(
        request,
        "notifications/notification_detail.html",
        {
            "notification": notification,
            "appointment": notification.appointment,
        }
    )


@login_required
def toggle_notification_read_view(request, notification_id):
    """
    Toggles the read/unread status of a notification for the logged-in user.
    """
    notification = get_object_or_404(Notification, id=notification_id, user=request.user)
    notification.is_read = not notification.is_read
    notification.save(update_fields=["is_read"])
    status_str = "Read" if notification.is_read else "Unread"
    messages.success(request, f"Notification marked as {status_str}.")
    next_url = request.GET.get("next")
    if next_url:
        return redirect(next_url)
    return redirect("notifications:notification_list")


@login_required
def delete_notification_view(request, notification_id):
    """
    Deletes a notification owned by the logged-in user.
    """
    notification = get_object_or_404(Notification, id=notification_id, user=request.user)
    notification.delete()
    messages.success(request, "Notification removed successfully.")
    return redirect("notifications:notification_list")


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

