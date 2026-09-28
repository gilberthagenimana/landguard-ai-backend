from enum import Enum


class UserRole(str, Enum):
    ADMIN = "ADMIN"
    OFFICER = "OFFICER"
    AUDITOR = "AUDITOR"


ALLOWED_ROLE_NAMES = {role.value for role in UserRole}
