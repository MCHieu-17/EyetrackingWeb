from pydantic import EmailStr, Field, model_validator

from app.schemas.common import CamelModel


class LoginRequest(CamelModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=72)


class RefreshRequest(CamelModel):
    refresh_token: str | None = None


class UserSummary(CamelModel):
    id: str
    email: str
    roles: list[str]
    full_name: str | None = None


class ChangePasswordRequest(CamelModel):
    current_password: str = Field(min_length=8, max_length=72)
    new_password: str = Field(min_length=8, max_length=72)

    @model_validator(mode="after")
    def validate_new_password(self):
        if self.current_password == self.new_password:
            raise ValueError("Mật khẩu mới phải khác mật khẩu hiện tại")
        return self


class TokenPair(CamelModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: UserSummary
