"""System settings service for LandGuard AI.

Persists key/value system configuration in the ``system_config`` table and
exposes validated access plus policy helpers used by authentication and the
file storage workflows.
"""
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.models.system_config import SystemConfig

DEFAULTS: dict[str, str] = {
    "general.system_name": "LandGuard AI",
    "general.organization": "Rwanda Land Administration",
    "general.review_threshold": "medium",
    "general.allowed_file_types": "pdf,jpg,jpeg,png",
    "security.jwt_expiry_minutes": "60",
    "security.min_password_length": "8",
    "security.max_failed_logins": "5",
    "security.lockout_minutes": "30",
    "notifications.email_high_risk": "false",
    "notifications.email_awaiting_review": "false",
    "notifications.email_account_events": "false",
    "notifications.in_app_system_alerts": "true",
    "notifications.frequency": "instant",
    "file_storage.max_file_size_mb": "10",
}

SECURITY_INT_SETTINGS: dict[str, dict[str, Any]] = {
    "security.jwt_expiry_minutes": {"default": 60, "min": 5, "max": 1440},
    "security.min_password_length": {"default": 8, "min": 8, "max": 64},
    "security.max_failed_logins": {"default": 5, "min": 1, "max": 20},
    "security.lockout_minutes": {"default": 30, "min": 1, "max": 1440},
}

NOTIFICATION_BOOL_SETTINGS = {
    "notifications.email_high_risk": "true",
    "notifications.email_awaiting_review": "true",
    "notifications.email_account_events": "false",
    "notifications.in_app_system_alerts": "true",
}

NOTIFICATION_FREQUENCY_SETTINGS = {
    "notifications.frequency": {"default": "instant", "values": ["instant", "daily", "weekly"]},
}

NOTIFICATION_PREFERENCE_KEYS = (
    "notifications.email_high_risk",
    "notifications.email_awaiting_review",
    "notifications.email_account_events",
    "notifications.in_app_system_alerts",
)

FILE_STORAGE_MAX_SIZE_SETTINGS = {
    "file_storage.max_file_size_mb": {"default": 10.0, "min": 1.0, "max": 500.0},
}


def list_settings(db: Session) -> list[SystemConfig]:
    """List all persisted system settings ordered by key."""
    return db.query(SystemConfig).order_by(SystemConfig.key.asc()).all()


def get_setting_value(db: Session, key: str, default: str = "") -> str:
    """Return a setting value by key, falling back to the default."""
    record = db.query(SystemConfig).filter(SystemConfig.key == key).first()
    if record is None:
        return default
    return record.value


def save_setting(
    db: Session,
    key: str,
    value: str,
    updated_by: int | None = None,
    description: str | None = None,
) -> SystemConfig:
    """Create or update a system setting."""
    record = db.query(SystemConfig).filter(SystemConfig.key == key).first()
    if record is None:
        record = SystemConfig(key=key, value=value, description=description, updated_by=updated_by)
        db.add(record)
    else:
        record.value = value
        if description is not None:
            record.description = description
        record.updated_by = updated_by
    db.commit()
    db.refresh(record)
    return record


def validate_setting(key: str, value: str) -> str:
    """Validate and normalize a system setting value."""
    if key == "general.system_name":
        cleaned = value.strip()
        if not cleaned or len(cleaned) > 100:
            raise ValueError("System name must be between 1 and 100 characters.")
        return cleaned
    if key == "general.organization":
        cleaned = value.strip()
        if not cleaned or len(cleaned) > 150:
            raise ValueError("Organization must be between 1 and 150 characters.")
        return cleaned
    if key == "general.review_threshold":
        cleaned = value.strip().lower()
        if cleaned not in {"low", "medium", "high"}:
            raise ValueError("Review threshold must be one of: low, medium, high.")
        return cleaned
    if key == "general.allowed_file_types":
        parts = [part.strip().lower() for part in value.split(",") if part.strip()]
        if not parts or len(parts) > 10:
            raise ValueError("Allowed file types must be a comma-separated list of at most 10 entries.")
        if any(not part.isalpha() for part in parts):
            raise ValueError("Allowed file types must be alphabetic extensions such as pdf, jpg, png.")
        return ",".join(parts)
    if key in SECURITY_INT_SETTINGS:
        spec = SECURITY_INT_SETTINGS[key]
        try:
            parsed = int(str(value).strip())
        except (ValueError, TypeError) as exc:
            raise ValueError(f"{key} must be an integer.") from exc
        if parsed < spec["min"] or parsed > spec["max"]:
            raise ValueError(f"{key} must be between {spec['min']} and {spec['max']}.")
        return str(parsed)
    if key in NOTIFICATION_BOOL_SETTINGS:
        cleaned = str(value).strip().lower()
        if cleaned not in {"true", "false"}:
            raise ValueError(f"{key} must be a boolean value (true or false).")
        return "true" if cleaned == "true" else "false"
    if key in NOTIFICATION_FREQUENCY_SETTINGS:
        cleaned = str(value).strip().lower()
        if cleaned not in NOTIFICATION_FREQUENCY_SETTINGS[key]["values"]:
            raise ValueError(f"{key} must be one of: {', '.join(NOTIFICATION_FREQUENCY_SETTINGS[key]['values'])}.")
        return cleaned
    if key in FILE_STORAGE_MAX_SIZE_SETTINGS:
        try:
            parsed = float(str(value).strip())
        except (ValueError, TypeError) as exc:
            raise ValueError(f"{key} must be a number.") from exc
        spec = FILE_STORAGE_MAX_SIZE_SETTINGS[key]
        if parsed < spec["min"] or parsed > spec["max"]:
            raise ValueError(f"{key} must be between {spec['min']} and {spec['max']}.")
        return str(parsed)
    raise ValueError(f"Unknown system setting key: {key}")


def get_security_policy(db: Session | None = None) -> dict[str, int]:
    """Return the effective security policy (DB-backed with safe defaults)."""

    def _int(key: str, default: int, minimum: int, maximum: int) -> int:
        raw = get_setting_value(db, key, DEFAULTS.get(key, str(default))) if db is not None else str(default)
        try:
            parsed = int(str(raw).strip())
        except (ValueError, TypeError):
            parsed = default
        return max(minimum, min(maximum, parsed))

    return {
        "jwt_expiry_minutes": _int("security.jwt_expiry_minutes", 60, 5, 1440),
        "min_password_length": _int("security.min_password_length", 8, 8, 64),
        "max_failed_logins": _int("security.max_failed_logins", 5, 1, 20),
        "lockout_minutes": _int("security.lockout_minutes", 30, 1, 1440),
    }


def get_notification_preferences(db: Session) -> dict[str, Any]:
    """Return effective notification preferences (DB-backed with safe defaults)."""

    def _bool(key: str, default: bool) -> bool:
        raw = get_setting_value(db, key, DEFAULTS.get(key, str(default))).lower()
        return raw == "true"

    frequency = get_setting_value(db, "notifications.frequency", DEFAULTS["notifications.frequency"]).lower()
    if frequency not in NOTIFICATION_FREQUENCY_SETTINGS["notifications.frequency"]["values"]:
        frequency = NOTIFICATION_FREQUENCY_SETTINGS["notifications.frequency"]["default"]
    return {
        "email_high_risk": _bool("notifications.email_high_risk", True),
        "email_awaiting_review": _bool("notifications.email_awaiting_review", True),
        "email_account_events": _bool("notifications.email_account_events", False),
        "in_app_system_alerts": _bool("notifications.in_app_system_alerts", True),
        "frequency": frequency,
    }


def get_file_storage_policy(db: Session) -> dict[str, Any]:
    """Return the effective file storage policy."""
    allowed_raw = get_setting_value(db, "general.allowed_file_types", DEFAULTS["general.allowed_file_types"])
    allowed = [part.strip().lower() for part in allowed_raw.split(",") if part.strip()]
    max_raw = get_setting_value(db, "file_storage.max_file_size_mb", DEFAULTS["file_storage.max_file_size_mb"])
    try:
        max_size_mb = float(str(max_raw).strip())
    except (ValueError, TypeError):
        max_size_mb = float(DEFAULTS["file_storage.max_file_size_mb"])
    return {
        "allowed_file_types": allowed,
        "max_file_size_mb": max_size_mb,
        "storage_provider": "local",
        "retention_policy": "preserve",
    }


def check_database_connection(db: Session) -> bool:
    """Run a lightweight connectivity check against the configured database."""
    try:
        result = db.execute(text("SELECT 1"))
        return result.scalar() is not None
    except Exception:
        return False
