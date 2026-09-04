from django.conf import settings
from django.db import models


class Service(models.Model):
    name = models.CharField(max_length=150, unique=True)
    description = models.TextField()
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class Expertise(models.Model):
    name = models.CharField(max_length=100, unique=True)

    class Meta:
        verbose_name_plural = "Expertises"
        ordering = ["name"]

    def __str__(self):
        return self.name


class EngineerExpertise(models.Model):
    class ProficiencyLevel(models.TextChoices):
        BEGINNER = "Beginner", "Beginner"
        INTERMEDIATE = "Intermediate", "Intermediate"
        EXPERT = "Expert", "Expert"
        LEAD = "Lead / Specialist", "Lead / Specialist"

    class VerificationStatus(models.TextChoices):
        PENDING = "Pending", "Pending Verification"
        APPROVED = "Approved", "Verified / Approved"
        REJECTED = "Rejected", "Rejected"

    engineer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="engineer_expertises",
        limit_choices_to={"role": "Engineer"}
    )
    expertise = models.ForeignKey(
        Expertise,
        on_delete=models.CASCADE,
        related_name="expertise_engineers"
    )
    proficiency_level = models.CharField(
        max_length=50,
        choices=ProficiencyLevel.choices,
        default=ProficiencyLevel.INTERMEDIATE
    )
    status = models.CharField(
        max_length=20,
        choices=VerificationStatus.choices,
        default=VerificationStatus.APPROVED
    )
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reviewed_skills"
    )
    admin_notes = models.TextField(blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["engineer", "expertise"], name="unique_engineer_expertise")
        ]
        verbose_name = "Engineer Expertise"
        verbose_name_plural = "Engineer Expertises"
        ordering = ["-created_at", "expertise__name"]

    def __str__(self):
        return f"{self.engineer.get_full_name() or self.engineer.username} - {self.expertise.name} ({self.proficiency_level}) [{self.status}]"

    @property
    def is_approved(self):
        return self.status == self.VerificationStatus.APPROVED

    @property
    def is_pending(self):
        return self.status == self.VerificationStatus.PENDING

    @property
    def is_rejected(self):
        return self.status == self.VerificationStatus.REJECTED

