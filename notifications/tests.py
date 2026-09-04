from datetime import date, time
from django.test import RequestFactory, TestCase
from django.urls import reverse
from accounts.models import User
from appointments.models import Appointment
from notifications.context_processors import unread_notifications
from notifications.models import Notification
from notifications.utils import create_notification
from services.models import Service


class NotificationsTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.user1 = User.objects.create_user(
            username="notif_client",
            password="Password123!",
            role=User.Role.CLIENT
        )
        self.user2 = User.objects.create_user(
            username="notif_engineer",
            password="Password123!",
            role=User.Role.ENGINEER
        )
        self.other_user = User.objects.create_user(
            username="notif_other",
            password="Password123!",
            role=User.Role.CLIENT
        )
        self.service = Service.objects.create(
            name="Cloud Architecture Review",
            description="Thorough review of cloud deployment."
        )
        self.appointment = Appointment.objects.create(
            client=self.user1,
            engineer=self.user2,
            service=self.service,
            appointment_date=date(2026, 9, 15),
            start_time=time(10, 0),
            end_time=time(11, 0),
            project_title="Cloud Migration Audit",
            project_description="Audit infrastructure and scalability.",
            status=Appointment.Status.PENDING
        )

    def test_notification_creation_and_isolation(self):
        n1 = create_notification(self.user1, "Your appointment has been approved.", appointment=self.appointment)
        n2 = create_notification(self.user2, "New consultation request received.")

        self.assertIsNotNone(n1)
        self.assertIsNotNone(n2)

        # user1 has 1 notification linked to appointment
        user1_notifs = Notification.objects.filter(user=self.user1)
        self.assertEqual(user1_notifs.count(), 1)
        self.assertFalse(user1_notifs.first().is_read)
        self.assertEqual(user1_notifs.first().appointment, self.appointment)

        # user2 has 1 notification
        user2_notifs = Notification.objects.filter(user=self.user2)
        self.assertEqual(user2_notifs.count(), 1)

    def test_context_processor(self):
        create_notification(self.user1, "Message 1")
        create_notification(self.user1, "Message 2")
        create_notification(self.user2, "Engineer Message")

        # Authenticated user context
        request = self.factory.get("/")
        request.user = self.user1
        ctx = unread_notifications(request)
        self.assertEqual(ctx["unread_notifications_count"], 2)
        self.assertEqual(len(ctx["recent_notifications"]), 2)

        # Mark 1 as read
        n = Notification.objects.filter(user=self.user1).first()
        n.is_read = True
        n.save()

        ctx_after = unread_notifications(request)
        self.assertEqual(ctx_after["unread_notifications_count"], 1)

        # Anonymous user context
        from django.contrib.auth.models import AnonymousUser
        request.user = AnonymousUser()
        anon_ctx = unread_notifications(request)
        self.assertEqual(anon_ctx["unread_notifications_count"], 0)
        self.assertEqual(anon_ctx["recent_notifications"], [])

    def test_list_view_and_isolation(self):
        create_notification(self.user1, "User1 Notification")
        create_notification(self.user2, "User2 Notification")

        self.client.login(username="notif_client", password="Password123!")
        response = self.client.get(reverse("notifications:notification_list"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "User1 Notification")
        self.assertNotContains(response, "User2 Notification")

    def test_mark_as_read_view_and_redirect(self):
        n = create_notification(self.user1, "Consultation updated", appointment=self.appointment)
        self.assertFalse(n.is_read)

        self.client.login(username="notif_client", password="Password123!")
        response = self.client.get(reverse("notifications:mark_as_read", args=[n.id]))
        
        # Should redirect to appointment detail
        self.assertRedirects(response, reverse("appointments:appointment_detail", args=[self.appointment.id]))
        
        n.refresh_from_db()
        self.assertTrue(n.is_read)

    def test_mark_as_read_idor_protection(self):
        n2 = create_notification(self.user2, "Private engineer message")

        # User 1 tries to mark User 2's notification as read
        self.client.login(username="notif_client", password="Password123!")
        response = self.client.get(reverse("notifications:mark_as_read", args=[n2.id]))
        self.assertEqual(response.status_code, 404)

        n2.refresh_from_db()
        self.assertFalse(n2.is_read)

    def test_mark_all_as_read_view(self):
        create_notification(self.user1, "Msg A")
        create_notification(self.user1, "Msg B")
        create_notification(self.user2, "Msg C")

        self.client.login(username="notif_client", password="Password123!")
        response = self.client.get(reverse("notifications:mark_all_as_read"))
        self.assertRedirects(response, reverse("notifications:notification_list"))

        # User1's notifications should now all be read
        self.assertEqual(Notification.objects.filter(user=self.user1, is_read=False).count(), 0)
        # User2's notification must remain unread
        self.assertEqual(Notification.objects.filter(user=self.user2, is_read=False).count(), 1)

    def test_filter_buttons_status_and_query(self):
        n1 = create_notification(self.user1, "Important deployment alert") # unread
        n2 = create_notification(self.user1, "General weekly summary")     # read
        n2.is_read = True
        n2.save()

        self.client.login(username="notif_client", password="Password123!")

        # 1. Filter by unread
        res_unread = self.client.get(reverse("notifications:notification_list") + "?status=unread")
        self.assertEqual(res_unread.status_code, 200)
        unread_messages = [item.message for item in res_unread.context["notifications"]]
        self.assertIn("Important deployment alert", unread_messages)
        self.assertNotIn("General weekly summary", unread_messages)

        # 2. Filter by read
        res_read = self.client.get(reverse("notifications:notification_list") + "?status=read")
        self.assertEqual(res_read.status_code, 200)
        read_messages = [item.message for item in res_read.context["notifications"]]
        self.assertIn("General weekly summary", read_messages)
        self.assertNotIn("Important deployment alert", read_messages)

        # 3. Filter by search query
        res_q = self.client.get(reverse("notifications:notification_list") + "?q=deployment")
        self.assertEqual(res_q.status_code, 200)
        q_messages = [item.message for item in res_q.context["notifications"]]
        self.assertIn("Important deployment alert", q_messages)
        self.assertNotIn("General weekly summary", q_messages)

    def test_notification_detail_client_access(self):
        n = create_notification(self.user1, "Your appointment was confirmed by the engineer.", appointment=self.appointment)
        self.client.login(username="notif_client", password="Password123!")

        response = self.client.get(reverse("notifications:notification_detail", args=[n.id]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Notification Details")
        self.assertContains(response, "Your appointment was confirmed by the engineer.")
        self.assertContains(response, "Cloud Migration Audit")
        
        # Verify auto-mark as read
        n.refresh_from_db()
        self.assertTrue(n.is_read)

    def test_notification_detail_engineer_access(self):
        n = create_notification(self.user2, "New consultation request submitted by client.", appointment=self.appointment)
        self.client.login(username="notif_engineer", password="Password123!")

        response = self.client.get(reverse("notifications:notification_detail", args=[n.id]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Notification Details")
        self.assertContains(response, "New consultation request submitted by client.")
        self.assertContains(response, "Cloud Migration Audit")

        n.refresh_from_db()
        self.assertTrue(n.is_read)

    def test_notification_detail_idor_forbidden(self):
        n = create_notification(self.user2, "Confidential engineer notification.")
        # Client tries to view engineer's notification detail
        self.client.login(username="notif_client", password="Password123!")

        response = self.client.get(reverse("notifications:notification_detail", args=[n.id]))
        self.assertEqual(response.status_code, 404)

    def test_toggle_notification_read(self):
        n = create_notification(self.user1, "Test status toggle")
        n.is_read = True
        n.save()

        self.client.login(username="notif_client", password="Password123!")
        response = self.client.get(reverse("notifications:toggle_read", args=[n.id]))
        self.assertRedirects(response, reverse("notifications:notification_list"))

        n.refresh_from_db()
        self.assertFalse(n.is_read)

    def test_delete_notification(self):
        n = create_notification(self.user1, "Notification to be deleted")
        self.client.login(username="notif_client", password="Password123!")

        response = self.client.get(reverse("notifications:delete_notification", args=[n.id]))
        self.assertRedirects(response, reverse("notifications:notification_list"))
        self.assertFalse(Notification.objects.filter(id=n.id).exists())

