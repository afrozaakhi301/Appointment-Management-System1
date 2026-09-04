from django.contrib.auth.models import AbstractUser
from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver


class User(AbstractUser):
    class Role(models.TextChoices):
        CLIENT = "Client", "Client"
        ENGINEER = "Engineer", "Software Engineer"
        ADMIN = "Admin", "Admin"

    role = models.CharField(
        max_length=20,
        choices=Role.choices,
        default=Role.CLIENT,
        db_index=True
    )

    phone_number = models.CharField(
        max_length=20,
        blank=True
    )

    @property
    def is_client(self):
        return self.role == self.Role.CLIENT

    @property
    def is_engineer(self):
        return self.role == self.Role.ENGINEER

    @property
    def is_admin_user(self):
        return self.role == self.Role.ADMIN or self.is_superuser

    def __str__(self):
        full_name = self.get_full_name()
        if full_name:
            return f"{full_name} ({self.username}) - {self.role}"
        return f"{self.username} - {self.role}"


class ClientProfile(models.Model):
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="client_profile"
    )
    address = models.TextField(blank=True)
    organization = models.CharField(max_length=150, blank=True)

    def __str__(self):
        return f"ClientProfile: {self.user.username}"


class EngineerProfile(models.Model):
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="engineer_profile"
    )
    designation = models.CharField(max_length=100, blank=True, default="Software Engineer")
    bio = models.TextField(blank=True)
    years_of_experience = models.PositiveIntegerField(default=0)
    profile_photo = models.ImageField(
        upload_to="profile_photos/",
        blank=True,
        null=True
    )

    def __str__(self):
        return f"EngineerProfile: {self.user.username} ({self.designation})"


@receiver(post_save, sender=User)
def create_or_update_user_profile(sender, instance, created, **kwargs):
    if instance.role == User.Role.CLIENT:
        ClientProfile.objects.get_or_create(user=instance)
    elif instance.role == User.Role.ENGINEER:
        EngineerProfile.objects.get_or_create(user=instance)