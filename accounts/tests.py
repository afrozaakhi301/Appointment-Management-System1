from django.test import TestCase
from django.urls import reverse
from accounts.models import ClientProfile, EngineerProfile, User


class AccountsAuthenticationTests(TestCase):
    def setUp(self):
        self.client_user = User.objects.create_user(
            username="testclient",
            password="Password123!",
            email="client@example.com",
            role=User.Role.CLIENT
        )
        self.engineer_user = User.objects.create_user(
            username="testengineer",
            password="Password123!",
            email="eng@example.com",
            role=User.Role.ENGINEER
        )
        self.admin_user = User.objects.create_user(
            username="testadmin",
            password="Password123!",
            email="admin@example.com",
            role=User.Role.ADMIN
        )

    def test_client_registration_assigns_client_role(self):
        response = self.client.post(reverse("accounts:register"), {
            "username": "newclient",
            "first_name": "New",
            "last_name": "Client",
            "email": "newclient@example.com",
            "phone_number": "1234567890",
            "password1": "SecurePass123!",
            "password2": "SecurePass123!",
        })
        self.assertEqual(response.status_code, 302)
        new_user = User.objects.get(username="newclient")
        self.assertEqual(new_user.role, User.Role.CLIENT)
        self.assertTrue(ClientProfile.objects.filter(user=new_user).exists())

    def test_login_and_role_based_redirects(self):
        # Client redirect
        self.client.login(username="testclient", password="Password123!")
        res = self.client.get(reverse("accounts:redirect_after_login"))
        self.assertRedirects(res, reverse("dashboard:client_dashboard"))
        self.client.logout()

        # Engineer redirect
        self.client.login(username="testengineer", password="Password123!")
        res = self.client.get(reverse("accounts:redirect_after_login"))
        self.assertRedirects(res, reverse("dashboard:engineer_dashboard"))
        self.client.logout()

        # Admin redirect
        self.client.login(username="testadmin", password="Password123!")
        res = self.client.get(reverse("accounts:redirect_after_login"))
        self.assertRedirects(res, reverse("dashboard:admin_dashboard"))
        self.client.logout()

    def test_role_authorization_protections(self):
        # Client attempting to access Admin dashboard -> blocked
        self.client.login(username="testclient", password="Password123!")
        res = self.client.get(reverse("dashboard:admin_dashboard"))
        self.assertRedirects(res, reverse("accounts:redirect_after_login"), target_status_code=302)

        # Client attempting to access Engineer working availability -> blocked
        res = self.client.get(reverse("scheduling:manage_availability"))
        self.assertRedirects(res, reverse("accounts:redirect_after_login"), target_status_code=302)

        # Engineer attempting to access Admin dashboard -> blocked
        self.client.logout()
        self.client.login(username="testengineer", password="Password123!")
        res = self.client.get(reverse("dashboard:admin_dashboard"))
        self.assertRedirects(res, reverse("accounts:redirect_after_login"), target_status_code=302)
