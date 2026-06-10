class AuditRecordAccessPolicy:
    """
    MVP audit access policy.

    Audit records are protected data.

    Temporary bootstrap rule:
    only Django superusers may view audit API data.

    Later this must become:
    authenticated user
    -> active membership
    -> acting organization
    -> view_audit_logs capability
    -> scope check
    -> sensitivity check where needed
    """

    @staticmethod
    def can_view_audit_records(*, user) -> bool:
        return bool(user and user.is_authenticated and user.is_superuser)