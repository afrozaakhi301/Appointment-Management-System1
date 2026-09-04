from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Avg, Count
from django.shortcuts import get_object_or_404, redirect, render
from accounts.decorators import client_required, engineer_required
from appointments.models import Appointment
from dashboard.utils import log_activity
from notifications.utils import create_notification
from .forms import FeedbackForm
from .models import Feedback


@client_required
def submit_feedback_view(request, appointment_id):
    """
    Allows a client to give rating and write feedback for a completed appointment.
    If feedback was already given, allows updating/viewing the previous feedback.
    """
    appointment = get_object_or_404(Appointment, id=appointment_id, client=request.user)

    if appointment.status != Appointment.Status.COMPLETED:
        messages.error(request, "Feedback can only be submitted after the appointment is marked as Completed.")
        return redirect("appointments:appointment_detail", appointment_id=appointment.id)

    existing_feedback = getattr(appointment, "feedback", None)

    if request.method == "POST":
        form = FeedbackForm(request.POST, instance=existing_feedback)
        if form.is_valid():
            feedback = form.save(commit=False)
            feedback.appointment = appointment
            feedback.save()

            if existing_feedback:
                log_activity(request.user, f"Updated feedback ({feedback.rating}★) for appointment #{appointment.id}")
                messages.success(request, "Your consultation feedback has been updated successfully!")
            else:
                log_activity(request.user, f"Submitted feedback ({feedback.rating}★) for appointment #{appointment.id}")
                create_notification(
                    user=appointment.engineer,
                    message=f"Client {request.user.get_full_name() or request.user.username} submitted a {feedback.rating}★ review for consultation '{appointment.project_title}'.",
                    appointment=appointment
                )
                messages.success(request, "Thank you! Your rating and consultation feedback have been submitted successfully.")

            return redirect("appointments:appointment_detail", appointment_id=appointment.id)
        else:
            messages.error(request, "Please correct the errors in your feedback submission.")
    else:
        form = FeedbackForm(instance=existing_feedback)

    return render(
        request,
        "feedback/submit_feedback.html",
        {
            "form": form,
            "appointment": appointment,
            "existing_feedback": existing_feedback,
        }
    )


@client_required
def my_feedback_list_view(request):
    """
    Displays all previous feedback given by the logged-in client across past consultations,
    along with completed consultations awaiting reviews.
    """
    client = request.user
    feedbacks = Feedback.objects.filter(
        appointment__client=client
    ).select_related("appointment__engineer", "appointment__service").order_by("-created_at")

    pending_feedback_appointments = Appointment.objects.filter(
        client=client,
        status=Appointment.Status.COMPLETED,
        feedback__isnull=True
    ).select_related("engineer", "service").order_by("-appointment_date")

    total_submitted = feedbacks.count()
    avg_rating_given = feedbacks.aggregate(Avg("rating"))["rating__avg"] or 0

    return render(
        request,
        "feedback/my_feedback_list.html",
        {
            "feedbacks": feedbacks,
            "pending_feedback_appointments": pending_feedback_appointments,
            "total_submitted": total_submitted,
            "avg_rating_given": round(avg_rating_given, 1),
        }
    )


@engineer_required
def engineer_feedback_list_view(request):
    """
    Displays all consultation feedback & ratings received by the logged-in software engineer.
    """
    engineer = request.user
    feedbacks = Feedback.objects.filter(
        appointment__engineer=engineer
    ).select_related("appointment__client", "appointment__service").order_by("-created_at")

    total_reviews = feedbacks.count()
    avg_rating = feedbacks.aggregate(Avg("rating"))["rating__avg"] or 0

    # Rating distribution breakdown
    rating_counts = {
        5: feedbacks.filter(rating=5).count(),
        4: feedbacks.filter(rating=4).count(),
        3: feedbacks.filter(rating=3).count(),
        2: feedbacks.filter(rating=2).count(),
        1: feedbacks.filter(rating=1).count(),
    }

    # Calculate percentage breakdown for progress bars
    breakdown_percentages = {}
    for stars in range(1, 6):
        count = rating_counts[stars]
        breakdown_percentages[stars] = round((count / total_reviews * 100)) if total_reviews > 0 else 0

    return render(
        request,
        "feedback/engineer_feedback_list.html",
        {
            "feedbacks": feedbacks,
            "total_reviews": total_reviews,
            "avg_rating": round(avg_rating, 1),
            "rating_counts": rating_counts,
            "breakdown_percentages": breakdown_percentages,
        }
    )

