from datetime import datetime
from django.contrib import messages
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from accounts.decorators import engineer_required
from accounts.models import User
from dashboard.utils import log_activity
from .forms import EngineerAvailabilityForm, EngineerLeaveForm
from .models import EngineerAvailability, EngineerLeave


@engineer_required
def manage_availability_view(request):
    engineer = request.user
    availabilities = EngineerAvailability.objects.filter(engineer=engineer).order_by("day_of_week", "start_time")

    if request.method == "POST":
        action = request.POST.get("action")
        if action == "delete":
            item_id = request.POST.get("item_id")
            item = get_object_or_404(EngineerAvailability, id=item_id, engineer=engineer)
            day_name = item.get_day_of_week_display()
            time_range = f"{item.start_time.strftime('%H:%M')} - {item.end_time.strftime('%H:%M')}"
            item.delete()
            log_activity(engineer, f"Deleted availability slot: {day_name} ({time_range})")
            messages.success(request, f"Removed availability slot for {day_name} ({time_range}).")
            return redirect("scheduling:manage_availability")
        else:
            form = EngineerAvailabilityForm(request.POST)
            if form.is_valid():
                availability = form.save(commit=False)
                availability.engineer = engineer
                availability.save()
                day_name = availability.get_day_of_week_display()
                time_range = f"{availability.start_time.strftime('%H:%M')} - {availability.end_time.strftime('%H:%M')}"
                log_activity(engineer, f"Added availability slot: {day_name} ({time_range})")
                messages.success(request, f"Added working hours for {day_name} ({time_range}).")
                return redirect("scheduling:manage_availability")
            else:
                messages.error(request, "Please correct the errors in the availability form.")
    else:
        form = EngineerAvailabilityForm()

    return render(
        request,
        "scheduling/manage_availability.html",
        {
            "form": form,
            "availabilities": availabilities,
        }
    )


@engineer_required
def manage_leave_view(request):
    engineer = request.user
    leaves = EngineerLeave.objects.filter(engineer=engineer).order_by("-start_date")

    if request.method == "POST":
        action = request.POST.get("action")
        if action == "delete":
            item_id = request.POST.get("item_id")
            item = get_object_or_404(EngineerLeave, id=item_id, engineer=engineer)
            date_range = f"{item.start_date} to {item.end_date}"
            item.delete()
            log_activity(engineer, f"Deleted leave: {date_range}")
            messages.success(request, f"Cancelled leave record ({date_range}).")
            return redirect("scheduling:manage_leave")
        else:
            form = EngineerLeaveForm(request.POST)
            if form.is_valid():
                leave = form.save(commit=False)
                leave.engineer = engineer
                leave.save()
                log_activity(engineer, f"Scheduled leave: {leave.start_date} to {leave.end_date}")
                messages.success(request, f"Leave scheduled from {leave.start_date} to {leave.end_date}.")
                return redirect("scheduling:manage_leave")
            else:
                messages.error(request, "Please correct the errors in the leave form.")
    else:
        form = EngineerLeaveForm()

    return render(
        request,
        "scheduling/manage_leave.html",
        {
            "form": form,
            "leaves": leaves,
        }
    )


def api_engineer_schedule_check(request, engineer_id):
    """
    JSON API for dynamic frontend checking of engineer schedule on a given date.
    Returns working slots, booked appointments, and suggested available times.
    """
    from datetime import datetime, timedelta

    date_str = request.GET.get("date")
    if not date_str:
        return JsonResponse({"error": "Missing date parameter"}, status=400)

    try:
        query_date = datetime.strptime(date_str, "%Y-%m-%d").date()
    except ValueError:
        return JsonResponse({"error": "Invalid date format, expected YYYY-MM-DD"}, status=400)

    engineer = get_object_or_404(User, id=engineer_id, role=User.Role.ENGINEER, is_active=True)

    # 1. Check leave
    leave_record = EngineerLeave.objects.filter(
        engineer=engineer,
        start_date__lte=query_date,
        end_date__gte=query_date
    ).first()

    if leave_record:
        return JsonResponse({
            "status": "on_leave",
            "message": f"Engineer {engineer.get_full_name() or engineer.username} is on leave on {query_date.strftime('%b %d, %Y')} (Leave: {leave_record.start_date.strftime('%b %d')} - {leave_record.end_date.strftime('%b %d, %Y')}).",
            "leave_start": leave_record.start_date.strftime("%Y-%m-%d"),
            "leave_end": leave_record.end_date.strftime("%Y-%m-%d"),
        })

    # Fetch all weekly schedule for fallback recommendations
    all_avail = EngineerAvailability.objects.filter(engineer=engineer).order_by("day_of_week", "start_time")
    weekly_schedule = [
        {
            "day": a.get_day_of_week_display(),
            "day_num": a.day_of_week,
            "start": a.start_time.strftime("%H:%M"),
            "end": a.end_time.strftime("%H:%M"),
            "label": f"{a.get_day_of_week_display()} ({a.start_time.strftime('%I:%M %p')} - {a.end_time.strftime('%I:%M %p')})"
        }
        for a in all_avail
    ]

    # 2. Check weekday availability
    weekday = query_date.weekday()
    availabilities = EngineerAvailability.objects.filter(engineer=engineer, day_of_week=weekday).order_by("start_time")
    if not availabilities.exists():
        day_name = query_date.strftime("%A")
        schedule_str = ", ".join([w["label"] for w in weekly_schedule]) if weekly_schedule else "No working days configured"
        return JsonResponse({
            "status": "not_available",
            "message": f"Engineer does not work on {day_name}s. Available schedule: {schedule_str}.",
            "weekly_schedule": weekly_schedule
        })

    working_slots = [
        {
            "start": a.start_time.strftime("%H:%M"),
            "end": a.end_time.strftime("%H:%M"),
            "label": f"{a.start_time.strftime('%I:%M %p')} - {a.end_time.strftime('%I:%M %p')}"
        }
        for a in availabilities
    ]

    # 3. Fetch existing blocking appointments for that date
    from appointments.models import Appointment
    blocking_appointments = list(Appointment.objects.filter(
        engineer=engineer,
        appointment_date=query_date,
        status__in=[Appointment.Status.PENDING, Appointment.Status.APPROVED, Appointment.Status.RESCHEDULED]
    ).values("id", "start_time", "end_time", "status"))

    booked_slots = [
        {
            "id": appt["id"],
            "start": appt["start_time"].strftime("%H:%M"),
            "end": appt["end_time"].strftime("%H:%M"),
            "status": appt["status"]
        }
        for appt in blocking_appointments
    ]

    # 4. Generate intelligent suggested 1-hour time slots
    suggested_slots = []
    for a in availabilities:
        cur_dt = datetime.combine(query_date, a.start_time)
        slot_end_dt = datetime.combine(query_date, a.end_time)
        while cur_dt + timedelta(minutes=60) <= slot_end_dt:
            cand_start = cur_dt.time()
            cand_end = (cur_dt + timedelta(minutes=60)).time()

            # Check collision with booked slots
            conflict = False
            for b in blocking_appointments:
                if cand_start < b["end_time"] and cand_end > b["start_time"]:
                    conflict = True
                    break

            if not conflict:
                suggested_slots.append({
                    "start": cand_start.strftime("%H:%M"),
                    "end": cand_end.strftime("%H:%M"),
                    "label": f"{cand_start.strftime('%I:%M %p')} - {cand_end.strftime('%I:%M %p')}"
                })

            cur_dt += timedelta(minutes=60)

    return JsonResponse({
        "status": "available",
        "working_slots": working_slots,
        "booked_slots": booked_slots,
        "suggested_slots": suggested_slots,
        "day_name": query_date.strftime("%A"),
        "weekly_schedule": weekly_schedule
    })
