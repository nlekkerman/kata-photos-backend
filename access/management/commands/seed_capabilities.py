from django.core.management.base import BaseCommand

from access.models import Capability


class Command(BaseCommand):
    help = "Seed the initial Kata Wild RBAC capabilities used for MVP admin testing."

    # Core MVP capability definitions.
    #
    # MVP purpose:
    # - create the first stable backend permission keys
    # - support early Django admin/manual RBAC setup
    # - avoid role-name authorization such as "admin", "reviewer", or "manager"
    #
    # Architecture rule:
    # - code is the stable permission key used by backend policies
    # - name/category/description are human-readable admin helpers
    # - is_active is permission-affecting state and must not be overwritten
    #   for existing records by a seed command
    #
    # Left for later:
    # - add more capability groups only when real workflows need them
    # - audit permission-affecting changes through a dedicated audited workflow
    CORE_CAPABILITIES = [
        {
            "code": "view_audit_logs",
            "name": "View audit logs",
            "category": "audit",
            "description": "Allows viewing audit records.",
        },
        {
            "code": "view_projects",
            "name": "View projects",
            "category": "projects",
            "description": "Allows viewing project records.",
        },
        {
            "code": "manage_projects",
            "name": "Manage projects",
            "category": "projects",
            "description": "Allows creating and editing project records.",
        },
        {
            "code": "manage_project_collaborations",
            "name": "Manage project collaborations",
            "category": "projects",
            "description": "Allows managing project collaboration records.",
        },
    ]

    def handle(self, *args, **options):
        created_count = 0
        skipped_count = 0
        filled_missing_count = 0

        for capability_data in self.CORE_CAPABILITIES:
            # Create missing capabilities as active.
            #
            # This is safe because a missing capability has no previous security state.
            # Existing capabilities are handled below and must not be blindly overwritten.
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

            # Existing capabilities are intentionally not overwritten.
            #
            # This keeps the command safe and rerunnable across local, staging,
            # and production environments.
            #
            # We only fill empty descriptive fields because that repairs incomplete
            # seed data without changing permission behavior.
            if not capability.name:
                capability.name = capability_data["name"]
                changed_fields.append("name")

            if not capability.category:
                capability.category = capability_data["category"]
                changed_fields.append("category")

            if not capability.description:
                capability.description = capability_data["description"]
                changed_fields.append("description")

            # Critical RBAC rule:
            # do not force is_active=True for existing records.
            #
            # A disabled capability may be disabled intentionally to block access.
            # Rerunning a seed command must never silently reactivate it.
            #
            # Future permission changes should happen through Django admin or,
            # later, a dedicated audited RBAC management workflow.
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
                "Capability seed complete. "
                f"Created: {created_count}. "
                f"Filled missing: {filled_missing_count}. "
                f"Skipped existing: {skipped_count}."
            )
        )