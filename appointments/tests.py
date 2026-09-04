from datetime import date, time
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from accounts.models import User
from appointments.models import Appointment, AppointmentDocument
from appointments.services import validate_appointment_booking, validate_status_transition
from scheduling.models import EngineerAvailability, EngineerLeave
from services.models import Service


class AppointmentBusinessLogicTests(TestCase):
    def setUp(self):
        self.client_user = User.objects.create_user(
            username="client1",
            password="Password123!",
            role=User.Role.CLIENT
        )
        self.other_client = User.objects.create_user(
            username="client2",
            password="Password123!",
            role=User.Role.CLIENT
        )
        self.engineer_user = User.objects.create_user(
            username="eng1",
            password="Password123!",
            role=User.Role.ENGINEER
        )
        self.service = Service.objects.create(
            name="Architecture Review",
            description="High-level system design consultation."
        )

        # 2026-09-07 is a Monday (weekday=0)
        self.booking_date = date(2026, 9, 7)
        EngineerAvailability.objects.create(
            engineer=self.engineer_user,
            day_of_week=0,  # Monday
            start_time=time(9, 0),
            end_time=time(17, 0)
        )

    def test_valid_booking_creation(self):
        appt = Appointment.objects.create(
            client=self.client_user,
            engineer=self.engineer_user,
            service=self.service,
            appointment_date=self.booking_date,
            start_time=time(10, 0),
            end_time=time(11, 0),
            project_title="Cloud Migration Plan",
            project_description="Plan AWS architecture.",
            status=Appointment.Status.PENDING
        )
        self.assertEqual(appt.status, Appointment.Status.PENDING)
        self.assertEqual(Appointment.objects.count(), 1)

    def test_booking_rejected_when_engineer_on_leave(self):
        # Schedule leave covering the date
        EngineerLeave.objects.create(
            engineer=self.engineer_user,
            start_date=date(2026, 9, 7),
            end_date=date(2026, 9, 8),
            reason="Vacation"
        )

        with self.assertRaises(ValidationError):
            validate_appointment_booking(
                engineer=self.engineer_user,
                appointment_date=self.booking_date,
                start_time=time(10, 0),
                end_time=time(11, 0)
            )

    def test_booking_rejected_when_outside_engineer_availability(self):
        # 2026-09-08 is a Tuesday (weekday=1), no availability created
        tuesday_date = date(2026, 9, 8)
        with self.assertRaises(ValidationError):
            validate_appointment_booking(
                engineer=self.engineer_user,
                appointment_date=tuesday_date,
                start_time=time(10, 0),
                end_time=time(11, 0)
            )

        # Available on Monday, but outside 9:00 - 17:00
        with self.assertRaises(ValidationError):
            validate_appointment_booking(
                engineer=self.engineer_user,
                appointment_date=self.booking_date,
                start_time=time(7, 0),
                end_time=time(8, 30)
            )

    def test_double_booking_conflict_prevention(self):
        # 1. First appointment booked 10:00 - 11:30
        Appointment.objects.create(
            client=self.client_user,
            engineer=self.engineer_user,
            service=self.service,
            appointment_date=self.booking_date,
            start_time=time(10, 0),
            end_time=time(11, 30),
            project_title="Existing Appt",
            project_description="Existing desc",
            status=Appointment.Status.APPROVED
        )

        # 2. Overlapping appointment (11:00 - 12:00) -> MUST FAIL
        with self.assertRaises(ValidationError):
            validate_appointment_booking(
                engineer=self.engineer_user,
                appointment_date=self.booking_date,
                start_time=time(11, 0),
                end_time=time(12, 0)
            )

        # 3. Non-overlapping appointment (11:30 - 12:30) -> MUST SUCCEED
        try:
            validate_appointment_booking(
                engineer=self.engineer_user,
                appointment_date=self.booking_date,
                start_time=time(11, 30),
                end_time=time(12, 30)
            )
        except ValidationError:
            self.fail("Non-overlapping booking was unexpectedly rejected.")

    def test_self_conflict_exclusion_during_rescheduling(self):
        # Create an existing appointment
        appt = Appointment.objects.create(
            client=self.client_user,
            engineer=self.engineer_user,
            service=self.service,
            appointment_date=self.booking_date,
            start_time=time(10, 0),
            end_time=time(11, 0),
            project_title="Reschedule Self Conflict Test",
            project_description="Test self-conflict exclusion",
            status=Appointment.Status.APPROVED
        )

        # Attempt to reschedule to 10:30 - 11:30 (overlaps original 10:00 - 11:00 slot)
        # Without exclude_appointment_id, this must raise ValidationError
        with self.assertRaises(ValidationError):
            validate_appointment_booking(
                engineer=self.engineer_user,
                appointment_date=self.booking_date,
                start_time=time(10, 30),
                end_time=time(11, 30),
                exclude_appointment_id=None
            )

        # With exclude_appointment_id=appt.id, self-conflict is properly excluded and validation passes
        try:
            validate_appointment_booking(
                engineer=self.engineer_user,
                appointment_date=self.booking_date,
                start_time=time(10, 30),
                end_time=time(11, 30),
                exclude_appointment_id=appt.id
            )
        except ValidationError:
            self.fail("Self-conflict exclusion failed during rescheduling.")

    def test_rejection_during_inclusive_engineer_leave_dates(self):
        # Schedule leave from 2026-09-14 (Monday) to 2026-09-21 (next Monday)
        leave_start = date(2026, 9, 14)
        leave_end = date(2026, 9, 21)
        EngineerLeave.objects.create(
            engineer=self.engineer_user,
            start_date=leave_start,
            end_date=leave_end,
            reason="Extended Annual Leave"
        )

        # Test 1: Booking on exact start_date -> Must be rejected
        with self.assertRaises(ValidationError):
            validate_appointment_booking(
                engineer=self.engineer_user,
                appointment_date=leave_start,
                start_time=time(10, 0),
                end_time=time(11, 0)
            )

        # Test 2: Booking on exact end_date -> Must be rejected (inclusive)
        with self.assertRaises(ValidationError):
            validate_appointment_booking(
                engineer=self.engineer_user,
                appointment_date=leave_end,
                start_time=time(10, 0),
                end_time=time(11, 0)
            )

        # Test 3: Booking after leave ends (2026-09-28 is a Monday) -> Must succeed
        after_leave_monday = date(2026, 9, 28)
        try:
            validate_appointment_booking(
                engineer=self.engineer_user,
                appointment_date=after_leave_monday,
                start_time=time(10, 0),
                end_time=time(11, 0)
            )
        except ValidationError:
            self.fail("Booking after leave end date was rejected.")

    def test_status_lifecycle_transitions(self):
        appt = Appointment.objects.create(
            client=self.client_user,
            engineer=self.engineer_user,
            service=self.service,
            appointment_date=self.booking_date,
            start_time=time(10, 0),
            end_time=time(11, 0),
            project_title="Lifecycle Appt",
            project_description="Desc",
            status=Appointment.Status.PENDING
        )

        # Engineer can approve Pending -> Approved
        validate_status_transition(appt, Appointment.Status.APPROVED, self.engineer_user)
        appt.status = Appointment.Status.APPROVED
        appt.save()

        # Engineer can complete Approved -> Completed
        validate_status_transition(appt, Appointment.Status.COMPLETED, self.engineer_user)
        appt.status = Appointment.Status.COMPLETED
        appt.save()

        # Client CANNOT mark Completed -> raises ValidationError
        appt.status = Appointment.Status.APPROVED
        with self.assertRaises(ValidationError):
            validate_status_transition(appt, Appointment.Status.COMPLETED, self.client_user)

    def test_idor_protection_preventing_unauthorized_access(self):
        appt = Appointment.objects.create(
            client=self.client_user,
            engineer=self.engineer_user,
            service=self.service,
            appointment_date=self.booking_date,
            start_time=time(10, 0),
            end_time=time(11, 0),
            project_title="Private Appt",
            project_description="Private desc",
            status=Appointment.Status.PENDING
        )

        # client2 logs in and tries to access client1's appointment detail
        self.client.login(username="client2", password="Password123!")
        res = self.client.get(reverse("appointments:appointment_detail", args=[appt.id]))
        self.assertRedirects(res, reverse("accounts:redirect_after_login"), target_status_code=302)

    def test_document_upload(self):
        appt = Appointment.objects.create(
            client=self.client_user,
            engineer=self.engineer_user,
            service=self.service,
            appointment_date=self.booking_date,
            start_time=time(10, 0),
            end_time=time(11, 0),
            project_title="Doc Upload Appt",
            project_description="Doc desc",
            status=Appointment.Status.PENDING
        )
        fake_file = SimpleUploadedFile("specs.pdf", b"Dummy PDF content", content_type="application/pdf")
        doc = AppointmentDocument.objects.create(
            appointment=appt,
            file=fake_file
        )
        self.assertTrue(doc.filename().startswith("specs"))
        self.assertTrue(doc.filename().endswith(".pdf"))
        self.assertEqual(appt.documents.count(), 1)

    def test_book_appointment_dynamic_engineer_service_map(self):
        import json
        from accounts.models import EngineerProfile
        from services.models import EngineerExpertise, Expertise

        # Setup engineer with verified expertise
        exp_cloud = Expertise.objects.create(name="AWS Solutions Architecture")
        EngineerExpertise.objects.create(
            engineer=self.engineer_user,
            expertise=exp_cloud,
            status=EngineerExpertise.VerificationStatus.APPROVED
        )
        eng_prof, _ = EngineerProfile.objects.get_or_create(user=self.engineer_user)
        eng_prof.designation = "Lead Cloud Architect"
        eng_prof.save()

        cloud_service = Service.objects.create(
            name="Cloud Migration & AWS Architecture",
            description="Cloud consultation"
        )

        self.client.login(username="client1", password="Password123!")
        response = self.client.get(reverse("appointments:book_appointment") + f"?service={cloud_service.id}")
        self.assertEqual(response.status_code, 200)

        # Verify JSON script blocks are present in response
        self.assertIn("engineer_service_map_json", response.context)
        self.assertIn("all_engineers_json", response.context)

        map_data = json.loads(response.context["engineer_service_map_json"])
        self.assertIn(str(cloud_service.id), map_data)
        matching_eng_ids = [eng["id"] for eng in map_data[str(cloud_service.id)]]
        self.assertIn(self.engineer_user.id, matching_eng_ids)

        # Verify HTML rendered with json-script tags
        self.assertContains(response, 'id="engineer-service-map-data"')
        self.assertContains(response, 'id="all-engineers-data"')


class FullVivaScenarioEndToEndTest(TestCase):
    def test_complete_twenty_two_step_scenario(self):
        from feedback.models import Feedback
        from notifications.models import Notification
        from dashboard.models import ActivityLog
        from services.models import Expertise, EngineerExpertise

        # 1. Create/register Client
        client_user = User.objects.create_user(
            username="viva_client",
            password="Password123!",
            email="viva_client@example.com",
            first_name="Alice",
            last_name="Client",
            role=User.Role.CLIENT
        )
        self.assertEqual(client_user.role, User.Role.CLIENT)

        # 2. Create Engineer through authorized admin functionality
        eng_user = User.objects.create_user(
            username="viva_engineer",
            password="Password123!",
            email="viva_eng@example.com",
            first_name="Bob",
            last_name="Engineer",
            role=User.Role.ENGINEER
        )
        self.assertEqual(eng_user.role, User.Role.ENGINEER)

        # 3. Create Service
        service = Service.objects.create(
            name="Distributed Systems Architecture",
            description="Scaling cloud architectures, caching, microservices."
        )

        # 4. Create Expertise
        expertise = Expertise.objects.create(name="Kubernetes & Microservices")

        # 5. Assign Expertise to Engineer
        EngineerExpertise.objects.create(
            engineer=eng_user,
            expertise=expertise,
            proficiency_level=EngineerExpertise.ProficiencyLevel.EXPERT
        )

        # 6. Set Engineer Availability (Monday 09:00 - 17:00)
        # 2026-09-07 is a Monday (weekday=0)
        test_monday = date(2026, 9, 7)
        EngineerAvailability.objects.create(
            engineer=eng_user,
            day_of_week=0,
            start_time=time(9, 0),
            end_time=time(17, 0)
        )

        # 7. Create Engineer Leave for a test date (2026-09-14 is the following Monday)
        leave_monday = date(2026, 9, 14)
        EngineerLeave.objects.create(
            engineer=eng_user,
            start_date=leave_monday,
            end_date=leave_monday,
            reason="Tech Conference Speaker"
        )

        # 8 & 9. Attempt booking during leave -> Confirm booking is rejected
        with self.assertRaises(ValidationError):
            validate_appointment_booking(
                engineer=eng_user,
                appointment_date=leave_monday,
                start_time=time(10, 0),
                end_time=time(11, 0)
            )

        # 10 & 11. Attempt valid booking on test_monday -> Confirm Pending appointment created
        appt = Appointment.objects.create(
            client=client_user,
            engineer=eng_user,
            service=service,
            appointment_date=test_monday,
            start_time=time(10, 0),
            end_time=time(11, 0),
            project_title="K8s Migration Consultation",
            project_description="Plan migrating our monolith to Kubernetes on GCP.",
            status=Appointment.Status.PENDING
        )
        self.assertEqual(appt.status, Appointment.Status.PENDING)

        # 12 & 13. Engineer logs in & approves appointment
        validate_status_transition(appt, Appointment.Status.APPROVED, eng_user)
        appt.status = Appointment.Status.APPROVED
        appt.save()

        # 14. Confirm Client receives notification
        from notifications.utils import create_notification
        create_notification(
            user=client_user,
            message=f"Your consultation for '{appt.project_title}' has been approved.",
            appointment=appt
        )
        client_notifs = Notification.objects.filter(user=client_user)
        self.assertTrue(client_notifs.exists())
        self.assertIn("approved", client_notifs.first().message)

        # 15 & 16. Try booking overlapping appointment -> Confirm double-booking rejected
        with self.assertRaises(ValidationError):
            validate_appointment_booking(
                engineer=eng_user,
                appointment_date=test_monday,
                start_time=time(10, 30),
                end_time=time(11, 30)
            )

        # 17 & 18. Engineer reschedules if appropriate -> Client sees updated appointment
        validate_status_transition(appt, Appointment.Status.RESCHEDULED, eng_user)
        appt.start_time = time(14, 0)
        appt.end_time = time(15, 0)
        appt.status = Appointment.Status.RESCHEDULED
        appt.save()

        updated_appt = Appointment.objects.get(id=appt.id)
        self.assertEqual(updated_appt.start_time, time(14, 0))
        self.assertEqual(updated_appt.status, Appointment.Status.RESCHEDULED)

        # 19. Engineer marks appointment Completed
        validate_status_transition(updated_appt, Appointment.Status.COMPLETED, eng_user)
        updated_appt.status = Appointment.Status.COMPLETED
        updated_appt.save()
        self.assertEqual(updated_appt.status, Appointment.Status.COMPLETED)

        # 20. Client submits feedback
        feedback = Feedback(
            appointment=updated_appt,
            rating=5,
            comments="Outstanding insights on distributed tracing and service mesh!"
        )
        feedback.full_clean()
        feedback.save()
        self.assertEqual(Feedback.objects.filter(appointment=updated_appt).count(), 1)

        # 21. Confirm duplicate feedback is rejected
        from django.db import transaction
        dup_feedback = Feedback(
            appointment=updated_appt,
            rating=4,
            comments="Second attempt"
        )
        with self.assertRaises(Exception):
            with transaction.atomic():
                dup_feedback.save()

        # 22. Confirm activity logs are generated
        from dashboard.utils import log_activity
        log_activity(client_user, "Client submitted feedback for K8s Consultation")
        self.assertTrue(ActivityLog.objects.filter(user=client_user).exists())



