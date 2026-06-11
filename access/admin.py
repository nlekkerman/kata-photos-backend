from django.contrib import admin

from access.models import Capability, Role, RoleCapability


@admin.register(Capability)
class CapabilityAdmin(admin.ModelAdmin):
    list_display = (
        "code",
        "name",
        "category",
        "is_active",
        "created_at",
    )
    list_filter = (
        "category",
        "is_active",
    )
    search_fields = (
        "code",
        "name",
        "description",
    )
    readonly_fields = (
        "created_at",
        "updated_at",
    )


class RoleCapabilityInline(admin.TabularInline):
    model = RoleCapability
    extra = 0
    autocomplete_fields = (
        "capability",
    )


@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "code",
        "organization",
        "is_system_role",
        "is_active",
        "created_at",
    )
    list_filter = (
        "organization",
        "is_system_role",
        "is_active",
    )
    search_fields = (
        "name",
        "code",
        "description",
        "organization__name",
        "organization__slug",
    )
    autocomplete_fields = (
        "organization",
    )
    readonly_fields = (
        "created_at",
        "updated_at",
    )
    inlines = (
        RoleCapabilityInline,
    )


@admin.register(RoleCapability)
class RoleCapabilityAdmin(admin.ModelAdmin):
    list_display = (
        "role",
        "capability",
        "created_at",
    )
    list_filter = (
        "role__organization",
        "capability__category",
    )
    search_fields = (
        "role__name",
        "role__code",
        "capability__code",
        "capability__name",
    )
    autocomplete_fields = (
        "role",
        "capability",
    )
    readonly_fields = (
        "created_at",
    )