from rest_framework import serializers

from organizations.models import Membership


class MembershipAdminSerializer(serializers.ModelSerializer):
    class Meta:
        model = Membership
        fields = [
            "id",
            "user",
            "organization",
            "status",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "created_at",
            "updated_at",
        ]