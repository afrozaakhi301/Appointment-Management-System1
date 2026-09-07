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

    def test_book_appointment_displays_scoping_card_highlight_and_sequential_badges(self):
        general_svc, _ = Service.objects.get_or_create(
            name="General Architecture & Technical Scoping",
            defaults={
                "description": "Scoping session for non-technical clients.",
                "is_active": True
            }
        )
        self.client.login(username="client1", password="Password123!")
        response = self.client.get(reverse("appointments:book_appointment"))
        self.assertEqual(response.status_code, 200)

        # Context has general_service as the first item in services list
        self.assertIn("general_service", response.context)
        self.assertEqual(response.context["general_service"], general_svc)
        self.assertEqual(list(response.context["services"])[0], general_svc)

        # Sequential badges and highlight on Service #1
        self.assertContains(response, "Service #1")
        self.assertContains(response, "💡 Not sure which service fits? Start Here")
        self.assertContains(response, "Work directly with a lead software architect to define requirements")
        self.assertContains(response, "scoping-highlight-card")


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


class AIMatcherUnitTests(TestCase):
    def setUp(self):
        from accounts.models import EngineerProfile
        from services.models import EngineerExpertise, Expertise

        # 1. Create Services
        self.cloud_service = Service.objects.create(
            name="Cloud Architecture & AWS Migration",
            description="Enterprise AWS infrastructure, Docker containerization, Kubernetes clusters, and Terraform."
        )
        self.db_service = Service.objects.create(
            name="Database Performance & Optimization",
            description="PostgreSQL indexing, SQL query tuning, Redis caching, and replication."
        )

        # 2. Create Expertises
        self.exp_aws = Expertise.objects.create(name="AWS Solutions Architecture")
        self.exp_k8s = Expertise.objects.create(name="Kubernetes & Docker")
        self.exp_postgres = Expertise.objects.create(name="PostgreSQL Optimization")

        # 3. Create Cloud Engineer (Lead)
        self.cloud_eng = User.objects.create_user(
            username="cloud_lead",
            password="Password123!",
            first_name="Jane",
            last_name="Doe",
            role=User.Role.ENGINEER
        )
        eng_prof1, _ = EngineerProfile.objects.get_or_create(user=self.cloud_eng)
        eng_prof1.designation = "Lead Cloud Architect"
        eng_prof1.years_of_experience = 10
        eng_prof1.save()

        EngineerExpertise.objects.create(
            engineer=self.cloud_eng,
            expertise=self.exp_aws,
            proficiency_level=EngineerExpertise.ProficiencyLevel.LEAD,
            status=EngineerExpertise.VerificationStatus.APPROVED
        )
        EngineerExpertise.objects.create(
            engineer=self.cloud_eng,
            expertise=self.exp_k8s,
            proficiency_level=EngineerExpertise.ProficiencyLevel.EXPERT,
            status=EngineerExpertise.VerificationStatus.APPROVED
        )

        # 4. Create Database Engineer (Intermediate)
        self.db_eng = User.objects.create_user(
            username="db_specialist",
            password="Password123!",
            first_name="Alex",
            last_name="Smith",
            role=User.Role.ENGINEER
        )
        eng_prof2, _ = EngineerProfile.objects.get_or_create(user=self.db_eng)
        eng_prof2.designation = "Database Administrator"
        eng_prof2.years_of_experience = 4
        eng_prof2.save()

        EngineerExpertise.objects.create(
            engineer=self.db_eng,
            expertise=self.exp_postgres,
            proficiency_level=EngineerExpertise.ProficiencyLevel.INTERMEDIATE,
            status=EngineerExpertise.VerificationStatus.APPROVED
        )

    def test_tokenize_clean_and_stop_words(self):
        from appointments.ai_matcher import tokenize

        text = "We need a cloud architecture for AWS and Kubernetes with ci/cd pipelines!"
        tokens = tokenize(text)

        self.assertIn("cloud", tokens)
        self.assertIn("aws", tokens)
        self.assertIn("kubernetes", tokens)
        self.assertIn("ci/cd", tokens)
        self.assertNotIn("a", tokens)
        self.assertNotIn("and", tokens)
        self.assertNotIn("with", tokens)

        # Empty/None handling
        self.assertEqual(tokenize(""), [])
        self.assertEqual(tokenize(None), [])

    def test_cosine_similarity_edge_cases(self):
        from appointments.ai_matcher import cosine_similarity

        # Identical vectors
        v1 = {"aws": 2, "cloud": 1}
        v2 = {"aws": 2, "cloud": 1}
        self.assertAlmostEqual(cosine_similarity(v1, v2), 1.0, places=3)

        # Orthogonal vectors (no intersection)
        v3 = {"database": 1, "sql": 2}
        self.assertEqual(cosine_similarity(v1, v3), 0.0)

        # Empty vectors
        self.assertEqual(cosine_similarity({}, v1), 0.0)
        self.assertEqual(cosine_similarity(v1, {}), 0.0)

    def test_calculate_match_scores_domain_and_engineer_scoring(self):
        from appointments.ai_matcher import calculate_match_scores

        query = "We need assistance with AWS cloud architecture, Kubernetes containers, and infrastructure scaling."
        result = calculate_match_scores(query)

        self.assertEqual(result["status"], "success")
        self.assertIsNotNone(result["matched_service"])
        self.assertEqual(result["matched_service"]["id"], self.cloud_service.id)

        # Cloud engineer must be top ranked and shortlisted >= 80%
        engineers = result["engineers"]
        self.assertTrue(len(engineers) >= 2)

        top_eng = engineers[0]
        self.assertEqual(top_eng["id"], self.cloud_eng.id)
        self.assertGreaterEqual(top_eng["score"], 80)
        self.assertTrue(top_eng["is_shortlisted"])
        self.assertTrue(top_eng["is_recommended"])

        # Database engineer should have lower score for cloud query
        db_score_entry = next(e for e in engineers if e["id"] == self.db_eng.id)
        self.assertLess(db_score_entry["score"], top_eng["score"])

    def test_calculate_match_scores_database_domain(self):
        from appointments.ai_matcher import calculate_match_scores

        query = "PostgreSQL query tuning, indexing optimization, and high volume database performance."
        result = calculate_match_scores(query)

        self.assertEqual(result["matched_service"]["id"], self.db_service.id)
        self.assertEqual(result["top_engineer"]["id"], self.db_eng.id)
        self.assertGreaterEqual(result["top_engineer"]["score"], 80)
        self.assertTrue(result["top_engineer"]["is_shortlisted"])

    def test_proficiency_multiplier_influences_score(self):
        from accounts.models import EngineerProfile
        from appointments.ai_matcher import calculate_match_scores
        from services.models import EngineerExpertise

        # Create beginner engineer with same expertise
        beginner_eng = User.objects.create_user(
            username="beginner_cloud",
            password="Password123!",
            role=User.Role.ENGINEER
        )
        EngineerProfile.objects.get_or_create(user=beginner_eng)
        EngineerExpertise.objects.create(
            engineer=beginner_eng,
            expertise=self.exp_aws,
            proficiency_level=EngineerExpertise.ProficiencyLevel.BEGINNER,
            status=EngineerExpertise.VerificationStatus.APPROVED
        )

        result = calculate_match_scores("AWS Solutions Architecture")
        lead_entry = next(e for e in result["engineers"] if e["id"] == self.cloud_eng.id)
        beg_entry = next(e for e in result["engineers"] if e["id"] == beginner_eng.id)

        self.assertGreater(lead_entry["score"], beg_entry["score"])


class AIMatchApiEndpointTests(TestCase):
    def setUp(self):
        from services.models import Expertise, EngineerExpertise

        self.service = Service.objects.create(
            name="Cloud DevOps Architecture",
            description="AWS, GCP, Docker, Kubernetes, CI/CD."
        )
        self.eng = User.objects.create_user(
            username="api_eng",
            password="Password123!",
            role=User.Role.ENGINEER
        )
        exp = Expertise.objects.create(name="AWS DevOps")
        EngineerExpertise.objects.create(
            engineer=self.eng,
            expertise=exp,
            proficiency_level=EngineerExpertise.ProficiencyLevel.LEAD,
            status=EngineerExpertise.VerificationStatus.APPROVED
        )

    def test_ai_match_endpoint_post_json_success(self):
        import json

        url = reverse("appointments:ai_match")
        payload = {"text": "We need AWS DevOps consultation with Kubernetes."}
        response = self.client.post(url, data=json.dumps(payload), content_type="application/json")

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "success")
        self.assertIn("matched_service", data)
        self.assertIn("engineers", data)
        self.assertIn("extracted_keywords", data)
        self.assertEqual(data["matched_service"]["id"], self.service.id)
        self.assertTrue(len(data["engineers"]) >= 1)

    def test_ai_match_endpoint_empty_text_returns_400(self):
        import json

        url = reverse("appointments:ai_match")
        response = self.client.post(url, data=json.dumps({"text": ""}), content_type="application/json")
        self.assertEqual(response.status_code, 400)
        self.assertIn("error", response.json())

    def test_ai_match_endpoint_invalid_method_returns_405(self):
        url = reverse("appointments:ai_match")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 405)


class BusinessPolicyAndTieredCancellationTests(TestCase):
    def setUp(self):
        from datetime import datetime, timedelta
        from django.utils import timezone

        self.client_user = User.objects.create_user(
            username="policy_client",
            password="Password123!",
            role=User.Role.CLIENT
        )
        self.engineer_user = User.objects.create_user(
            username="policy_eng",
            password="Password123!",
            role=User.Role.ENGINEER
        )
        self.service = Service.objects.create(
            name="Policy Review Service",
            description="Testing business rules"
        )

        # Set up broad engineer availability for every day of the week
        for d in range(7):
            EngineerAvailability.objects.create(
                engineer=self.engineer_user,
                day_of_week=d,
                start_time=time(0, 0),
                end_time=time(23, 59)
            )

        self.future_date = timezone.localdate() + timedelta(days=5)

    def test_minimum_session_duration_policy(self):
        """Policy: Sessions must be at least 30 minutes in duration."""
        # 15 minutes session -> MUST FAIL
        with self.assertRaises(ValidationError) as ctx:
            validate_appointment_booking(
                engineer=self.engineer_user,
                appointment_date=self.future_date,
                start_time=time(10, 0),
                end_time=time(10, 15)
            )
        self.assertIn("[Policy Rule]", str(ctx.exception))
        self.assertIn("30 minutes", str(ctx.exception))

        # 30 minutes session -> MUST SUCCEED
        try:
            validate_appointment_booking(
                engineer=self.engineer_user,
                appointment_date=self.future_date,
                start_time=time(10, 0),
                end_time=time(10, 30)
            )
        except ValidationError:
            self.fail("30-minute session was unexpectedly rejected.")

    def test_minimum_booking_lead_time_policy(self):
        """Policy: Booking must be placed at least 6 hours in advance."""
        from django.utils import timezone
        from datetime import timedelta

        # Slot 2 hours from now -> MUST FAIL
        now = timezone.now()
        near_slot = now + timedelta(hours=2)
        with self.assertRaises(ValidationError) as ctx:
            validate_appointment_booking(
                engineer=self.engineer_user,
                appointment_date=near_slot.date(),
                start_time=near_slot.time(),
                end_time=(near_slot + timedelta(minutes=45)).time()
            )
        self.assertIn("[Policy Rule]", str(ctx.exception))
        self.assertIn("6 hours", str(ctx.exception))

    def test_max_daily_engineer_sessions_limit_policy(self):
        """Policy: Engineer cannot have more than 4 active sessions per day."""
        # Create 4 sessions on the same future date
        for i in range(4):
            Appointment.objects.create(
                client=self.client_user,
                engineer=self.engineer_user,
                service=self.service,
                appointment_date=self.future_date,
                start_time=time(8 + i * 2, 0),
                end_time=time(9 + i * 2, 0),
                project_title=f"Session #{i+1}",
                status=Appointment.Status.APPROVED
            )

        # 5th session on same date -> MUST FAIL
        with self.assertRaises(ValidationError) as ctx:
            validate_appointment_booking(
                engineer=self.engineer_user,
                appointment_date=self.future_date,
                start_time=time(18, 0),
                end_time=time(19, 0)
            )
        self.assertIn("[Policy Rule]", str(ctx.exception))
        self.assertIn("maximum capacity limit", str(ctx.exception))

    def test_tiered_cancellation_under_24_hours_requires_reason(self):
        """Tiered Cancellation: Cancelling < 24 hours requires mandatory reason."""
        from django.utils import timezone
        from datetime import timedelta
        from notifications.models import Notification

        # Create appointment scheduled in 4 hours
        now = timezone.now()
        appt_time = now + timedelta(hours=4)
        appt = Appointment.objects.create(
            client=self.client_user,
            engineer=self.engineer_user,
            service=self.service,
            appointment_date=appt_time.date(),
            start_time=appt_time.time(),
            end_time=(appt_time + timedelta(hours=1)).time(),
            project_title="Short Notice Cancellation Test",
            status=Appointment.Status.APPROVED
        )

        self.client.login(username="policy_client", password="Password123!")

        # 1. GET cancel page shows late cancellation notice
        res = self.client.get(reverse("appointments:appointment_cancel", args=[appt.id]))
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.context["is_late_cancellation"])

        # 2. POST without reason is rejected
        res_post_empty = self.client.post(reverse("appointments:appointment_cancel", args=[appt.id]), {"cancellation_reason": ""})
        self.assertEqual(res_post_empty.status_code, 200)
        appt.refresh_from_db()
        self.assertEqual(appt.status, Appointment.Status.APPROVED)

        # 3. POST with reason succeeds
        res_post_valid = self.client.post(
            reverse("appointments:appointment_cancel", args=[appt.id]),
            {"cancellation_reason": "Emergency production deployment"}
        )
        self.assertEqual(res_post_valid.status_code, 302)
        appt.refresh_from_db()
        self.assertEqual(appt.status, Appointment.Status.CANCELLED)
        self.assertEqual(appt.cancellation_reason, "Emergency production deployment")

        # Verify engineer was notified
        notif = Notification.objects.filter(user=self.engineer_user, appointment=appt).first()
        self.assertIsNotNone(notif)
        self.assertIn("Emergency production deployment", notif.message)

    def test_standard_cancellation_over_24_hours(self):
        """Tiered Cancellation: Cancelling >= 24 hours does not mandate reason."""
        appt = Appointment.objects.create(
            client=self.client_user,
            engineer=self.engineer_user,
            service=self.service,
            appointment_date=self.future_date,
            start_time=time(10, 0),
            end_time=time(11, 0),
            project_title="Advance Cancellation Test",
            status=Appointment.Status.PENDING
        )

        self.client.login(username="policy_client", password="Password123!")

        # GET cancel page
        res = self.client.get(reverse("appointments:appointment_cancel", args=[appt.id]))
        self.assertEqual(res.status_code, 200)
        self.assertFalse(res.context["is_late_cancellation"])

        # POST without reason succeeds
        res_post = self.client.post(reverse("appointments:appointment_cancel", args=[appt.id]), {"cancellation_reason": ""})
        self.assertEqual(res_post.status_code, 302)
        appt.refresh_from_db()
        self.assertEqual(appt.status, Appointment.Status.CANCELLED)





