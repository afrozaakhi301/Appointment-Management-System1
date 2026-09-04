from datetime import date, time
from django.test import Client, TestCase
from django.urls import reverse
from accounts.models import ClientProfile, EngineerProfile, User
from appointments.models import Appointment
from feedback.models import Feedback
from services.models import Service


class ServiceAndReviewViewsTestCase(TestCase):
    def setUp(self):
        self.client = Client()

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
