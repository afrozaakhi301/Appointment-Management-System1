import csv
import json
from datetime import date, timedelta
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Avg, Count, Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from accounts.decorators import admin_required, client_required, engineer_required
from accounts.forms import (
    AdminCreationForm,
    AdminEngineerCreationForm,
    ClientProfileUpdateForm,
    EngineerProfileUpdateForm,
    UserUpdateForm,
)
from accounts.models import ClientProfile, EngineerProfile, User
from appointments.models import Appointment
from feedback.models import Feedback
from notifications.utils import create_notification
from scheduling.models import EngineerAvailability, EngineerLeave
from services.forms import AdminEngineerExpertiseForm, ExpertiseForm, ServiceForm
from services.models import EngineerExpertise, Expertise, Service
from .analytics import (
    get_completion_kpis,
    get_daily_completion_breakdown,
    get_weekly_completion_breakdown,
    get_monthly_completion_breakdown,
    get_service_and_engineer_breakdown,
)
from .models import ActivityLog
from .utils import log_activity


# ==========================================
# CLIENT DASHBOARD
# ==========================================

@client_required
def client_dashboard(request):
    client = request.user
    appointments = Appointment.objects.filter(client=client).select_related("engineer", "service")

    total_count = appointments.count()
    pending_count = appointments.filter(status=Appointment.Status.PENDING).count()
    upcoming_count = appointments.filter(status__in=[Appointment.Status.APPROVED, Appointment.Status.RESCHEDULED]).count()
    completed_count = appointments.filter(status=Appointment.Status.COMPLETED).count()

    next_appointment = appointments.filter(
        status__in=[Appointment.Status.APPROVED, Appointment.Status.RESCHEDULED],
        appointment_date__gte=date.today()
    ).order_by("appointment_date", "start_time").first()

    recent_appointments = appointments.order_by("-created_at")[:5]

    return render(
        request,
        "dashboard/client_dashboard.html",
        {
            "total_count": total_count,
            "pending_count": pending_count,
            "upcoming_count": upcoming_count,
            "completed_count": completed_count,
            "next_appointment": next_appointment,
            "recent_appointments": recent_appointments,
        }
    )


# ==========================================
# ENGINEER DASHBOARD
# ==========================================

@engineer_required
def engineer_dashboard(request):
    engineer = request.user
    appointments = Appointment.objects.filter(engineer=engineer).select_related("client", "service")

    pending_requests = appointments.filter(status=Appointment.Status.PENDING).order_by("appointment_date", "start_time")
    pending_count = pending_requests.count()

    upcoming_appointments = appointments.filter(
        status__in=[Appointment.Status.APPROVED, Appointment.Status.RESCHEDULED],
        appointment_date__gte=date.today()
    ).order_by("appointment_date", "start_time")[:5]
    upcoming_count = upcoming_appointments.count()

    completed_count = appointments.filter(status=Appointment.Status.COMPLETED).count()

    # Feedback aggregation
    feedbacks = Feedback.objects.filter(appointment__engineer=engineer)
    avg_rating = feedbacks.aggregate(Avg("rating"))["rating__avg"] or 0
    feedback_count = feedbacks.count()

    # Personal completion tracking KPIs (daily, weekly, monthly)
    completion_kpis = get_completion_kpis(engineer=engineer)

    # Engineer skills summary
    verified_skills_count = EngineerExpertise.objects.filter(engineer=engineer, status=EngineerExpertise.VerificationStatus.APPROVED).count()
    pending_skills_count = EngineerExpertise.objects.filter(engineer=engineer, status=EngineerExpertise.VerificationStatus.PENDING).count()

    return render(
        request,
        "dashboard/engineer_dashboard.html",
        {
            "pending_requests": pending_requests[:5],
            "pending_count": pending_count,
            "upcoming_appointments": upcoming_appointments,
            "upcoming_count": upcoming_count,
            "completed_count": completed_count,
            "avg_rating": round(avg_rating, 1),
            "feedback_count": feedback_count,
            "completion_kpis": completion_kpis,
            "verified_skills_count": verified_skills_count,
            "pending_skills_count": pending_skills_count,
        }
    )


# ==========================================
# ADMIN DASHBOARD & MANAGEMENT
# ==========================================

@admin_required
def admin_dashboard(request):
    total_clients = User.objects.filter(role=User.Role.CLIENT).count()
    total_engineers = User.objects.filter(role=User.Role.ENGINEER).count()
    total_admins = User.objects.filter(role=User.Role.ADMIN).count()

    total_appointments = Appointment.objects.count()
    pending_appointments = Appointment.objects.filter(status=Appointment.Status.PENDING).count()
    approved_appointments = Appointment.objects.filter(status=Appointment.Status.APPROVED).count()
    completed_appointments = Appointment.objects.filter(status=Appointment.Status.COMPLETED).count()
    cancelled_appointments = Appointment.objects.filter(status__in=[Appointment.Status.CANCELLED, Appointment.Status.REJECTED]).count()

    # Pending skill verification requests
    pending_skill_requests_count = EngineerExpertise.objects.filter(status=EngineerExpertise.VerificationStatus.PENDING).count()

    recent_activities = ActivityLog.objects.select_related("user")[:10]
    recent_appointments = Appointment.objects.select_related("client", "engineer", "service").order_by("-created_at")[:6]

    completion_kpis = get_completion_kpis()

    return render(
        request,
        "dashboard/admin_dashboard.html",
        {
            "total_clients": total_clients,
            "total_engineers": total_engineers,
            "total_admins": total_admins,
            "total_appointments": total_appointments,
            "pending_appointments": pending_appointments,
            "approved_appointments": approved_appointments,
            "completed_appointments": completed_appointments,
            "cancelled_appointments": cancelled_appointments,
            "pending_skill_requests_count": pending_skill_requests_count,
            "recent_activities": recent_activities,
            "recent_appointments": recent_appointments,
            "completion_kpis": completion_kpis,
        }
    )


@admin_required
def admin_manage_clients(request):
    query = request.GET.get("q", "").strip()
    clients = User.objects.filter(role=User.Role.CLIENT).select_related("client_profile").order_by("-date_joined")

    if query:
        clients = clients.filter(
            Q(username__icontains=query) |
            Q(first_name__icontains=query) |
            Q(last_name__icontains=query) |
            Q(email__icontains=query) |
            Q(client_profile__organization__icontains=query)
        )

    if request.method == "POST":
        action = request.POST.get("action")
        client_id = request.POST.get("client_id")
        target_client = get_object_or_404(User, id=client_id, role=User.Role.CLIENT)
        if action == "toggle_active":
            target_client.is_active = not target_client.is_active
            target_client.save()
            state = "activated" if target_client.is_active else "deactivated"
            log_activity(request.user, f"Admin {state} client account: {target_client.username}")
            messages.success(request, f"Client {target_client.username} has been {state}.")
            return redirect("dashboard:manage_clients")

    return render(
        request,
        "dashboard/admin_manage_clients.html",
        {
            "clients": clients,
            "query": query,
        }
    )


@admin_required
def admin_manage_engineers(request):
    query = request.GET.get("q", "").strip()
    status_filter = request.GET.get("status", "").strip()
    engineers = User.objects.filter(role=User.Role.ENGINEER).select_related("engineer_profile").prefetch_related("engineer_expertises__expertise").order_by("-date_joined")

    if status_filter == "active":
        engineers = engineers.filter(is_active=True)
    elif status_filter == "inactive":
        engineers = engineers.filter(is_active=False)

    if query:
        engineers = engineers.filter(
            Q(username__icontains=query) |
            Q(first_name__icontains=query) |
            Q(last_name__icontains=query) |
            Q(email__icontains=query) |
            Q(engineer_profile__designation__icontains=query) |
            Q(engineer_expertises__expertise__name__icontains=query)
        ).distinct()

    if request.method == "POST":
        action = request.POST.get("action")
        engineer_id = request.POST.get("engineer_id")
        target_eng = get_object_or_404(User, id=engineer_id, role=User.Role.ENGINEER)
        if action == "toggle_active":
            target_eng.is_active = not target_eng.is_active
            target_eng.save()
            state = "activated" if target_eng.is_active else "deactivated"
            log_activity(request.user, f"Admin {state} engineer account: {target_eng.username}")
            messages.success(request, f"Engineer {target_eng.username} has been {state}.")
            return redirect("dashboard:manage_engineers")

    return render(
        request,
        "dashboard/admin_manage_engineers.html",
        {
            "engineers": engineers,
            "query": query,
            "status_filter": status_filter,
            "total_count": engineers.count(),
        }
    )


@admin_required
def admin_add_engineer(request):
    if request.method == "POST":
        form = AdminEngineerCreationForm(request.POST, request.FILES)
        if form.is_valid():
            engineer = form.save()
            log_activity(request.user, f"Created new engineer account: {engineer.username}")
            messages.success(request, f"Engineer '{engineer.get_full_name() or engineer.username}' has been successfully created!")
            return redirect("dashboard:manage_engineers")
        else:
            messages.error(request, "Failed to create engineer. Please check the form errors.")
    else:
        form = AdminEngineerCreationForm()

    return render(
        request,
        "dashboard/admin_add_engineer.html",
        {"form": form}
    )


@admin_required
def admin_add_admin(request):
    if request.method == "POST":
        form = AdminCreationForm(request.POST)
        if form.is_valid():
            new_admin = form.save()
            log_activity(request.user, f"Created new admin account: {new_admin.username}")
            messages.success(request, f"Admin account '{new_admin.username}' created successfully!")
            return redirect("dashboard:admin_dashboard")
        else:
            messages.error(request, "Failed to create admin. Please check the form errors.")
    else:
        form = AdminCreationForm()

    return render(
        request,
        "dashboard/admin_add_admin.html",
        {"form": form}
    )


@admin_required
def admin_manage_services(request):
    services = Service.objects.all()
    expertises = Expertise.objects.all()

    # Skill verifications & assignments
    pending_skill_requests = EngineerExpertise.objects.filter(
        status=EngineerExpertise.VerificationStatus.PENDING
    ).select_related("engineer__engineer_profile", "expertise").order_by("-created_at")

    engineer_expertises = EngineerExpertise.objects.select_related(
        "engineer", "expertise", "reviewed_by"
    ).order_by("-created_at", "engineer__username")

    service_form = ServiceForm()
    expertise_form = ExpertiseForm()
    assign_form = AdminEngineerExpertiseForm()

    if request.method == "POST":
        action = request.POST.get("action")

        if action == "approve_skill_request":
            ee_id = request.POST.get("ee_id")
            ee = get_object_or_404(EngineerExpertise, id=ee_id)
            ee.status = EngineerExpertise.VerificationStatus.APPROVED
            ee.reviewed_at = timezone.now()
            ee.reviewed_by = request.user
            ee.admin_notes = request.POST.get("admin_notes", "").strip()
            ee.save()

            create_notification(
                user=ee.engineer,
                message=f"Your skill verification request for '{ee.expertise.name}' ({ee.proficiency_level}) has been approved and verified by admin!"
            )
            log_activity(request.user, f"Approved skill verification: {ee.expertise.name} for {ee.engineer.username}")
            messages.success(request, f"Skill '{ee.expertise.name}' for {ee.engineer.get_full_name() or ee.engineer.username} has been verified and approved.")
            return redirect("dashboard:manage_services")

        elif action == "reject_skill_request":
            ee_id = request.POST.get("ee_id")
            ee = get_object_or_404(EngineerExpertise, id=ee_id)
            rejection_reason = request.POST.get("rejection_reason", "").strip()
            ee.status = EngineerExpertise.VerificationStatus.REJECTED
            ee.reviewed_at = timezone.now()
            ee.reviewed_by = request.user
            ee.admin_notes = rejection_reason
            ee.save()

            msg = f"Your skill verification request for '{ee.expertise.name}' was rejected by admin."
            if rejection_reason:
                msg += f" Note: {rejection_reason}"
            create_notification(user=ee.engineer, message=msg)

            log_activity(request.user, f"Rejected skill verification: {ee.expertise.name} for {ee.engineer.username}")
            messages.warning(request, f"Skill verification request for '{ee.expertise.name}' from {ee.engineer.get_full_name() or ee.engineer.username} was rejected.")
            return redirect("dashboard:manage_services")

        elif action == "create_service":
            form = ServiceForm(request.POST)
            if form.is_valid():
                svc = form.save()
                log_activity(request.user, f"Created service: {svc.name}")
                messages.success(request, f"Service '{svc.name}' created.")
                return redirect("dashboard:manage_services")
            else:
                messages.error(request, "Error creating service.")

        elif action == "toggle_service":
            svc_id = request.POST.get("service_id")
            svc = get_object_or_404(Service, id=svc_id)
            svc.is_active = not svc.is_active
            svc.save()
            log_activity(request.user, f"Toggled service active status: {svc.name} -> {svc.is_active}")
            messages.success(request, f"Service '{svc.name}' is now {'Active' if svc.is_active else 'Inactive'}.")
            return redirect("dashboard:manage_services")

        elif action == "delete_service":
            svc_id = request.POST.get("service_id")
            svc = get_object_or_404(Service, id=svc_id)
            if svc.appointments.exists():
                messages.error(request, f"Cannot delete service '{svc.name}' because it has linked appointments. You can set it to inactive instead.")
            else:
                svc_name = svc.name
                svc.delete()
                log_activity(request.user, f"Deleted service: {svc_name}")
                messages.success(request, f"Service '{svc_name}' deleted.")
            return redirect("dashboard:manage_services")

        elif action == "create_expertise":
            form = ExpertiseForm(request.POST)
            if form.is_valid():
                exp = form.save()
                log_activity(request.user, f"Created expertise: {exp.name}")
                messages.success(request, f"Expertise category '{exp.name}' created.")
                return redirect("dashboard:manage_services")
            else:
                messages.error(request, "Error creating expertise.")

        elif action == "delete_expertise":
            exp_id = request.POST.get("expertise_id")
            exp = get_object_or_404(Expertise, id=exp_id)
            exp_name = exp.name
            exp.delete()
            log_activity(request.user, f"Deleted expertise: {exp_name}")
            messages.success(request, f"Expertise '{exp_name}' deleted.")
            return redirect("dashboard:manage_services")

        elif action == "assign_expertise":
            form = AdminEngineerExpertiseForm(request.POST)
            if form.is_valid():
                eng = form.cleaned_data["engineer"]
                exp = form.cleaned_data["expertise"]
                level = form.cleaned_data["proficiency_level"]
                ee, created = EngineerExpertise.objects.get_or_create(
                    engineer=eng,
                    expertise=exp,
                    defaults={
                        "proficiency_level": level,
                        "status": EngineerExpertise.VerificationStatus.APPROVED,
                        "reviewed_by": request.user,
                        "reviewed_at": timezone.now()
                    }
                )
                if not created:
                    ee.proficiency_level = level
                    ee.status = EngineerExpertise.VerificationStatus.APPROVED
                    ee.reviewed_by = request.user
                    ee.reviewed_at = timezone.now()
                    ee.save()

                create_notification(
                    user=eng,
                    message=f"Admin directly assigned and verified expertise '{exp.name}' ({level}) on your profile."
                )
                log_activity(request.user, f"Assigned expertise {exp.name} ({level}) to {eng.username}")
                messages.success(request, f"Expertise '{exp.name}' ({level}) assigned to {eng.get_full_name() or eng.username}.")
                return redirect("dashboard:manage_services")

        elif action == "remove_engineer_expertise":
            ee_id = request.POST.get("ee_id")
            ee = get_object_or_404(EngineerExpertise, id=ee_id)
            ee_name = ee.expertise.name
            ee_eng = ee.engineer.username
            ee.delete()
            log_activity(request.user, f"Removed skill assignment {ee_name} from {ee_eng}")
            messages.success(request, "Expertise assignment removed.")
            return redirect("dashboard:manage_services")

    return render(
        request,
        "dashboard/admin_manage_services.html",
        {
            "services": services,
            "expertises": expertises,
            "pending_skill_requests": pending_skill_requests,
            "engineer_expertises": engineer_expertises,
            "service_form": service_form,
            "expertise_form": expertise_form,
            "assign_form": assign_form,
        }
    )



@admin_required
def admin_manage_appointments(request):
    status_filter = request.GET.get("status", "").strip()
    engineer_id = request.GET.get("engineer", "").strip()
    query = request.GET.get("q", "").strip()

    appointments = Appointment.objects.select_related("client", "engineer", "service").order_by("-appointment_date", "-start_time")

    if status_filter:
        appointments = appointments.filter(status=status_filter)
    if engineer_id:
        appointments = appointments.filter(engineer_id=engineer_id)
    if query:
        appointments = appointments.filter(
            Q(project_title__icontains=query) |
            Q(client__username__icontains=query) |
            Q(engineer__username__icontains=query) |
            Q(service__name__icontains=query)
        )

    engineers = User.objects.filter(role=User.Role.ENGINEER)

    return render(
        request,
        "dashboard/admin_manage_appointments.html",
        {
            "appointments": appointments,
            "status_filter": status_filter,
            "selected_engineer": engineer_id,
            "query": query,
            "engineers": engineers,
            "status_choices": Appointment.Status.choices,
        }
    )


@admin_required
def admin_reports(request):
    # 1. Appointments by status
    status_counts = Appointment.objects.values("status").annotate(count=Count("id")).order_by("status")
    total_appts = Appointment.objects.count()

    # 2. Appointments by service
    service_counts = Service.objects.annotate(appt_count=Count("appointments")).order_by("-appt_count")

    # 3. Top engineers by completed appointments & avg rating
    engineer_stats = User.objects.filter(role=User.Role.ENGINEER).annotate(
        total_booked=Count("engineer_appointments"),
        completed_count=Count("engineer_appointments", filter=Q(engineer_appointments__status=Appointment.Status.COMPLETED)),
        avg_rating=Avg("engineer_appointments__feedback__rating")
    ).order_by("-completed_count")

    # 4. Recent feedback
    recent_feedback = Feedback.objects.select_related("appointment__engineer", "appointment__client").order_by("-created_at")[:10]

    # 5. Completion tracking KPIs (daily, weekly, monthly)
    completion_kpis = get_completion_kpis()

    return render(
        request,
        "dashboard/admin_reports.html",
        {
            "status_counts": status_counts,
            "total_appts": total_appts,
            "service_counts": service_counts,
            "engineer_stats": engineer_stats,
            "recent_feedback": recent_feedback,
            "completion_kpis": completion_kpis,
        }
    )


@admin_required
def admin_appointment_tracking(request):
    timeframe = request.GET.get("timeframe", "daily").strip().lower()
    if timeframe not in ["daily", "weekly", "monthly", "overview"]:
        timeframe = "daily"

    engineer_id = request.GET.get("engineer", "").strip()
    service_id = request.GET.get("service", "").strip()
    year_param = request.GET.get("year", "").strip()
    month_param = request.GET.get("month", "").strip()
    days_param = request.GET.get("days", "30").strip()

    selected_engineer = None
    if engineer_id:
        selected_engineer = get_object_or_404(User, id=engineer_id, role=User.Role.ENGINEER)

    selected_service = None
    if service_id:
        selected_service = get_object_or_404(Service, id=service_id)

    today = date.today()

    try:
        target_year = int(year_param) if year_param else today.year
    except ValueError:
        target_year = today.year

    try:
        target_month = int(month_param) if month_param else today.month
    except ValueError:
        target_month = today.month

    try:
        days_back = int(days_param) if days_param else 30
    except ValueError:
        days_back = 30

    # Get overarching KPI cards (Done Today, This Week, This Month, All Time)
    kpis = get_completion_kpis(engineer=selected_engineer, service=selected_service)

    # Get breakdown data
    daily_data = get_daily_completion_breakdown(
        engineer=selected_engineer,
        service=selected_service,
        year=target_year if month_param else None,
        month=target_month if month_param else None,
        days_back=days_back
    )

    weekly_data = get_weekly_completion_breakdown(
        engineer=selected_engineer,
        service=selected_service,
        weeks_back=12,
        year=target_year if timeframe == "weekly" and year_param else None
    )

    monthly_data = get_monthly_completion_breakdown(
        engineer=selected_engineer,
        service=selected_service,
        year=target_year
    )

    distribution_data = get_service_and_engineer_breakdown(
        engineer=selected_engineer,
        service=selected_service
    )

    # Form options
    engineers = User.objects.filter(role=User.Role.ENGINEER, is_active=True).order_by("first_name", "username")
    services = Service.objects.filter(is_active=True).order_by("name")

    # Available years for selection
    available_years = list(range(today.year - 3, today.year + 2))
    available_months = [
        (1, "January"), (2, "February"), (3, "March"), (4, "April"),
        (5, "May"), (6, "June"), (7, "July"), (8, "August"),
        (9, "September"), (10, "October"), (11, "November"), (12, "December")
    ]

    # JSON formatted datasets for Chart.js
    daily_chart_json = json.dumps({
        "labels": daily_data["chart_labels"],
        "data": daily_data["chart_data"],
    })
    weekly_chart_json = json.dumps({
        "labels": weekly_data["chart_labels"],
        "data": weekly_data["chart_data"],
    })
    monthly_chart_json = json.dumps({
        "labels": monthly_data["chart_labels"],
        "data": monthly_data["chart_data"],
    })
    service_chart_json = json.dumps({
        "labels": [s["service__name"] for s in distribution_data["service_breakdown"]],
        "data": [s["count"] for s in distribution_data["service_breakdown"]],
    })

    return render(
        request,
        "dashboard/appointment_tracking.html",
        {
            "timeframe": timeframe,
            "kpis": kpis,
            "daily_data": daily_data,
            "weekly_data": weekly_data,
            "monthly_data": monthly_data,
            "distribution_data": distribution_data,
            "engineers": engineers,
            "services": services,
            "selected_engineer_id": int(engineer_id) if engineer_id and engineer_id.isdigit() else None,
            "selected_service_id": int(service_id) if service_id and service_id.isdigit() else None,
            "target_year": target_year,
            "target_month": target_month,
            "month_param": month_param,
            "days_back": days_back,
            "available_years": available_years,
            "available_months": available_months,
            "daily_chart_json": daily_chart_json,
            "weekly_chart_json": weekly_chart_json,
            "monthly_chart_json": monthly_chart_json,
            "service_chart_json": service_chart_json,
        }
    )


@admin_required
def export_tracking_csv(request):
    engineer_id = request.GET.get("engineer", "").strip()
    service_id = request.GET.get("service", "").strip()
    timeframe = request.GET.get("timeframe", "all").strip()

    qs = Appointment.objects.filter(status=Appointment.Status.COMPLETED).select_related("client", "engineer", "service").order_by("-appointment_date", "-start_time")

    if engineer_id:
        qs = qs.filter(engineer_id=engineer_id)
    if service_id:
        qs = qs.filter(service_id=service_id)

    today = date.today()
    if timeframe == "daily":
        qs = qs.filter(appointment_date=today)
    elif timeframe == "weekly":
        curr_week_start = today - timedelta(days=today.weekday())
        curr_week_end = curr_week_start + timedelta(days=6)
        qs = qs.filter(appointment_date__gte=curr_week_start, appointment_date__lte=curr_week_end)
    elif timeframe == "monthly":
        qs = qs.filter(appointment_date__year=today.year, appointment_date__month=today.month)

    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = f'attachment; filename="completed_appointments_{timeframe}_{today.strftime("%Y%m%d")}.csv"'

    writer = csv.writer(response)
    writer.writerow([
        "Appointment ID",
        "Project Title",
        "Client Username",
        "Client Full Name",
        "Engineer Username",
        "Engineer Full Name",
        "Service Category",
        "Appointment Date",
        "Start Time",
        "End Time",
        "Created At",
        "Updated At",
    ])

    for appt in qs:
        writer.writerow([
            appt.id,
            appt.project_title,
            appt.client.username,
            appt.client.get_full_name() or appt.client.username,
            appt.engineer.username,
            appt.engineer.get_full_name() or appt.engineer.username,
            appt.service.name,
            appt.appointment_date.strftime("%Y-%m-%d"),
            appt.start_time.strftime("%H:%M"),
            appt.end_time.strftime("%H:%M"),
            appt.created_at.strftime("%Y-%m-%d %H:%M:%S"),
            appt.updated_at.strftime("%Y-%m-%d %H:%M:%S"),
        ])

    return response


@admin_required
def admin_activity_logs(request):
    query = request.GET.get("q", "").strip()
    user_id = request.GET.get("user_id", "").strip()

    logs = ActivityLog.objects.select_related("user").order_by("-timestamp")

    if query:
        logs = logs.filter(
            Q(action__icontains=query) |
            Q(user__username__icontains=query)
        )

    if user_id:
        logs = logs.filter(user_id=user_id)

    users = User.objects.all().order_by("username")

    return render(
        request,
        "dashboard/admin_activity_logs.html",
        {
            "logs": logs[:150],
            "query": query,
            "selected_user": user_id,
            "users": users,
        }
    )
