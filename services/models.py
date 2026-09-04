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

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["engineer", "expertise"], name="unique_engineer_expertise")
        ]
        verbose_name = "Engineer Expertise"
        verbose_name_plural = "Engineer Expertises"

    def __str__(self):
        return f"{self.engineer.get_full_name() or self.engineer.username} - {self.expertise.name} ({self.proficiency_level})"
