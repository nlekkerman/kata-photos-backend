from django.core.management.base import BaseCommand

from access.models import Capability


class Command(BaseCommand):
    help = "Seed canonical observation capabilities for Kata Wild RBAC."

    OBSERVATION_CAPABILITIES = [
        {
            "code": "view_observations",
            "name": "View observations",
            "category": "observations",
            "description": "Allows viewing observation records where scope, visibility, and sensitivity rules allow.",
        },
        {
            "code": "create_observations",
            "name": "Create observations",
            "category": "observations",
            "description": "Allows creating draft observation records.",
        },
        {
            "code": "submit_observations",
            "name": "Submit observations",
            "category": "observations",
            "description": "Allows submitting observation records for review.",
        },
        {
            "code": "edit_observations",
            "name": "Edit observations",
            "category": "observations",
            "description": "Allows editing observation records where policy allows.",
        },
        {
            "code": "revise_observations",
            "name": "Revise observations",
            "category": "observations",
            "description": "Allows creating scientific revisions for observation records.",
        },
        {
            "code": "review_observations",
            "name": "Review observations",
            "category": "observations",
            "description": "Allows reviewing submitted observation records.",
        },
        {
            "code": "verify_observations",
            "name": "Verify observations",
            "category": "observations",
            "description": "Allows verifying observation records as human-reviewed scientific truth.",
        },
        {
            "code": "reject_observations",
            "name": "Reject observations",
            "category": "observations",
            "description": "Allows rejecting observation records that do not meet scientific or evidence standards.",
        },
        {
            "code": "publish_observations",
            "name": "Publish observations",
            "category": "observations",
            "description": "Allows publishing observation records after verification and safety checks.",
        },
        {
            "code": "unpublish_observations",
            "name": "Unpublish observations",
            "category": "observations",
            "description": "Allows removing observation records from published/public availability.",
        },
        {
            "code": "view_unpublished_observations",
            "name": "View unpublished observations",
            "category": "observations",
            "description": "Allows viewing unpublished observation records where scope allows.",
        },
        {
            "code": "view_rejected_observations",
            "name": "View rejected observations",
            "category": "observations",
            "description": "Allows viewing rejected observation records where scope allows.",
        },
        {
            "code": "view_sensitive_observations",
            "name": "View sensitive observations",
            "category": "observations",
            "description": "Allows viewing sensitive observation records where policy and scope allow.",
        },
        {
            "code": "view_observation_revisions",
            "name": "View observation revisions",
            "category": "observations",
            "description": "Allows viewing observation revision/history records.",
        },
    ]

    def handle(self, *args, **options):
        created_count = 0
        skipped_count = 0
        filled_missing_count = 0

        for capability_data in self.OBSERVATION_CAPABILITIES:
            capability, created = Capability.objects.get_or_create(
                code=capability_data["code"],
                defaults={
                    "name": capability_data["name"],
                    "category": capability_data["category"],
                    "description": capability_data["description"],
                    "is_active": True,
                },
            )

            if created:
                created_count += 1
                self.stdout.write(
                    self.style.SUCCESS(f"Created: {capability.code}")
                )
                continue

            changed_fields = []

            # Existing capabilities are not overwritten.
            # We only fill empty/missing fields to keep the command safe and rerunnable.
            if not capability.name:
                capability.name = capability_data["name"]
                changed_fields.append("name")

            if not capability.category:
                capability.category = capability_data["category"]
                changed_fields.append("category")

            if not capability.description:
                capability.description = capability_data["description"]
                changed_fields.append("description")

            # If an existing capability was manually disabled, leave it disabled.
            # Do not force is_active=True on existing records.

            if changed_fields:
                capability.save(update_fields=changed_fields)
                filled_missing_count += 1
                self.stdout.write(
                    self.style.WARNING(
                        f"Filled missing fields for {capability.code}: {', '.join(changed_fields)}"
                    )
                )
            else:
                skipped_count += 1
                self.stdout.write(f"Skipped existing: {capability.code}")

        self.stdout.write(
            self.style.SUCCESS(
                "Observation capability seed complete. "
                f"Created: {created_count}. "
                f"Filled missing: {filled_missing_count}. "
                f"Skipped existing: {skipped_count}."
            )
        )