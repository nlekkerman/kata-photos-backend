from django.contrib import admin

from organizations.models import Membership, Organization


@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
    list_display = ("name", "organization_type", "is_active", "created_at")
    list_filter = ("organization_type", "is_active")
    search_fields = ("name", "slug")
    prepopulated_fields = {"slug": ("name",)}
    readonly_fields = ("created_at", "updated_at")


@admin.register(Membership)
class MembershipAdmin(admin.ModelAdmin):
    list_display = ("user", "organization", "status", "created_at")
    list_filter = ("status", "organization")
    search_fields = ("user__username", "user__email", "organization__name")
    readonly_fields = ("created_at", "updated_at")