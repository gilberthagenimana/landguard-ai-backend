from typing import Literal

from pydantic import BaseModel, ConfigDict


class NotificationPreferenceUpdate(BaseModel):
    email_enabled: bool
    sms_enabled: bool
    in_app_enabled: bool
    frequency: Literal["instant", "daily", "weekly"]


class NotificationPreferenceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user_id: int
    email_enabled: bool
    sms_enabled: bool
    in_app_enabled: bool
    frequency: str