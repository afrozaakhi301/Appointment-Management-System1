import calendar
from datetime import date, datetime, timedelta
from django.db.models import Avg, Count, Q
from django.utils import timezone
from accounts.models import User
from appointments.models import Appointment


def get_completion_kpis(engineer=None, service=None, reference_date=None):
    """
    Computes summary KPI numbers for completed appointments:
    - Done Today vs Yesterday
    - Done This Week (Mon-Sun) vs Last Week
    - Done This Month vs Last Month
    - Done This Year & Total All-Time
    """
    if reference_date is None:
        reference_date = timezone.localdate() if hasattr(timezone, "localdate") else date.today()

    qs = Appointment.objects.filter(status=Appointment.Status.COMPLETED)

    if engineer:
        qs = qs.filter(engineer=engineer)
    if service:
        qs = qs.filter(service=service)

    today = reference_date
    yesterday = today - timedelta(days=1)

    # 1. Daily metrics
    done_today = qs.filter(appointment_date=today).count()
    done_yesterday = qs.filter(appointment_date=yesterday).count()
    daily_diff = done_today - done_yesterday

    # 2. Weekly metrics (Monday = 0, Sunday = 6)
    curr_week_start = today - timedelta(days=today.weekday())
    curr_week_end = curr_week_start + timedelta(days=6)
    last_week_start = curr_week_start - timedelta(days=7)
    last_week_end = curr_week_start - timedelta(days=1)

    done_this_week = qs.filter(appointment_date__gte=curr_week_start, appointment_date__lte=curr_week_end).count()
    done_last_week = qs.filter(appointment_date__gte=last_week_start, appointment_date__lte=last_week_end).count()
    weekly_diff = done_this_week - done_last_week
    weekly_pct_change = 0
    if done_last_week > 0:
        weekly_pct_change = round(((done_this_week - done_last_week) / done_last_week) * 100, 1)

    # 3. Monthly metrics
    curr_month_start = date(today.year, today.month, 1)
    if today.month == 12:
        next_month_start = date(today.year + 1, 1, 1)
    else:
        next_month_start = date(today.year, today.month + 1, 1)
    curr_month_end = next_month_start - timedelta(days=1)

    if today.month == 1:
        last_month_start = date(today.year - 1, 12, 1)
        last_month_end = date(today.year - 1, 12, 31)
    else:
        last_month_start = date(today.year, today.month - 1, 1)
        last_month_end = curr_month_start - timedelta(days=1)

    done_this_month = qs.filter(appointment_date__gte=curr_month_start, appointment_date__lte=curr_month_end).count()
    done_last_month = qs.filter(appointment_date__gte=last_month_start, appointment_date__lte=last_month_end).count()
    monthly_diff = done_this_month - done_last_month
    monthly_pct_change = 0
    if done_last_month > 0:
        monthly_pct_change = round(((done_this_month - done_last_month) / done_last_month) * 100, 1)

    # 4. Yearly & Total metrics
    curr_year_start = date(today.year, 1, 1)
    curr_year_end = date(today.year, 12, 31)
    done_this_year = qs.filter(appointment_date__gte=curr_year_start, appointment_date__lte=curr_year_end).count()
    total_completed = qs.count()

    return {
        "today": today,
        "done_today": done_today,
        "done_yesterday": done_yesterday,
        "daily_diff": daily_diff,
        "curr_week_start": curr_week_start,
        "curr_week_end": curr_week_end,
        "done_this_week": done_this_week,
        "done_last_week": done_last_week,
        "weekly_diff": weekly_diff,
        "weekly_pct_change": weekly_pct_change,
        "curr_month_start": curr_month_start,
        "curr_month_end": curr_month_end,
        "done_this_month": done_this_month,
        "done_last_month": done_last_month,
        "monthly_diff": monthly_diff,
        "monthly_pct_change": monthly_pct_change,
        "done_this_year": done_this_year,
        "total_completed": total_completed,
    }


def get_daily_completion_breakdown(engineer=None, service=None, year=None, month=None, days_back=30, reference_date=None):
    """
    Returns day-by-day completed appointment counts and list.
    If year & month are specified, returns daily breakdown for all days of that month.
    Otherwise, returns breakdown for the past `days_back` days up to reference_date.
    """
    if reference_date is None:
        reference_date = timezone.localdate() if hasattr(timezone, "localdate") else date.today()

    qs = Appointment.objects.filter(status=Appointment.Status.COMPLETED).select_related("client", "engineer", "service")

    if engineer:
        qs = qs.filter(engineer=engineer)
    if service:
        qs = qs.filter(service=service)

    daily_list = []
    
    if year and month:
        year = int(year)
        month = int(month)
        _, num_days = calendar.monthrange(year, month)
        start_date = date(year, month, 1)
        end_date = date(year, month, num_days)
    else:
        end_date = reference_date
        start_date = end_date - timedelta(days=days_back - 1)

    appts = qs.filter(appointment_date__gte=start_date, appointment_date__lte=end_date).order_by("-appointment_date", "-start_time")
    
    # Map by date
    appts_by_date = {}
    for a in appts:
        appts_by_date.setdefault(a.appointment_date, []).append(a)

    curr = start_date
    while curr <= end_date:
        items = appts_by_date.get(curr, [])
        daily_list.append({
            "date": curr,
            "date_str": curr.strftime("%Y-%m-%d"),
            "formatted_date": curr.strftime("%b %d, %Y"),
            "short_label": curr.strftime("%b %d"),
            "day_name": curr.strftime("%A"),
            "count": len(items),
            "appointments": items,
        })
        curr += timedelta(days=1)

    return {
        "start_date": start_date,
        "end_date": end_date,
        "daily_breakdown": daily_list,
        "chart_labels": [d["short_label"] for d in daily_list],
        "chart_data": [d["count"] for d in daily_list],
        "total_in_period": sum(d["count"] for d in daily_list),
        "appointments": appts,
    }


def get_weekly_completion_breakdown(engineer=None, service=None, weeks_back=12, reference_date=None, year=None):
    """
    Returns weekly breakdown of completed appointments for the past `weeks_back` weeks,
    or across all weeks of a given year.
    Each week is represented by its start date (Monday) and end date (Sunday).
    """
    if reference_date is None:
        reference_date = timezone.localdate() if hasattr(timezone, "localdate") else date.today()

    qs = Appointment.objects.filter(status=Appointment.Status.COMPLETED).select_related("client", "engineer", "service")

    if engineer:
        qs = qs.filter(engineer=engineer)
    if service:
        qs = qs.filter(service=service)

    # Current week Monday
    curr_mon = reference_date - timedelta(days=reference_date.weekday())
    
    weekly_list = []
    
    if year:
        year = int(year)
        # Find first Monday of year or week 1
        d = date(year, 1, 1)
        d_mon = d - timedelta(days=d.weekday())
        # iterate weeks until year changes
        while d_mon.year <= year or (d_mon + timedelta(days=6)).year == year:
            w_start = d_mon
            w_end = w_start + timedelta(days=6)
            iso_year, iso_week, _ = w_start.isocalendar()
            weekly_list.append({
                "week_num": iso_week,
                "year": iso_year,
                "start_date": w_start,
                "end_date": w_end,
                "label": f"Wk {iso_week} ({w_start.strftime('%b %d')} - {w_end.strftime('%b %d')})",
                "short_label": f"W{iso_week} ({w_start.strftime('%b %d')})",
                "count": 0,
                "appointments": [],
            })
            d_mon += timedelta(days=7)
            if d_mon.year > year and (d_mon + timedelta(days=6)).year > year:
                break
    else:
        # past N weeks up to current week
        for i in range(weeks_back - 1, -1, -1):
            w_start = curr_mon - timedelta(weeks=i)
            w_end = w_start + timedelta(days=6)
            iso_year, iso_week, _ = w_start.isocalendar()
            weekly_list.append({
                "week_num": iso_week,
                "year": iso_year,
                "start_date": w_start,
                "end_date": w_end,
                "label": f"Wk {iso_week} ({w_start.strftime('%b %d')} - {w_end.strftime('%b %d')})",
                "short_label": f"W{iso_week} ({w_start.strftime('%b %d')})",
                "count": 0,
                "appointments": [],
            })

    if weekly_list:
        start_bound = weekly_list[0]["start_date"]
        end_bound = weekly_list[-1]["end_date"]
        appts = qs.filter(appointment_date__gte=start_bound, appointment_date__lte=end_bound).order_by("-appointment_date", "-start_time")
        
        for a in appts:
            for w in weekly_list:
                if w["start_date"] <= a.appointment_date <= w["end_date"]:
                    w["count"] += 1
                    w["appointments"].append(a)
                    break
    else:
        appts = qs.none()

    return {
        "weekly_breakdown": weekly_list,
        "chart_labels": [w["short_label"] for w in weekly_list],
        "chart_data": [w["count"] for w in weekly_list],
        "total_in_period": sum(w["count"] for w in weekly_list),
        "appointments": appts,
    }


def get_monthly_completion_breakdown(engineer=None, service=None, year=None, reference_date=None):
    """
    Returns monthly breakdown of completed appointments for all 12 months of the target year.
    Defaults to current year.
    """
    if reference_date is None:
        reference_date = timezone.localdate() if hasattr(timezone, "localdate") else date.today()

    if year is None:
        year = reference_date.year
    else:
        year = int(year)

    qs = Appointment.objects.filter(status=Appointment.Status.COMPLETED).select_related("client", "engineer", "service")

    if engineer:
        qs = qs.filter(engineer=engineer)
    if service:
        qs = qs.filter(service=service)

    start_date = date(year, 1, 1)
    end_date = date(year, 12, 31)

    appts = qs.filter(appointment_date__gte=start_date, appointment_date__lte=end_date).order_by("-appointment_date", "-start_time")

    monthly_list = []
    for m in range(1, 13):
        m_name = calendar.month_name[m]
        m_abbr = calendar.month_abbr[m]
        _, num_days = calendar.monthrange(year, m)
        m_start = date(year, m, 1)
        m_end = date(year, m, num_days)
        m_appts = [a for a in appts if a.appointment_date.month == m]
        
        monthly_list.append({
            "month_num": m,
            "month_name": m_name,
            "month_abbr": m_abbr,
            "year": year,
            "start_date": m_start,
            "end_date": m_end,
            "count": len(m_appts),
            "appointments": m_appts,
            "is_current": (year == reference_date.year and m == reference_date.month),
        })

    return {
        "year": year,
        "monthly_breakdown": monthly_list,
        "chart_labels": [m["month_abbr"] for m in monthly_list],
        "chart_data": [m["count"] for m in monthly_list],
        "total_in_period": sum(m["count"] for m in monthly_list),
        "appointments": appts,
    }


def get_service_and_engineer_breakdown(engineer=None, service=None, start_date=None, end_date=None):
    """
    Returns breakdown of completed appointments grouped by service and engineer.
    """
    qs = Appointment.objects.filter(status=Appointment.Status.COMPLETED)
    if engineer:
        qs = qs.filter(engineer=engineer)
    if service:
        qs = qs.filter(service=service)
    if start_date:
        qs = qs.filter(appointment_date__gte=start_date)
    if end_date:
        qs = qs.filter(appointment_date__lte=end_date)

    service_breakdown = (
        qs.values("service__name")
        .annotate(count=Count("id"))
        .order_by("-count")
    )

    engineer_breakdown = (
        qs.values("engineer__username", "engineer__first_name", "engineer__last_name")
        .annotate(count=Count("id"))
        .order_by("-count")
    )

    return {
        "service_breakdown": list(service_breakdown),
        "engineer_breakdown": list(engineer_breakdown),
    }


def get_engineer_workload_distribution():
    """
    Computes workload and capacity balance across active engineers:
    - active_load: Total sessions in Pending, Approved, or Rescheduled status.
    - completed_count: Total completed sessions.
    - avg_rating & review_count: Feedback metrics.
    - capacity_pct: Percentage of daily max threshold (4 sessions), capped at 100%.
    - status_label / status_badge / progress_bar:
        * 'Overloaded' (active_load >= 4): Red
        * 'Optimal' (2 <= active_load <= 3): Green
        * 'Available' (active_load <= 1): Blue / Info
    """
    engineers = User.objects.filter(role=User.Role.ENGINEER, is_active=True).annotate(
        active_load=Count(
            "engineer_appointments",
            filter=Q(engineer_appointments__status__in=[
                Appointment.Status.PENDING,
                Appointment.Status.APPROVED,
                Appointment.Status.RESCHEDULED,
            ]),
            distinct=True,
        ),
        completed_count=Count(
            "engineer_appointments",
            filter=Q(engineer_appointments__status=Appointment.Status.COMPLETED),
            distinct=True,
        ),
        avg_rating=Avg("engineer_appointments__feedback__rating"),
        review_count=Count("engineer_appointments__feedback", distinct=True),
    ).order_by("-active_load", "first_name", "last_name")

    workload_data = []
    for eng in engineers:
        active = eng.active_load
        capacity_pct = min(100, int((active / 4.0) * 100))

        if active >= 4:
            status_label = "Overloaded"
            status_badge = "bg-danger"
            progress_bar = "bg-danger"
        elif active >= 2:
            status_label = "Optimal"
            status_badge = "bg-success"
            progress_bar = "bg-success"
        else:
            status_label = "Available"
            status_badge = "bg-info"
            progress_bar = "bg-info"

        workload_data.append({
            "engineer": eng,
            "active_load": active,
            "completed_count": eng.completed_count,
            "avg_rating": round(eng.avg_rating, 1) if eng.avg_rating else 0.0,
            "review_count": eng.review_count,
            "capacity_pct": capacity_pct,
            "status_label": status_label,
            "status_badge": status_badge,
            "progress_bar": progress_bar,
        })

    return workload_data
