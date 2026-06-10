from django.db import models


class Organization(models.Model):
    class OrganizationType(models.TextChoices):
        INDIVIDUAL = "individual", "Individual"
        NGO = "ngo", "NGO"
        UNIVERSITY = "university", "University"
        GOVERNMENT = "government", "Government"
        RESEARCH_GROUP = "research_group", "Research Group"
        SPONSOR = "sponsor", "Sponsor"
        OTHER = "other", "Other"

    name = models.CharField(max_length=255, unique=True)
    slug = models.SlugField(max_length=255, unique=True)
    organization_type = models.CharField(
        max_length=50,
        choices=OrganizationType.choices,
        default=OrganizationType.INDIVIDUAL,
    )

    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name