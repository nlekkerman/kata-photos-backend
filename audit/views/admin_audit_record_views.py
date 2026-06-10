from rest_framework import generics
from rest_framework.exceptions import PermissionDenied

from audit.policies import AuditRecordAccessPolicy
from audit.selectors import AuditRecordSelector
from audit.serializers import (
    AuditRecordAdminDetailSerializer,
    AuditRecordAdminListSerializer,
)


class AdminAuditRecordListView(generics.ListAPIView):
    """
    Admin-family read-only audit list.

    Canonical final route:
    /api/admin/audit/records/

    Audit records are protected data.
    This view must never become public.
    """

    serializer_class = AuditRecordAdminListSerializer

    def get_queryset(self):
        if not AuditRecordAccessPolicy.can_view_audit_records(user=self.request.user):
            raise PermissionDenied("You do not have permission to view audit records.")

        return AuditRecordSelector.list_records()


class AdminAuditRecordDetailView(generics.RetrieveAPIView):
    """
    Admin-family read-only audit detail.

    Canonical final route:
    /api/admin/audit/records/<uuid:uuid>/

    Audit records are protected data.
    This view must never become public.
    """

    serializer_class = AuditRecordAdminDetailSerializer
    lookup_field = "uuid"

    def get_queryset(self):
        if not AuditRecordAccessPolicy.can_view_audit_records(user=self.request.user):
            raise PermissionDenied("You do not have permission to view audit records.")

        return AuditRecordSelector.list_records()