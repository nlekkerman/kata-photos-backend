from django.core.management.base import BaseCommand

from access.models import Capability


class Command(BaseCommand):
    help = "Seed the initial Kata Wild RBAC capabilities used for MVP admin testing."

    def handle(self, *args, **options):
        # These capabilities are the first backend permission keys for the MVP foundation.
        # Code is the stable permission key used later by backend policies.
        # Name and description are only human-readable admin helpers.
        #
        # Current MVP purpose:
        # - allow us to create test roles in Django admin
        # - prepare the access layer before projects are implemented
        # - avoid hardcoded role-name authorization
        #
        # Left for later:
        # - policies will check these capability codes
        # - scopes will limit where capabilities apply
        # - audit records will track permission-affecting changes
        capabilities = [
            {
                "code": "view_audit_logs",
                "name": "View audit logs",
                "category": "audit",
                "description": "Allows viewing audit records.",
                "is_active": True,
            },
            {
                "code": "view_projects",
                "name": "View projects",
                "category": "projects",
                "description": "Allows viewing project records.",
                "is_active": True,
            },
            {
                "code": "manage_projects",
                "name": "Manage projects",
                "category": "projects",
                "description": "Allows creating and editing project records.",
                "is_active": True,
            },
            {
                "code": "manage_project_collaborations",
                "name": "Manage project collaborations",
                "category": "projects",
                "description": "Allows managing project collaboration records.",
                "is_active": True,
            },
        ]

        created_count = 0
        updated_count = 0

        for capability_data in capabilities:
            capability, created = Capability.objects.update_or_create(
                code=capability_data["code"],
                defaults={
                    "name": capability_data["name"],
                    "category": capability_data["category"],
                    "description": capability_data["description"],
                    "is_active": capability_data["is_active"],
                },
            )

            if created:
                created_count += 1
            else:
                updated_count += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Capability seed complete. Created: {created_count}. Updated: {updated_count}."
            )
        )