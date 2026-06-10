from audit.models import AuditRecord


class AuditRecordSelector:
    """
    Read/query layer for audit records.

    Views should use selectors instead of building audit queries directly.
    """

    @staticmethod
    def list_records():
        return AuditRecord.objects.select_related("actor").all()

    @staticmethod
    def get_by_uuid(*, uuid):
        return AuditRecord.objects.select_related("actor").get(uuid=uuid)