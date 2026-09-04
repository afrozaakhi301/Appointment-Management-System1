from datetime import date, time
from django.core.exceptions import ValidationError
from django.test import TestCase
from accounts.models import User
from scheduling.models import EngineerAvailability, EngineerLeave


class SchedulingModelTests(TestCase):
    def setUp(self):
        self.engineer = User.objects.create_user(
            username="eng_sched",
            password="Password123!",
            role=User.Role.ENGINEER
        )

    def test_availability_valid_and_invalid_times(self):
        # Valid slot
        avail = EngineerAvailability(
            engineer=self.engineer,
            day_of_week=0,  # Monday
            start_time=time(9, 0),
            end_time=time(17, 0)
        )
        avail.full_clean()
        avail.save()
        self.assertEqual(EngineerAvailability.objects.count(), 1)

        # Invalid slot: start_time >= end_time
        bad_avail = EngineerAvailability(
            engineer=self.engineer,
            day_of_week=1,
            start_time=time(17, 0),
            end_time=time(9, 0)
        )
        with self.assertRaises(ValidationError):
            bad_avail.full_clean()

    def test_leave_valid_and_invalid_dates(self):
        # Valid leave
        leave = EngineerLeave(
            engineer=self.engineer,
            start_date=date(2026, 9, 1),
            end_date=date(2026, 9, 5),
            reason="Conference"
        )
        leave.full_clean()
        leave.save()
        self.assertEqual(EngineerLeave.objects.count(), 1)

        # Invalid leave: start_date > end_date
        bad_leave = EngineerLeave(
            engineer=self.engineer,
            start_date=date(2026, 9, 10),
            end_date=date(2026, 9, 5)
        )
        with self.assertRaises(ValidationError):
            bad_leave.full_clean()

    def test_api_schedule_check_suggestions(self):
        # Monday (0) 09:00 - 17:00
        EngineerAvailability.objects.create(
            engineer=self.engineer,
            day_of_week=0,
            start_time=time(9, 0),
            end_time=time(17, 0)
        )

        # 2026-09-07 is Monday
        res = self.client.get(f"/scheduling/api/check/{self.engineer.id}/?date=2026-09-07")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["status"], "available")
        self.assertEqual(len(data["working_slots"]), 1)
        self.assertGreater(len(data["suggested_slots"]), 0)

        # Tuesday (1) is not configured
        res_tue = self.client.get(f"/scheduling/api/check/{self.engineer.id}/?date=2026-09-08")
        self.assertEqual(res_tue.status_code, 200)
        data_tue = res_tue.json()
        self.assertEqual(data_tue["status"], "not_available")
        self.assertIn("weekly_schedule", data_tue)

        # Leave check
        EngineerLeave.objects.create(
            engineer=self.engineer,
            start_date=date(2026, 9, 14),
            end_date=date(2026, 9, 15),
            reason="Vacation"
        )
        res_leave = self.client.get(f"/scheduling/api/check/{self.engineer.id}/?date=2026-09-14")
        self.assertEqual(res_leave.status_code, 200)
        data_leave = res_leave.json()
        self.assertEqual(data_leave["status"], "on_leave")
        self.assertEqual(data_leave["leave_end"], "2026-09-15")
