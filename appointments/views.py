import json
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.db.models import Avg, Case, Count, IntegerField, Prefetch, Q, Value, When
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from accounts.decorators import client_required, engineer_required, role_required
from accounts.models import User
from dashboard.utils import log_activity
from notifications.utils import create_notification
from services.models import EngineerExpertise, Service
from .ai_matcher import calculate_match_scores
from .forms import (
    AppointmentBookingForm,
    AppointmentDocumentUploadForm,
    AppointmentRescheduleForm,
)
from .models import Appointment, AppointmentDocument
from .services import validate_status_transition


@client_required
def book_appointment_view(request):
    engineers = User.objects.filter(
        role=User.Role.ENGINEER, 
        is_active=True
    ).select_related("engineer_profile").prefetch_related(
        Prefetch(
            "engineer_expertises",
            queryset=EngineerExpertise.objects.filter(
                status=EngineerExpertise.VerificationStatus.APPROVED
            ).select_related("expertise")
        )
    ).annotate(
        avg_rating=Avg("engineer_appointments__feedback__rating"),
        review_count=Count("engineer_appointments__feedback", distinct=True)
    )
    services = Service.objects.filter(is_active=True).annotate(
        priority=Case(
            When(name__icontains="General Architecture", then=Value(0)),
            default=Value(1),
            output_field=IntegerField(),
        )
    ).order_by("priority", "name")
    general_service = services.filter(
        Q(name__icontains="General Architecture") | 
        Q(name__icontains="Scoping")
    ).first()

    # Prepare serialized data for dynamic frontend filtering
    all_engineers_data = []
    for eng in engineers:
        rating_val = round(eng.avg_rating, 1) if eng.avg_rating else None
        rating_str = f"★ {rating_val}" if rating_val else ""
        exp_names = [ee.expertise.name for ee in eng.engineer_expertises.all()]
        exp_ids = [ee.expertise.id for ee in eng.engineer_expertises.all()]
        desig = eng.engineer_profile.designation if hasattr(eng, "engineer_profile") and eng.engineer_profile.designation else "Lead Software Engineer"

        eng_data = {
            "id": eng.id,
            "name": eng.get_full_name() or eng.username,
            "designation": desig,
            "rating": rating_val,
            "rating_str": rating_str,
            "expertises": exp_names,
            "expertise_ids": exp_ids,
            "years_of_experience": eng.engineer_profile.years_of_experience if hasattr(eng, "engineer_profile") else 0,
        }
        all_engineers_data.append(eng_data)

    # Domain match mapping per service
    engineer_service_map = {}
    for svc in services:
        matching = []
        svc_name_lower = svc.name.lower()

        for eng in all_engineers_data:
            exp_lower = [e.lower() for e in eng["expertises"]]
            desig_lower = eng["designation"].lower()

            is_match = False
            if "general architecture" in svc_name_lower or "scoping" in svc_name_lower:
                # General Architecture & Scoping can be taken by all qualified engineers/architects
                is_match = True
            elif "cloud" in svc_name_lower or "aws" in svc_name_lower or "gcp" in svc_name_lower:
                if any("cloud" in e or "aws" in e or "devops" in e or "kubernetes" in e or "terraform" in e for e in exp_lower) or "cloud" in desig_lower or "architect" in desig_lower:
                    is_match = True
            elif "database" in svc_name_lower or "performance" in svc_name_lower:
                if any("database" in e or "sql" in e or "redis" in e or "postgres" in e or "query" in e or "python" in e for e in exp_lower) or "database" in desig_lower or "backend" in desig_lower:
                    is_match = True
            elif "devops" in svc_name_lower or "ci/cd" in svc_name_lower or "infrastructure" in svc_name_lower:
                if any("devops" in e or "docker" in e or "kubernetes" in e or "terraform" in e or "ci/cd" in e for e in exp_lower) or "devops" in desig_lower or "infrastructure" in desig_lower:
                    is_match = True
            elif "microservice" in svc_name_lower or "api" in svc_name_lower:
                if any("microservice" in e or "grpc" in e or "api" in e or "django" in e or "python" in e for e in exp_lower) or "microservice" in desig_lower or "architect" in desig_lower:
                    is_match = True
            elif "code review" in svc_name_lower or "django code" in svc_name_lower:
                if any("python" in e or "django" in e or "security" in e or "qa" in e or "owasp" in e for e in exp_lower) or "python" in desig_lower or "django" in desig_lower:
                    is_match = True
            elif "mobile" in svc_name_lower or "cross-platform" in svc_name_lower or "ios" in svc_name_lower or "android" in svc_name_lower or "flutter" in svc_name_lower:
                if any("mobile" in e or "flutter" in e or "react native" in e or "ios" in e or "android" in e for e in exp_lower) or "mobile" in desig_lower:
                    is_match = True
            elif "cybersecurity" in svc_name_lower or "security" in svc_name_lower or "hardening" in svc_name_lower or "audit" in svc_name_lower:
                if any("security" in e or "owasp" in e or "penetration" in e or "hardening" in e or "audit" in e for e in exp_lower) or "security" in desig_lower or "cybersecurity" in desig_lower:
                    is_match = True
            else:
                for exp in exp_lower:
                    if any(word in exp for word in svc_name_lower.split() if len(word) > 3):
                        is_match = True
                        break

            if is_match:
                matching.append(eng)

        if not matching:
            matching = all_engineers_data

        engineer_service_map[str(svc.id)] = matching

    initial_data = {}
    if "engineer" in request.GET:
        initial_data["engineer"] = request.GET.get("engineer")
    if "service" in request.GET:
        initial_data["service"] = request.GET.get("service")
        if "engineer" not in initial_data:
            svc_key = str(request.GET.get("service"))
            if svc_key in engineer_service_map and len(engineer_service_map[svc_key]) == 1:
                initial_data["engineer"] = engineer_service_map[svc_key][0]["id"]

    if request.method == "POST":
        form = AppointmentBookingForm(request.POST, request.FILES)
        if form.is_valid():
            appointment = form.save(commit=False)
            appointment.client = request.user
            appointment.status = Appointment.Status.PENDING

            # File upload validation: max 5MB, PDF/DOC/DOCX/ZIP
            uploaded_doc = request.FILES.get("document")
            if uploaded_doc:
                max_size = 5 * 1024 * 1024
                if uploaded_doc.size > max_size:
                    messages.error(request, "Document file size exceeds 5MB limit.")
                    return render(
                        request, 
                        "appointments/book_appointment.html", 
                        {
                            "form": form,
                            "engineers": engineers,
                            "services": services,
                            "general_service": general_service,
                            "engineer_service_map": engineer_service_map,
                            "all_engineers_data": all_engineers_data,
                            "engineer_service_map_json": json.dumps(engineer_service_map),
                            "all_engineers_json": json.dumps(all_engineers_data),
                        }
                    )

            appointment.save()

            if uploaded_doc:
                AppointmentDocument.objects.create(
                    appointment=appointment,
                    file=uploaded_doc
                )

            log_activity(request.user, f"Created appointment #{appointment.id} for {appointment.service.name}")

            # Send Notification to Engineer
            create_notification(
                user=appointment.engineer,
                message=f"New consultation request submitted by client {request.user.username} for '{appointment.project_title}'.",
                appointment=appointment
            )

            messages.success(request, f"Your appointment request for '{appointment.project_title}' has been submitted successfully! The engineer will review your request.")
            return redirect("appointments:appointment_detail", appointment_id=appointment.id)
        else:
            messages.error(request, "Unable to submit appointment request. Please check the errors below.")
    else:
        form = AppointmentBookingForm(initial=initial_data)

    return render(
        request,
        "appointments/book_appointment.html",
        {
            "form": form,
            "engineers": engineers,
            "services": services,
            "general_service": general_service,
            "engineer_service_map": engineer_service_map,
            "all_engineers_data": all_engineers_data,
            "engineer_service_map_json": json.dumps(engineer_service_map),
            "all_engineers_json": json.dumps(all_engineers_data),
        }
    )



@client_required
def client_appointments_view(request):
    status_filter = request.GET.get("status", "").strip()
    query = request.GET.get("q", "").strip()

    appointments = Appointment.objects.filter(client=request.user).select_related("engineer", "service", "feedback")

    if status_filter:
        appointments = appointments.filter(status=status_filter)

    if query:
        appointments = appointments.filter(
            Q(project_title__icontains=query) |
            Q(project_description__icontains=query) |
            Q(engineer__first_name__icontains=query) |
            Q(engineer__last_name__icontains=query)
        )

    return render(
        request,
        "appointments/client_appointments.html",
        {
            "appointments": appointments,
            "status_filter": status_filter,
            "query": query,
            "status_choices": Appointment.Status.choices,
        }
    )


@engineer_required
def engineer_requests_view(request):
    requests_list = Appointment.objects.filter(
        engineer=request.user,
        status=Appointment.Status.PENDING
    ).select_related("client", "service").order_by("appointment_date", "start_time")

    return render(
        request,
        "appointments/engineer_requests.html",
        {"requests": requests_list}
    )


@engineer_required
def engineer_schedule_view(request):
    tab = request.GET.get("tab", "upcoming")
    engineer = request.user

    if tab == "history":
        appointments = Appointment.objects.filter(
            engineer=engineer,
            status__in=[Appointment.Status.COMPLETED, Appointment.Status.CANCELLED, Appointment.Status.REJECTED]
        ).select_related("client", "service", "feedback").order_by("-appointment_date", "-start_time")
    else:
        appointments = Appointment.objects.filter(
            engineer=engineer,
            status__in=[Appointment.Status.APPROVED, Appointment.Status.RESCHEDULED]
        ).select_related("client", "service", "feedback").order_by("appointment_date", "start_time")

    return render(
        request,
        "appointments/engineer_schedule.html",
        {
            "appointments": appointments,
            "tab": tab,
        }
    )


@login_required
def appointment_detail_view(request, appointment_id):
    appointment = get_object_or_404(
        Appointment.objects.select_related("client", "engineer", "service"),
        id=appointment_id
    )

    user = request.user
    # Authorization & IDOR protection
    if not (user.is_superuser or user.role == User.Role.ADMIN or appointment.client == user or appointment.engineer == user):
        messages.error(request, "You do not have permission to view this appointment.")
        return redirect("accounts:redirect_after_login")

    documents = appointment.documents.all().order_by("-uploaded_at")
    feedback = getattr(appointment, "feedback", None)
    doc_form = AppointmentDocumentUploadForm()

    return render(
        request,
        "appointments/appointment_detail.html",
        {
            "appointment": appointment,
            "documents": documents,
            "feedback": feedback,
            "doc_form": doc_form,
        }
    )


@login_required
def appointment_approve_view(request, appointment_id):
    appointment = get_object_or_404(Appointment, id=appointment_id)
    user = request.user

    if not (user.is_superuser or user.role == User.Role.ADMIN or (user.role == User.Role.ENGINEER and appointment.engineer == user)):
        messages.error(request, "You are not authorized to approve this appointment.")
        return redirect("appointments:appointment_detail", appointment_id=appointment.id)

    try:
        validate_status_transition(appointment, Appointment.Status.APPROVED, user)
        appointment.status = Appointment.Status.APPROVED
        appointment.save()

        log_activity(user, f"Approved appointment #{appointment.id} ({appointment.project_title})")
        create_notification(
            user=appointment.client,
            message=f"Great news! Your consultation request for '{appointment.project_title}' has been approved by {appointment.engineer.get_full_name() or appointment.engineer.username}.",
            appointment=appointment
        )
        messages.success(request, f"Appointment #{appointment.id} has been approved.")
    except ValidationError as e:
        messages.error(request, str(e.message if hasattr(e, 'message') else e))

    return redirect("appointments:appointment_detail", appointment_id=appointment.id)


@login_required
def appointment_reject_view(request, appointment_id):
    appointment = get_object_or_404(Appointment, id=appointment_id)
    user = request.user

    if not (user.is_superuser or user.role == User.Role.ADMIN or (user.role == User.Role.ENGINEER and appointment.engineer == user)):
        messages.error(request, "You are not authorized to reject this appointment.")
        return redirect("appointments:appointment_detail", appointment_id=appointment.id)

    try:
        validate_status_transition(appointment, Appointment.Status.REJECTED, user)
        appointment.status = Appointment.Status.REJECTED
        appointment.save()

        log_activity(user, f"Rejected appointment #{appointment.id} ({appointment.project_title})")
        create_notification(
            user=appointment.client,
            message=f"Your consultation request for '{appointment.project_title}' was declined by {appointment.engineer.get_full_name() or appointment.engineer.username}.",
            appointment=appointment
        )
        messages.info(request, f"Appointment #{appointment.id} has been rejected.")
    except ValidationError as e:
        messages.error(request, str(e.message if hasattr(e, 'message') else e))

    return redirect("appointments:appointment_detail", appointment_id=appointment.id)


@login_required
def appointment_reschedule_view(request, appointment_id):
    appointment = get_object_or_404(Appointment, id=appointment_id)
    user = request.user

    if not (user.is_superuser or user.role == User.Role.ADMIN or appointment.client == user or appointment.engineer == user):
        messages.error(request, "You do not have permission to reschedule this appointment.")
        return redirect("accounts:redirect_after_login")

    if not appointment.can_reschedule():
        messages.error(request, f"Cannot reschedule an appointment with status '{appointment.status}'.")
        return redirect("appointments:appointment_detail", appointment_id=appointment.id)

    if request.method == "POST":
        form = AppointmentRescheduleForm(request.POST, instance=appointment)
        if form.is_valid():
            appt = form.save(commit=False)
            appt.status = Appointment.Status.RESCHEDULED
            appt.save()

            log_activity(user, f"Rescheduled appointment #{appt.id} to {appt.appointment_date} ({appt.start_time.strftime('%H:%M')}-{appt.end_time.strftime('%H:%M')})")

            # Notify the opposite party
            notify_user = appt.engineer if user == appt.client else appt.client
            create_notification(
                user=notify_user,
                message=f"Consultation '{appt.project_title}' has been rescheduled to {appt.appointment_date} ({appt.start_time.strftime('%H:%M')} - {appt.end_time.strftime('%H:%M')}) by {user.get_full_name() or user.username}.",
                appointment=appt
            )

            messages.success(request, f"Appointment has been rescheduled successfully to {appt.appointment_date}.")
            return redirect("appointments:appointment_detail", appointment_id=appt.id)
        else:
            messages.error(request, "Failed to reschedule appointment. Please check the errors below.")
    else:
        form = AppointmentRescheduleForm(instance=appointment)

    return render(
        request,
        "appointments/reschedule_appointment.html",
        {
            "form": form,
            "appointment": appointment,
        }
    )


@login_required
def appointment_cancel_view(request, appointment_id):
    appointment = get_object_or_404(Appointment, id=appointment_id)
    user = request.user

    if not (user.is_superuser or user.role == User.Role.ADMIN or appointment.client == user or appointment.engineer == user):
        messages.error(request, "You do not have permission to cancel this appointment.")
        return redirect("accounts:redirect_after_login")

    if not appointment.can_cancel():
        messages.error(request, f"Cannot cancel an appointment with status '{appointment.status}'.")
        return redirect("appointments:appointment_detail", appointment_id=appointment.id)

    try:
        validate_status_transition(appointment, Appointment.Status.CANCELLED, user)
        appointment.status = Appointment.Status.CANCELLED
        appointment.save()

        log_activity(user, f"Cancelled appointment #{appointment.id} ({appointment.project_title})")

        notify_user = appointment.engineer if user == appointment.client else appointment.client
        create_notification(
            user=notify_user,
            message=f"Consultation '{appointment.project_title}' scheduled on {appointment.appointment_date} was cancelled by {user.get_full_name() or user.username}.",
            appointment=appointment
        )

        messages.success(request, f"Appointment #{appointment.id} has been cancelled.")
    except ValidationError as e:
        messages.error(request, str(e.message if hasattr(e, 'message') else e))

    return redirect("appointments:appointment_detail", appointment_id=appointment.id)


@login_required
def appointment_complete_view(request, appointment_id):
    appointment = get_object_or_404(Appointment, id=appointment_id)
    user = request.user

    # Clients are strictly forbidden from marking complete
    if not (user.is_superuser or user.role == User.Role.ADMIN or (user.role == User.Role.ENGINEER and appointment.engineer == user)):
        messages.error(request, "Only the assigned engineer or administrator can mark an appointment as Completed.")
        return redirect("appointments:appointment_detail", appointment_id=appointment.id)

    if not appointment.can_complete():
        messages.error(request, f"Cannot mark appointment as Completed from status '{appointment.status}'. Must be Approved or Rescheduled.")
        return redirect("appointments:appointment_detail", appointment_id=appointment.id)

    try:
        validate_status_transition(appointment, Appointment.Status.COMPLETED, user)
        appointment.status = Appointment.Status.COMPLETED
        appointment.save()

        log_activity(user, f"Completed appointment #{appointment.id} ({appointment.project_title})")
        create_notification(
            user=appointment.client,
            message=f"Your consultation '{appointment.project_title}' has been marked as Completed. Please take a moment to leave a review and rating!",
            appointment=appointment
        )

        messages.success(request, f"Appointment #{appointment.id} marked as Completed.")
    except ValidationError as e:
        messages.error(request, str(e.message if hasattr(e, 'message') else e))

    return redirect("appointments:appointment_detail", appointment_id=appointment.id)


@login_required
def appointment_upload_doc_view(request, appointment_id):
    appointment = get_object_or_404(Appointment, id=appointment_id)
    user = request.user

    if not (user.is_superuser or user.role == User.Role.ADMIN or appointment.client == user or appointment.engineer == user):
        messages.error(request, "You do not have permission to upload documents for this appointment.")
        return redirect("accounts:redirect_after_login")

    if request.method == "POST":
        form = AppointmentDocumentUploadForm(request.POST, request.FILES)
        if form.is_valid():
            doc = form.save(commit=False)
            doc.appointment = appointment
            doc.save()
            log_activity(user, f"Uploaded document '{doc.filename()}' for appointment #{appointment.id}")
            messages.success(request, f"Document '{doc.filename()}' uploaded successfully.")
        else:
            messages.error(request, "Failed to upload document.")

    return redirect("appointments:appointment_detail", appointment_id=appointment.id)


def ai_match_view(request):
    """
    JSON API endpoint for AI-assisted problem analysis and engineer matching.
    Accepts POST JSON {"text": "..."} and returns structured analysis including
    the matched Service and ranked Engineers with compatibility scores.
    """
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed. Use POST."}, status=405)

    text = ""
    try:
        if request.body:
            content_type = request.META.get("CONTENT_TYPE", "")
            if "application/json" in content_type:
                payload = json.loads(request.body.decode("utf-8"))
                text = payload.get("text", "")
            else:
                text = request.POST.get("text", "")
        else:
            text = request.POST.get("text", "")
    except (json.JSONDecodeError, UnicodeDecodeError):
        return JsonResponse({"error": "Invalid JSON format in request body."}, status=400)

    if not isinstance(text, str) or not text.strip():
        return JsonResponse(
            {"error": "Please provide project details or problem text in the 'text' field."},
            status=400
        )

    try:
        analysis = calculate_match_scores(text.strip())
        return JsonResponse(analysis, status=200)
    except Exception as e:
        return JsonResponse({"error": f"AI Matcher error: {str(e)}"}, status=500)

