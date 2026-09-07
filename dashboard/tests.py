from datetime import date, time, timedelta
from django.test import Client, TestCase
from django.urls import reverse
from accounts.models import User
from appointments.models import Appointment
from dashboard.analytics import (
    get_completion_kpis,
    get_daily_completion_breakdown,
    get_weekly_completion_breakdown,
    get_monthly_completion_breakdown,
    get_service_and_engineer_breakdown,
    get_engineer_workload_distribution,
)
from dashboard.models import ActivityLog
from dashboard.utils import log_activity
from services.models import Service


class DashboardActivityLogTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="log_user",
            password="Password123!",
            role=User.Role.ADMIN
        )

    def test_log_activity_creation(self):
        log_activity(self.user, "Created a new test consultation service")
        self.assertEqual(ActivityLog.objects.count(), 1)
        log_entry = ActivityLog.objects.first()
        self.assertEqual(log_entry.user, self.user)
        self.assertIn("Created a new test consultation service", log_entry.action)

    def test_anonymous_log_activity(self):
        log_activity(None, "System automated maintenance completed")
        self.assertEqual(ActivityLog.objects.count(), 1)
        log_entry = ActivityLog.objects.first()
        self.assertIsNone(log_entry.user)


class AppointmentTrackingAnalyticsTests(TestCase):
    def setUp(self):
        self.client_user = User.objects.create_user(
            username="test_client",
            password="Password123!",
            role=User.Role.CLIENT
        )
        self.engineer_1 = User.objects.create_user(
            username="eng_one",
            password="Password123!",
            role=User.Role.ENGINEER
        )
        self.engineer_2 = User.objects.create_user(
            username="eng_two",
            password="Password123!",
            role=User.Role.ENGINEER
        )
        self.service_1 = Service.objects.create(name="Cloud Architecture", description="Cloud consulting", is_active=True)
        self.service_2 = Service.objects.create(name="DB Optimization", description="DB tuning", is_active=True)

        self.today = date.today()
        self.yesterday = self.today - timedelta(days=1)
        self.last_week = self.today - timedelta(days=7)
        self.last_month = self.today - timedelta(days=35)

        # 1. Completed today by engineer_1
        Appointment.objects.create(
            client=self.client_user,
            engineer=self.engineer_1,
            service=self.service_1,
            appointment_date=self.today,
            start_time=time(10, 0),
            end_time=time(11, 0),
            project_title="Cloud Migration Session",
            status=Appointment.Status.COMPLETED
        )

        # 2. Completed yesterday by engineer_1
        Appointment.objects.create(
            client=self.client_user,
            engineer=self.engineer_1,
            service=self.service_1,
            appointment_date=self.yesterday,
            start_time=time(14, 0),
            end_time=time(15, 0),
            project_title="Cloud Review Session",
            status=Appointment.Status.COMPLETED
        )

        # 3. Completed last week by engineer_2
        Appointment.objects.create(
            client=self.client_user,
            engineer=self.engineer_2,
            service=self.service_2,
            appointment_date=self.last_week,
            start_time=time(9, 0),
            end_time=time(10, 0),
            project_title="DB Index Tuning",
            status=Appointment.Status.COMPLETED
        )

        # 4. Pending appointment (should not be counted as completed)
        Appointment.objects.create(
            client=self.client_user,
            engineer=self.engineer_1,
            service=self.service_1,
            appointment_date=self.today,
            start_time=time(16, 0),
            end_time=time(17, 0),
            project_title="Pending Session",
            status=Appointment.Status.PENDING
        )

    def test_get_completion_kpis(self):
        kpis = get_completion_kpis(reference_date=self.today)
        self.assertEqual(kpis["done_today"], 1)
        self.assertEqual(kpis["done_yesterday"], 1)
        self.assertEqual(kpis["daily_diff"], 0)
        self.assertGreaterEqual(kpis["done_this_week"], 1)
        self.assertEqual(kpis["total_completed"], 3)

    def test_get_completion_kpis_filtered_by_engineer(self):
        kpis_eng2 = get_completion_kpis(engineer=self.engineer_2, reference_date=self.today)
        self.assertEqual(kpis_eng2["done_today"], 0)
        self.assertEqual(kpis_eng2["total_completed"], 1)

    def test_get_daily_completion_breakdown(self):
        daily = get_daily_completion_breakdown(reference_date=self.today, days_back=7)
        self.assertIn("daily_breakdown", daily)
        self.assertEqual(len(daily["daily_breakdown"]), 7)
        self.assertEqual(daily["chart_data"][-1], 1)  # today count

    def test_get_weekly_completion_breakdown(self):
        weekly = get_weekly_completion_breakdown(reference_date=self.today, weeks_back=4)
        self.assertEqual(len(weekly["weekly_breakdown"]), 4)
        self.assertGreaterEqual(weekly["total_in_period"], 2)

    def test_get_monthly_completion_breakdown(self):
        monthly = get_monthly_completion_breakdown(reference_date=self.today, year=self.today.year)
        self.assertEqual(len(monthly["monthly_breakdown"]), 12)
        curr_month_entry = monthly["monthly_breakdown"][self.today.month - 1]
        self.assertGreaterEqual(curr_month_entry["count"], 1)

    def test_get_service_and_engineer_breakdown(self):
        breakdown = get_service_and_engineer_breakdown()
        self.assertEqual(len(breakdown["service_breakdown"]), 2)
        self.assertEqual(len(breakdown["engineer_breakdown"]), 2)


class AppointmentTrackingViewsTests(TestCase):
    def setUp(self):
        self.client_http = Client()
        self.admin_user = User.objects.create_user(
            username="admin_user",
            password="AdminPassword123!",
            role=User.Role.ADMIN,
            is_staff=True,
            is_superuser=True
        )
        self.client_user = User.objects.create_user(
            username="regular_client",
            password="ClientPassword123!",
            role=User.Role.CLIENT
        )
        self.engineer_user = User.objects.create_user(
            username="eng_user",
            password="EngineerPassword123!",
            role=User.Role.ENGINEER
        )

    def test_admin_tracking_view_requires_admin(self):
        # Unauthenticated redirects
        response = self.client_http.get(reverse("dashboard:appointment_tracking"))
        self.assertEqual(response.status_code, 302)

        # Client access denied
        self.client_http.login(username="regular_client", password="ClientPassword123!")
        response = self.client_http.get(reverse("dashboard:appointment_tracking"))
        self.assertEqual(response.status_code, 302)

        # Admin access granted
        self.client_http.login(username="admin_user", password="AdminPassword123!")
        response = self.client_http.get(reverse("dashboard:appointment_tracking"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "dashboard/appointment_tracking.html")
        self.assertIn("kpis", response.context)
        self.assertIn("daily_data", response.context)
        self.assertIn("weekly_data", response.context)
        self.assertIn("monthly_data", response.context)

    def test_admin_tracking_timeframes(self):
        self.client_http.login(username="admin_user", password="AdminPassword123!")
        for tf in ["daily", "weekly", "monthly", "overview"]:
            response = self.client_http.get(reverse("dashboard:appointment_tracking") + f"?timeframe={tf}")
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.context["timeframe"], tf)

    def test_export_tracking_csv(self):
        self.client_http.login(username="admin_user", password="AdminPassword123!")
        response = self.client_http.get(reverse("dashboard:export_tracking_csv"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "text/csv")
        self.assertIn("attachment; filename=", response["Content-Disposition"])
        content = response.content.decode("utf-8")
        self.assertIn("Appointment ID", content)
        self.assertIn("Project Title", content)
        self.assertIn("Client Username", content)


class EngineerWorkloadAnalyticsTests(TestCase):
    def setUp(self):
        self.client_http = Client()
        self.admin_user = User.objects.create_user(
            username="analytics_admin",
            password="Password123!",
            role=User.Role.ADMIN,
            is_staff=True,
            is_superuser=True
        )
        self.client_user = User.objects.create_user(
            username="analytics_client",
            password="Password123!",
            role=User.Role.CLIENT
        )
        self.service = Service.objects.create(
            name="Architecture Review",
            description="System Architecture Consulting",
            is_active=True
        )

        # Create 3 engineers: one overloaded (4 active), one optimal (2 active), one available (0 active)
        self.eng_overloaded = User.objects.create_user(
            username="eng_overloaded",
            password="Password123!",
            role=User.Role.ENGINEER
        )
        self.eng_optimal = User.objects.create_user(
            username="eng_optimal",
            password="Password123!",
            role=User.Role.ENGINEER
        )
        self.eng_available = User.objects.create_user(
            username="eng_available",
            password="Password123!",
            role=User.Role.ENGINEER
        )

        # 4 active sessions for eng_overloaded
        for i in range(4):
            Appointment.objects.create(
                client=self.client_user,
                engineer=self.eng_overloaded,
                service=self.service,
                appointment_date=date.today(),
                start_time=time(8 + i * 2, 0),
                end_time=time(9 + i * 2, 0),
                project_title=f"Overloaded Task #{i+1}",
                status=Appointment.Status.APPROVED
            )

        # 2 active sessions for eng_optimal
        for i in range(2):
            Appointment.objects.create(
                client=self.client_user,
                engineer=self.eng_optimal,
                service=self.service,
                appointment_date=date.today(),
                start_time=time(9 + i * 3, 0),
                end_time=time(10 + i * 3, 0),
                project_title=f"Optimal Task #{i+1}",
                status=Appointment.Status.PENDING
            )

        # 1 completed session for eng_available
        Appointment.objects.create(
            client=self.client_user,
            engineer=self.eng_available,
            service=self.service,
            appointment_date=date.today() - timedelta(days=1),
            start_time=time(10, 0),
            end_time=time(11, 0),
            project_title="Completed Task",
            status=Appointment.Status.COMPLETED
        )

    def test_get_engineer_workload_distribution(self):
        workload = get_engineer_workload_distribution()
        self.assertEqual(len(workload), 3)

        # Find entries
        overloaded_entry = next(w for w in workload if w["engineer"].id == self.eng_overloaded.id)
        optimal_entry = next(w for w in workload if w["engineer"].id == self.eng_optimal.id)
        available_entry = next(w for w in workload if w["engineer"].id == self.eng_available.id)

        # Assert Overloaded
        self.assertEqual(overloaded_entry["active_load"], 4)
        self.assertEqual(overloaded_entry["capacity_pct"], 100)
        self.assertEqual(overloaded_entry["status_label"], "Overloaded")
        self.assertEqual(overloaded_entry["status_badge"], "bg-danger")
        self.assertEqual(overloaded_entry["progress_bar"], "bg-danger")

        # Assert Optimal
        self.assertEqual(optimal_entry["active_load"], 2)
        self.assertEqual(optimal_entry["capacity_pct"], 50)
        self.assertEqual(optimal_entry["status_label"], "Optimal")
        self.assertEqual(optimal_entry["status_badge"], "bg-success")
        self.assertEqual(optimal_entry["progress_bar"], "bg-success")

        # Assert Available
        self.assertEqual(available_entry["active_load"], 0)
        self.assertEqual(available_entry["completed_count"], 1)
        self.assertEqual(available_entry["capacity_pct"], 0)
        self.assertEqual(available_entry["status_label"], "Available")
        self.assertEqual(available_entry["status_badge"], "bg-info")
        self.assertEqual(available_entry["progress_bar"], "bg-info")

    def test_admin_reports_view_renders_workload_distribution(self):
        self.client_http.login(username="analytics_admin", password="Password123!")
        response = self.client_http.get(reverse("dashboard:admin_reports"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "dashboard/admin_reports.html")
        self.assertIn("workload_distribution", response.context)
        self.assertEqual(len(response.context["workload_distribution"]), 3)
        content = response.content.decode("utf-8")
        self.assertIn("Engineer Workload & Capacity Balance", content)
        self.assertIn("Overloaded", content)
        self.assertIn("Optimal", content)
        self.assertIn("Available", content)


