from pydantic import BaseModel, Field

from app.core.roles import UserRole


class LoginRequest(BaseModel):
    email: str | None = None
    username: str | None = None
    password: str
    role: UserRole

    def identifier(self) -> str:
        value = (self.email or self.username or "").strip()
        if not value:
            raise ValueError("Email or username is required")
        return value


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
