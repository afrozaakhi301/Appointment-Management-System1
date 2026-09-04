from django.core.exceptions import ValidationError
from scheduling.models import EngineerAvailability, EngineerLeave


def validate_appointment_booking(engineer, appointment_date, start_time, end_time, exclude_appointment_id=None):
    """
    Validates complete booking constraints:
    1. start_time < end_time
    2. Engineer is not on leave
    3. Requested slot falls within an active EngineerAvailability period for that weekday
    4. No overlapping appointments with status in [Pending, Approved, Rescheduled]
    """
    if not engineer or not appointment_date or not start_time or not end_time:
        return

    # 1. Time range check
    if start_time >= end_time:
        raise ValidationError({"end_time": "Appointment end time must be after start time."})

    # 2. Leave check
    leave_record = EngineerLeave.objects.filter(
        engineer=engineer,
        start_date__lte=appointment_date,
        end_date__gte=appointment_date
    ).first()

    if leave_record:
        eng_name = engineer.get_full_name() or engineer.username
        raise ValidationError(
            f"Engineer {eng_name} is on leave on {appointment_date} "
            f"(Leave period: {leave_record.start_date.strftime('%b %d, %Y')} to {leave_record.end_date.strftime('%b %d, %Y')}). "
            f"Please select an available date after {leave_record.end_date.strftime('%b %d, %Y')}."
        )

    # 3. Weekday & Working hours availability check
    weekday = appointment_date.weekday()
    day_name = appointment_date.strftime("%A")
    availabilities = EngineerAvailability.objects.filter(
        engineer=engineer,
        day_of_week=weekday
    ).order_by("start_time")

    if not availabilities.exists():
        all_avail = EngineerAvailability.objects.filter(engineer=engineer).order_by("day_of_week", "start_time")
        if all_avail.exists():
            days_summary = []
            for a in all_avail:
                days_summary.append(f"{a.get_day_of_week_display()} ({a.start_time.strftime('%I:%M %p')} - {a.end_time.strftime('%I:%M %p')})")
            schedule_text = ", ".join(days_summary)
            raise ValidationError(
                f"Engineer {engineer.get_full_name() or engineer.username} is not available on {day_name}s. "
                f"Suggested available days & times: {schedule_text}."
            )
        else:
            raise ValidationError(
                f"Engineer {engineer.get_full_name() or engineer.username} has no scheduled working hours on {day_name}s."
            )

    # Check if the requested start and end fall completely within any single availability slot
    within_slot = False
    for slot in availabilities:
        if start_time >= slot.start_time and end_time <= slot.end_time:
            within_slot = True
            break

    if not within_slot:
        slots_str = ", ".join([f"{slot.start_time.strftime('%I:%M %p')} - {slot.end_time.strftime('%I:%M %p')}" for slot in availabilities])
        raise ValidationError(
            f"Selected time slot ({start_time.strftime('%I:%M %p')} - {end_time.strftime('%I:%M %p')}) is outside the engineer's working availability. "
            f"Available working hours on {day_name}: {slots_str}."
        )

    # 4. Double-booking conflict check
    # Blocking statuses: Pending, Approved, Rescheduled
    from .models import Appointment
    blocking_statuses = [
        Appointment.Status.PENDING,
        Appointment.Status.APPROVED,
        Appointment.Status.RESCHEDULED,
    ]

    conflicting_query = Appointment.objects.filter(
        engineer=engineer,
        appointment_date=appointment_date,
        status__in=blocking_statuses,
        start_time__lt=end_time,
        end_time__gt=start_time
    )

    if exclude_appointment_id:
        conflicting_query = conflicting_query.exclude(id=exclude_appointment_id)

    if conflicting_query.exists():
        conflict_list = [f"{c.start_time.strftime('%I:%M %p')} - {c.end_time.strftime('%I:%M %p')}" for c in conflicting_query]
        slots_str = ", ".join([f"{slot.start_time.strftime('%I:%M %p')} - {slot.end_time.strftime('%I:%M %p')}" for slot in availabilities])
        raise ValidationError(
            f"Appointment time conflicts with an existing consultation ({', '.join(conflict_list)}). "
            f"Available working hours on {day_name}: {slots_str}."
        )


def validate_status_transition(appointment, new_status, user):
    """
    Enforces strict status transition rules:
    Pending -> Approved, Rejected, Cancelled, Rescheduled
    Approved -> Rescheduled, Cancelled, Completed
    Rescheduled -> Approved, Cancelled, Completed

    Clients cannot mark Completed or Approve/Reject.
    Engineers can Approve, Reject, Reschedule, Complete.
    """
    from accounts.models import User
    from .models import Appointment

    current_status = appointment.status
    role = user.role

    if user.is_superuser or role == User.Role.ADMIN:
        return True

    if role == User.Role.CLIENT:
        if appointment.client != user:
            raise ValidationError("You do not have permission to modify this appointment.")
        # Clients can only Cancel or Reschedule (if allowed)
        if new_status == Appointment.Status.CANCELLED:
            if current_status not in [Appointment.Status.PENDING, Appointment.Status.APPROVED, Appointment.Status.RESCHEDULED]:
                raise ValidationError(f"Cannot cancel appointment in '{current_status}' status.")
            return True
        elif new_status == Appointment.Status.RESCHEDULED:
            if current_status not in [Appointment.Status.PENDING, Appointment.Status.APPROVED, Appointment.Status.RESCHEDULED]:
                raise ValidationError(f"Cannot reschedule appointment in '{current_status}' status.")
            return True
        else:
            raise ValidationError("Clients are not permitted to make this status change.")

    elif role == User.Role.ENGINEER:
        if appointment.engineer != user:
            raise ValidationError("You do not have permission to modify this appointment.")

        allowed_transitions = {
            Appointment.Status.PENDING: [
                Appointment.Status.APPROVED,
                Appointment.Status.REJECTED,
                Appointment.Status.RESCHEDULED,
                Appointment.Status.CANCELLED,
            ],
            Appointment.Status.APPROVED: [
                Appointment.Status.RESCHEDULED,
                Appointment.Status.CANCELLED,
                Appointment.Status.COMPLETED,
            ],
            Appointment.Status.RESCHEDULED: [
                Appointment.Status.APPROVED,
                Appointment.Status.CANCELLED,
                Appointment.Status.COMPLETED,
            ],
        }

        valid_next_statuses = allowed_transitions.get(current_status, [])
        if new_status not in valid_next_statuses:
            raise ValidationError(f"Cannot transition appointment from '{current_status}' to '{new_status}'.")
        return True

    return True
