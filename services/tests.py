from datetime import date, time
from django.test import Client, TestCase
from django.urls import reverse
from accounts.models import ClientProfile, EngineerProfile, User
from appointments.models import Appointment
from feedback.models import Feedback
from notifications.models import Notification
from services.models import EngineerExpertise, Expertise, Service


class ServiceAndReviewViewsTestCase(TestCase):
    def setUp(self):
        self.client = Client()

        # Create Admin User
        self.admin_user = User.objects.create_superuser(
            username="testadmin",
            email="admin@example.com",
            password="Password123!",
            role=User.Role.ADMIN,
            first_name="Admin",
            last_name="Super"
        )

        # Create Client User
        self.client_user = User.objects.create_user(
            username="testclient",
            email="client@example.com",
            password="Password123!",
            role=User.Role.CLIENT,
            first_name="Alice",
            last_name="Smith"
        )
        client_prof, _ = ClientProfile.objects.get_or_create(user=self.client_user)
        client_prof.organization = "TechCorp"
        client_prof.save()

        # Create Engineer User
        self.engineer_user = User.objects.create_user(
            username="testengineer",
            email="engineer@example.com",
            password="Password123!",
            role=User.Role.ENGINEER,
            first_name="Bob",
            last_name="Taylor"
        )
        eng_prof, _ = EngineerProfile.objects.get_or_create(user=self.engineer_user)
        eng_prof.designation = "Principal Cloud Architect"
        eng_prof.years_of_experience = 8
        eng_prof.bio = "Experienced cloud architect"
        eng_prof.save()

        # Create Expertise
        self.expertise_aws = Expertise.objects.create(name="AWS Cloud Architecture")
        self.expertise_python = Expertise.objects.create(name="Python & Django")

        # Create Service
        self.service = Service.objects.create(
            name="Cloud Architecture Review",
            description="Detailed review of AWS/GCP cloud topology",
            is_active=True
        )

        # Create Completed Appointment
        self.appointment = Appointment.objects.create(
            client=self.client_user,
            engineer=self.engineer_user,
            service=self.service,
            appointment_date=date.today(),
            start_time=time(10, 0),
            end_time=time(11, 0),
            project_title="AWS Multi-Region Migration",
            project_description="Need advice on multi-region failover",
            status=Appointment.Status.COMPLETED
        )

        # Create Feedback
        self.feedback = Feedback.objects.create(
            appointment=self.appointment,
            rating=5,
            comments="Bob provided outstanding architecture recommendations!"
        )

    def test_homepage_displays_reviews_and_ratings(self):
        response = self.client.get(reverse("home"))
        self.assertEqual(response.status_code, 200)
        self.assertIn("recent_reviews", response.context)
        self.assertIn("total_reviews", response.context)
        self.assertIn("overall_avg_rating", response.context)
        self.assertEqual(response.context["total_reviews"], 1)
        self.assertEqual(response.context["overall_avg_rating"], 5.0)
        
        # Verify rendered content
        self.assertContains(response, "What Our Clients Say")
        self.assertContains(response, "Bob provided outstanding architecture recommendations!")
        self.assertContains(response, "TechCorp")
        self.assertContains(response, "Alice Smith")

    def test_engineer_detail_displays_reviews_and_rating(self):
        response = self.client.get(reverse("services:engineer_detail", args=[self.engineer_user.id]))
        self.assertEqual(response.status_code, 200)
        self.assertIn("feedbacks", response.context)
        self.assertIn("avg_rating", response.context)
        self.assertIn("review_count", response.context)
        self.assertEqual(response.context["avg_rating"], 5.0)
        self.assertEqual(response.context["review_count"], 1)

        # Verify rendered content
        self.assertContains(response, "Client Reviews & Ratings")
        self.assertContains(response, "Bob provided outstanding architecture recommendations!")
        self.assertContains(response, "TechCorp")

    def test_engineer_adds_skill_creates_pending_verification_and_notifies_admin(self):
        self.client.login(username="testengineer", password="Password123!")
        
        # Submit skill verification request
        response = self.client.post(
            reverse("services:manage_my_expertise"),
            {
                "expertise": self.expertise_aws.id,
                "proficiency_level": EngineerExpertise.ProficiencyLevel.EXPERT,
            },
            follow=True
        )
        self.assertEqual(response.status_code, 200)
        
        # Check EngineerExpertise was created in PENDING status
        ee = EngineerExpertise.objects.get(engineer=self.engineer_user, expertise=self.expertise_aws)
        self.assertEqual(ee.status, EngineerExpertise.VerificationStatus.PENDING)
        self.assertEqual(ee.proficiency_level, EngineerExpertise.ProficiencyLevel.EXPERT)

        # Check Admin received in-app notification
        admin_notif = Notification.objects.filter(user=self.admin_user).first()
        self.assertIsNotNone(admin_notif)
        self.assertIn("requested verification for skill 'AWS Cloud Architecture'", admin_notif.message)

    def test_pending_skill_not_visible_on_public_profile_or_engineer_list(self):
        # Create pending skill
        EngineerExpertise.objects.create(
            engineer=self.engineer_user,
            expertise=self.expertise_aws,
            proficiency_level=EngineerExpertise.ProficiencyLevel.EXPERT,
            status=EngineerExpertise.VerificationStatus.PENDING
        )

        # Check public engineer detail page
        response = self.client.get(reverse("services:engineer_detail", args=[self.engineer_user.id]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context["expertises"]), 0)
        self.assertContains(response, "No specific expertise records listed.")

        # Check public engineer list page
        response = self.client.get(reverse("services:engineer_list"))
        self.assertEqual(response.status_code, 200)
        # Should not display verified skill badge on the engineer card
        self.assertEqual(len(response.context["engineers"][0].engineer_expertises.all()), 0)
        self.assertContains(response, "General Software Engineering")

    def test_admin_approves_skill_request_becomes_verified_and_visible(self):
        # Create pending skill
        ee = EngineerExpertise.objects.create(
            engineer=self.engineer_user,
            expertise=self.expertise_aws,
            proficiency_level=EngineerExpertise.ProficiencyLevel.LEAD,
            status=EngineerExpertise.VerificationStatus.PENDING
        )

        self.client.login(username="testadmin", password="Password123!")

        # Admin approves the request
        response = self.client.post(
            reverse("dashboard:manage_services"),
            {
                "action": "approve_skill_request",
                "ee_id": ee.id,
            },
            follow=True
        )
        self.assertEqual(response.status_code, 200)

        ee.refresh_from_db()
        self.assertEqual(ee.status, EngineerExpertise.VerificationStatus.APPROVED)
        self.assertEqual(ee.reviewed_by, self.admin_user)
        self.assertIsNotNone(ee.reviewed_at)

        # Engineer should receive notification
        eng_notif = Notification.objects.filter(user=self.engineer_user).first()
        self.assertIsNotNone(eng_notif)
        self.assertIn("approved and verified", eng_notif.message)

        # Now public engineer profile should display the verified skill
        self.client.logout()
        response = self.client.get(reverse("services:engineer_detail", args=[self.engineer_user.id]))
        self.assertContains(response, "AWS Cloud Architecture")
        self.assertContains(response, "Lead / Specialist")

    def test_admin_rejects_skill_request_with_reason_and_notifies_engineer(self):
        ee = EngineerExpertise.objects.create(
            engineer=self.engineer_user,
            expertise=self.expertise_python,
            proficiency_level=EngineerExpertise.ProficiencyLevel.INTERMEDIATE,
            status=EngineerExpertise.VerificationStatus.PENDING
        )

        self.client.login(username="testadmin", password="Password123!")

        # Admin rejects the request
        response = self.client.post(
            reverse("dashboard:manage_services"),
            {
                "action": "reject_skill_request",
                "ee_id": ee.id,
                "rejection_reason": "Please attach GitHub profile or code sample."
            },
            follow=True
        )
        self.assertEqual(response.status_code, 200)

        ee.refresh_from_db()
        self.assertEqual(ee.status, EngineerExpertise.VerificationStatus.REJECTED)
        self.assertEqual(ee.admin_notes, "Please attach GitHub profile or code sample.")

        # Check engineer notification
        eng_notif = Notification.objects.filter(user=self.engineer_user).first()
        self.assertIsNotNone(eng_notif)
        self.assertIn("rejected", eng_notif.message)
        self.assertIn("Please attach GitHub profile or code sample.", eng_notif.message)

    def test_engineer_resubmits_rejected_skill(self):
        # Create rejected skill
        ee = EngineerExpertise.objects.create(
            engineer=self.engineer_user,
            expertise=self.expertise_python,
            proficiency_level=EngineerExpertise.ProficiencyLevel.BEGINNER,
            status=EngineerExpertise.VerificationStatus.REJECTED,
            admin_notes="Not enough experience"
        )

        self.client.login(username="testengineer", password="Password123!")

        # Resubmit with higher proficiency
        response = self.client.post(
            reverse("services:manage_my_expertise"),
            {
                "expertise": self.expertise_python.id,
                "proficiency_level": EngineerExpertise.ProficiencyLevel.INTERMEDIATE,
            },
            follow=True
        )
        self.assertEqual(response.status_code, 200)

        ee.refresh_from_db()
        self.assertEqual(ee.status, EngineerExpertise.VerificationStatus.PENDING)
        self.assertEqual(ee.proficiency_level, EngineerExpertise.ProficiencyLevel.INTERMEDIATE)
        self.assertEqual(ee.admin_notes, "")

    def test_service_list_displays_scoping_banner_and_use_cases(self):
        # Create General Architecture service
        general_svc, _ = Service.objects.get_or_create(
            name="General Architecture & Technical Scoping",
            defaults={
                "description": "Scoping session for non-technical clients.",
                "is_active": True
            }
        )

        response = self.client.get(reverse("services:service_list"))
        self.assertEqual(response.status_code, 200)
        self.assertIn("general_service", response.context)
        self.assertEqual(response.context["general_service"], general_svc)

        # Verify banner text and button
        self.assertContains(response, "Not sure what technical service fits your project?")
        self.assertContains(response, "Book a <strong>General Architecture & Technical Scoping Session</strong>")
        self.assertContains(response, "Book Scoping Session")

        # Verify typical use cases section
        self.assertContains(response, "Typical Use Cases")
        self.assertContains(response, "MVP Development")
        self.assertContains(response, "AWS / GCP Migration")


