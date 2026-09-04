from datetime import date, time
from django.core.exceptions import ValidationError
from django.test import TestCase
from accounts.models import User
from appointments.models import Appointment
from feedback.models import Feedback
from services.models import Service


class FeedbackLogicTests(TestCase):
    def setUp(self):
        self.client_user = User.objects.create_user(
            username="fb_client",
            password="Password123!",
            role=User.Role.CLIENT
        )
        self.other_client = User.objects.create_user(
            username="fb_other",
            password="Password123!",
            role=User.Role.CLIENT
        )
        self.engineer_user = User.objects.create_user(
            username="fb_eng",
            password="Password123!",
            role=User.Role.ENGINEER
        )
        self.service = Service.objects.create(
            name="Code Review",
            description="Detailed code inspection."
        )

        self.appointment = Appointment.objects.create(
            client=self.client_user,
            engineer=self.engineer_user,
            service=self.service,
            appointment_date=date(2026, 9, 1),
            start_time=time(14, 0),
            end_time=time(15, 0),
            project_title="Security Audit",
            project_description="Audit desc",
            status=Appointment.Status.APPROVED
        )

    def test_feedback_before_completion_fails(self):
        # Feedback must be strictly blocked for all non-completed statuses
        non_completed_statuses = [
            Appointment.Status.PENDING,
            Appointment.Status.APPROVED,
            Appointment.Status.RESCHEDULED,
            Appointment.Status.CANCELLED,
            Appointment.Status.REJECTED,
        ]
        for status in non_completed_statuses:
            self.appointment.status = status
            self.appointment.save()
            fb = Feedback(
                appointment=self.appointment,
                rating=5,
                comments=f"Attempting feedback during {status}"
            )
            with self.assertRaises(ValidationError, msg=f"Feedback should have been blocked for status: {status}"):
                fb.full_clean()

    def test_feedback_after_completion_succeeds(self):
        # Transition to COMPLETED
        self.appointment.status = Appointment.Status.COMPLETED
        self.appointment.save()

        fb = Feedback(
            appointment=self.appointment,
            rating=5,
            comments="Excellent advice on microservice resilience."
        )
        fb.full_clean()
        fb.save()
        self.assertEqual(Feedback.objects.count(), 1)
        self.assertEqual(self.appointment.feedback.rating, 5)

    def test_duplicate_feedback_prevented(self):
        self.appointment.status = Appointment.Status.COMPLETED
        self.appointment.save()

        Feedback.objects.create(
            appointment=self.appointment,
            rating=4,
            comments="First review"
        )

        from django.db import transaction
        # Attempt to create second feedback for the same appointment -> fails due to OneToOne constraint
        with self.assertRaises(Exception):
            with transaction.atomic():
                Feedback.objects.create(
                    appointment=self.appointment,
                    rating=5,
                    comments="Second review attempt"
                )


class FeedbackViewTests(TestCase):
    def setUp(self):
        self.client_user = User.objects.create_user(
            username="test_client",
            password="Password123!",
            role=User.Role.CLIENT
        )
        self.engineer_user = User.objects.create_user(
            username="test_eng",
            password="Password123!",
            role=User.Role.ENGINEER
        )
        self.service = Service.objects.create(
            name="Architecture Design",
            description="System design consultation."
        )
        self.completed_appointment = Appointment.objects.create(
            client=self.client_user,
            engineer=self.engineer_user,
            service=self.service,
            appointment_date=date(2026, 9, 10),
            start_time=time(10, 0),
            end_time=time(11, 0),
            project_title="Cloud Migration Architecture",
            project_description="Plan AWS cloud migration.",
            status=Appointment.Status.COMPLETED
        )

    def test_submit_feedback_get_and_post(self):
        self.client.login(username="test_client", password="Password123!")
        
        # GET request to submit feedback page
        response = self.client.get(f"/feedback/submit/{self.completed_appointment.id}/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Give Rating & Write Feedback")

        # POST request to submit feedback
        response = self.client.post(f"/feedback/submit/{self.completed_appointment.id}/", {
            "rating": 5,
            "comments": "Super helpful consultation! Solved our latency bottleneck."
        }, follow=True)
        self.assertEqual(response.status_code, 200)
        
        # Verify feedback saved
        fb = Feedback.objects.get(appointment=self.completed_appointment)
        self.assertEqual(fb.rating, 5)
        self.assertEqual(fb.comments, "Super helpful consultation! Solved our latency bottleneck.")

    def test_update_existing_feedback(self):
        self.client.login(username="test_client", password="Password123!")
        
        Feedback.objects.create(
            appointment=self.completed_appointment,
            rating=4,
            comments="Good initial consultation."
        )

        # POST request to update existing feedback
        response = self.client.post(f"/feedback/submit/{self.completed_appointment.id}/", {
            "rating": 5,
            "comments": "Updated: Outstanding consultation and architecture advice."
        }, follow=True)
        self.assertEqual(response.status_code, 200)

        # Verify only 1 feedback exists and it has been updated
        self.assertEqual(Feedback.objects.filter(appointment=self.completed_appointment).count(), 1)
        fb = Feedback.objects.get(appointment=self.completed_appointment)
        self.assertEqual(fb.rating, 5)
        self.assertEqual(fb.comments, "Updated: Outstanding consultation and architecture advice.")

    def test_my_feedback_list_view(self):
        self.client.login(username="test_client", password="Password123!")
        
        Feedback.objects.create(
            appointment=self.completed_appointment,
            rating=5,
            comments="Very knowledgeable consultant."
        )

        response = self.client.get("/feedback/my-reviews/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "My Previous Feedback & Reviews")
        self.assertContains(response, "Cloud Migration Architecture")
        self.assertContains(response, "Very knowledgeable consultant.")

    def test_engineer_reviews_view(self):
        Feedback.objects.create(
            appointment=self.completed_appointment,
            rating=5,
            comments="Great guidance on database optimization."
        )

        self.client.login(username="test_eng", password="Password123!")
        response = self.client.get("/feedback/engineer-reviews/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Client Consultation Reviews & Ratings")
        self.assertContains(response, "Cloud Migration Architecture")
        self.assertContains(response, "Great guidance on database optimization.")

